/**
 * RpcClient — JSON-RPC 2.0 over WebSocket.
 *
 * Communicates with the Python CAD server.  Supports request/response
 * (call), notifications (notify), server-sent events (on), automatic
 * reconnection with exponential backoff, and connection lifecycle
 * management.
 */

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const DEFAULT_TIMEOUT_MS = 30000;

export class RpcClient {
  /**
   * @param {string} url - WebSocket URL (e.g. 'ws://127.0.0.1:8765/ws')
   */
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.requestId = 0;
    /** @type {Map<number, {resolve, reject, timer}>} */
    this.pending = new Map();
    /** @type {Map<string, Set<function>>} event type -> callbacks */
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxRetries = 10;
    this._shouldReconnect = true;
    this._isConnected = false;

    // Bound handler (avoids creating closures every time)
    this._onMessage = this._onMessage.bind(this);
    this._onClose = this._onClose.bind(this);
    this._onError = this._onError.bind(this);
    this._onOpen = this._onOpen.bind(this);
  }

  // ── Connection Lifecycle ──────────────────────────────────────────

  /**
   * Open the WebSocket connection.
   * @returns {Promise<void>} Resolves when the connection is established.
   */
  connect() {
    return new Promise((resolve, reject) => {
      if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
        resolve();
        return;
      }

      this._shouldReconnect = true;
      this.reconnectAttempts = 0;

      try {
        this.ws = new WebSocket(this.url);
      } catch (err) {
        reject(err);
        return;
      }

      this.ws.onopen = () => {
        this._isConnected = true;
        this.reconnectAttempts = 0;
        this._dispatchEvent('connection_open', {});
        resolve();
      };

      this.ws.onclose = (event) => {
        this._isConnected = false;
        this._dispatchEvent('connection_close', { code: event.code, reason: event.reason });
        this._rejectAllPending(new Error(`WebSocket closed (code=${event.code})`));
        if (this._shouldReconnect) {
          this._scheduleReconnect();
        }
      };

      this.ws.onerror = (err) => {
        this._dispatchEvent('connection_error', { error: err });
        reject(err);
      };

      this.ws.onmessage = this._onMessage;
    });
  }

  /**
   * Close the WebSocket connection and stop reconnecting.
   */
  disconnect() {
    this._shouldReconnect = false;
    this._rejectAllPending(new Error('Client disconnected'));
    if (this.ws) {
      // Remove listeners to prevent reconnect on intentional close
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.close();
      this.ws = null;
    }
    this._isConnected = false;
  }

  /**
   * @returns {boolean} Whether the WebSocket is currently open.
   */
  get isConnected() {
    return this._isConnected;
  }

  // ── JSON-RPC Calls ────────────────────────────────────────────────

  /**
   * Send a JSON-RPC 2.0 request and wait for the response.
   * @param {string} method - RPC method name.
   * @param {object} [params] - Parameters object.
   * @param {number} [timeoutMs] - Timeout in ms (default 30000).
   * @returns {Promise<object>} The result field from the response.
   */
  call(method, params = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
    return new Promise((resolve, reject) => {
      if (!this._isConnected || !this.ws) {
        reject(new Error('Not connected'));
        return;
      }

      const id = ++this.requestId;
      const request = {
        jsonrpc: '2.0',
        id,
        method,
        params,
      };

      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`RPC timeout: ${method} (${timeoutMs}ms)`));
      }, timeoutMs);

      this.pending.set(id, { resolve, reject, timer });

      try {
        this.ws.send(JSON.stringify(request));
      } catch (err) {
        this.pending.delete(id);
        clearTimeout(timer);
        reject(err);
      }
    });
  }

  /**
   * Send a JSON-RPC 2.0 notification (no response expected).
   * @param {string} method - RPC method name.
   * @param {object} [params] - Parameters object.
   */
  notify(method, params = {}) {
    if (!this._isConnected || !this.ws) return;

    const request = {
      jsonrpc: '2.0',
      method,
      params,
    };

    try {
      this.ws.send(JSON.stringify(request));
    } catch (err) {
      console.warn('RPC notify failed:', err);
    }
  }

  // ── Server-Sent Events ────────────────────────────────────────────

  /**
   * Subscribe to server-sent events.
   * @param {string} eventType - Event type string (e.g. 'document_updated').
   * @param {function} callback - Called with the event payload.
   * @returns {function} Unsubscribe function.
   */
  on(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType).add(callback);
    return () => {
      const set = this.listeners.get(eventType);
      if (set) set.delete(callback);
    };
  }

  /**
   * Subscribe to a one-shot event.
   * @param {string} eventType
   * @param {function} callback
   * @returns {function} Unsubscribe function.
   */
  once(eventType, callback) {
    const wrapper = (payload) => {
      cleanup();
      callback(payload);
    };
    const cleanup = this.on(eventType, wrapper);
    return cleanup;
  }

  // ── Handshake ─────────────────────────────────────────────────────

  /**
   * Perform version/capability negotiation with the server.
   * Must be called after connect() resolves.
   * @returns {Promise<object>} Server capabilities.
   */
  async handshake() {
    const result = await this.call('handshake', {
      client_name: 'fiona-cad-frontend',
      client_version: '0.1.0',
      protocol_version: '1.0',
      capabilities: ['full_state', 'incremental_updates', 'camera_sync'],
    });
    return result;
  }

  // ── Reconnection ──────────────────────────────────────────────────

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxRetries) {
      this._dispatchEvent('reconnect_exhausted', { attempts: this.reconnectAttempts });
      return;
    }

    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, this.reconnectAttempts),
      RECONNECT_MAX_MS
    );
    this.reconnectAttempts++;

    this._dispatchEvent('reconnecting', {
      attempt: this.reconnectAttempts,
      maxRetries: this.maxRetries,
      delay,
    });

    setTimeout(() => this._reconnect(), delay);
  }

  async _reconnect() {
    try {
      await this.connect();
      await this.handshake();
      this._dispatchEvent('reconnected', {});
    } catch (err) {
      // onclose will schedule another attempt
    }
  }

  // ── Internal ──────────────────────────────────────────────────────

  _onMessage(event) {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      console.warn('RPC client: invalid JSON from server:', event.data);
      return;
    }

    // JSON-RPC 2.0 Response (has id)
    if (data && typeof data.id === 'number') {
      const pending = this.pending.get(data.id);
      if (!pending) return; // stale response, ignore

      this.pending.delete(data.id);
      clearTimeout(pending.timer);

      if (data.error) {
        pending.reject(new Error(data.error.message || 'RPC error'));
      } else {
        pending.resolve(data.result);
      }
      return;
    }

    // Server-sent event (no id, has method)
    if (data && typeof data.method === 'string') {
      this._dispatchEvent(data.method, data.params || {});
      return;
    }

    console.warn('RPC client: unhandled message:', data);
  }

  _onClose() {
    // Handled via ws.onclose above
  }

  _onError() {
    // Handled via ws.onerror above
  }

  _onOpen() {
    // Handled via ws.onopen above
  }

  _dispatchEvent(eventType, payload) {
    const set = this.listeners.get(eventType);
    if (set) {
      for (const cb of set) {
        try {
          cb(payload);
        } catch (err) {
          console.warn(`RPC event handler error (${eventType}):`, err);
        }
      }
    }
  }

  _rejectAllPending(error) {
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}
