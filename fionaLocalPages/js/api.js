/* ==========================================================================
   api.js — HTTP + WebSocket Client for Backend Communication
   ==========================================================================
   Provides a unified client for REST API calls, WebSocket connections,
   and Server-Sent Events.  Features typed errors, interceptors, auto-
   reconnect with exponential backoff, request deduplication, and
   AbortController support.
   
   Usage:
     import { createApi } from './api.js';
     const api = createApi({ baseURL: 'http://localhost:9876' });
     const data = await api.get('/api/actions');
     const ws = api.connect('ws://localhost:9876/ws');
   ========================================================================== */

/* ── Custom Error Types ─────────────────────────────────────────────────── */

/**
 * Base API error thrown when the server returns a non-ok response.
 * @extends Error
 */
export class ApiError extends Error {
  /**
   * @param {string} message
   * @param {number} [status]
   * @param {*} [data] - The parsed error body
   */
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Error thrown when a network request fails (no response received).
 * @extends Error
 */
export class NetworkError extends Error {
  /**
   * @param {string} message
   * @param {Error} [original]
   */
  constructor(message, original = null) {
    super(message);
    this.name = 'NetworkError';
    this.original = original;
  }
}

/**
 * Error thrown when a request exceeds the specified timeout.
 * @extends Error
 */
export class TimeoutError extends Error {
  /**
   * @param {string} message
   * @param {number} timeoutMs
   */
  constructor(message, timeoutMs) {
    super(message);
    this.name = 'TimeoutError';
    this.timeoutMs = timeoutMs;
  }
}

/* ── Constants ──────────────────────────────────────────────────────────── */

const DEFAULT_BASE_URL = 'http://localhost:8765';
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const WS_RECONNECT_INITIAL = 1000; // 1 second
const WS_RECONNECT_MAX = 30000; // 30 seconds
const WS_RECONNECT_JITTER = 0.3; // ±30% jitter

/* ── Utility Functions ──────────────────────────────────────────────────── */

/**
 * Encode an object as URL query parameters.
 * @param {Object} params
 * @returns {string}
 */
function encodeQueryParams(params) {
  if (!params || Object.keys(params).length === 0) return '';
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) {
      searchParams.append(key, String(value));
    }
  }
  const str = searchParams.toString();
  return str ? `?${str}` : '';
}

/**
 * Create an AbortSignal that times out after a given duration.
 * @param {number} ms - Timeout in milliseconds
 * @param {AbortController} [parentController] - Optional parent AbortController
 * @returns {{ signal: AbortSignal, clear: Function }}
 */
function createTimeoutSignal(ms, parentController) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new TimeoutError(`Request timed out after ${ms}ms`, ms)), ms);
  
  // If a parent controller is provided, forward its abort
  if (parentController) {
    parentController.signal.addEventListener('abort', () => {
      clearTimeout(timer);
      controller.abort(parentController.signal.reason);
    }, { once: true });
  }

  return {
    signal: controller.signal,
    clear: () => clearTimeout(timer),
  };
}

/**
 * Compute exponential backoff delay with jitter.
 * @param {number} attempt - Attempt number (0-indexed)
 * @param {number} [initial=1000]
 * @param {number} [max=30000]
 * @returns {number} Delay in milliseconds
 */
function backoffDelay(attempt, initial = WS_RECONNECT_INITIAL, max = WS_RECONNECT_MAX) {
  const delay = Math.min(initial * Math.pow(2, attempt), max);
  const jitter = delay * WS_RECONNECT_JITTER * (Math.random() * 2 - 1);
  return Math.round(delay + jitter);
}

/* ── Request Deduplication ─────────────────────────────────────────────── */

/**
 * Simple in-flight request deduplicator.
 * Keyed by method + URL + body, so identical requests share one promise.
 */
class RequestDedup {
  constructor() {
    /** @type {Map<string, Promise<*>>} */
    this._inflight = new Map();
  }

  /**
   * Generate a dedup key from request parameters.
   * @param {string} method
   * @param {string} url
   * @param {*} [body]
   * @returns {string}
   */
  _key(method, url, body) {
    return `${method}:${url}:${body ? JSON.stringify(body) : ''}`;
  }

  /**
   * Run a request, deduplicating if an identical one is in flight.
   * @param {string} method
   * @param {string} url
   * @param {Function} requestFn - () => Promise
   * @param {*} [body]
   * @returns {Promise<*>}
   */
  async run(method, url, requestFn, body) {
    const key = this._key(method, url, body);
    const existing = this._inflight.get(key);
    if (existing) return existing;

    const promise = requestFn().finally(() => {
      this._inflight.delete(key);
    });
    this._inflight.set(key, promise);
    return promise;
  }

  /** Clear all in-flight requests. */
  clear() {
    this._inflight.clear();
  }
}

/* ── WebSocket Connection Manager ───────────────────────────────────────── */

/**
 * Manages a single WebSocket connection with auto-reconnect.
 * Emits events: 'open', 'close', 'message', 'error', 'reconnecting'
 *
 * @class WSConnection
 */
class WSConnection {
  /**
   * @param {string} url - WebSocket URL
   * @param {Object} [options]
   * @param {Function} [options.onMessage] - Message handler
   * @param {Function} [options.onOpen] - Open handler
   * @param {Function} [options.onClose] - Close handler
   * @param {Function} [options.onError] - Error handler
   * @param {boolean} [options.autoReconnect=true]
   * @param {Function} [options.shouldReconnect] - (event) => boolean
   */
  constructor(url, options = {}) {
    /** @private */
    this._url = url;
    this._options = options;
    this._autoReconnect = options.autoReconnect !== false;
    this._shouldReconnect = options.shouldReconnect || (() => true);

    /** @private */
    this._ws = null;
    this._isClosing = false;
    this._reconnectAttempt = 0;
    this._reconnectTimer = null;
    this._listeners = new Map();
    this._isConnected = false;

    this._connect();
  }

  /**
   * Initiate the WebSocket connection.
   * @private
   */
  _connect() {
    if (this._isClosing) return;
    try {
      this._ws = new WebSocket(this._url);
    } catch (err) {
      this._emit('error', err);
      this._scheduleReconnect();
      return;
    }

    this._ws.onopen = () => {
      this._isConnected = true;
      this._reconnectAttempt = 0;
      this._emit('open', {});
      if (this._options.onOpen) this._options.onOpen();
    };

    this._ws.onclose = (event) => {
      this._isConnected = false;
      this._emit('close', event);
      if (this._options.onClose) this._options.onClose(event);
      if (!this._isClosing && this._autoReconnect && this._shouldReconnect(event)) {
        this._scheduleReconnect();
      }
    };

    this._ws.onerror = (event) => {
      this._emit('error', event);
      if (this._options.onError) this._options.onError(event);
    };

    this._ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        data = event.data;
      }
      this._emit('message', data);
      if (this._options.onMessage) this._options.onMessage(data);
    };
  }

  /**
   * Schedule a reconnection attempt with exponential backoff.
   * @private
   */
  _scheduleReconnect() {
    if (this._isClosing) return;
    const delay = backoffDelay(this._reconnectAttempt);
    this._reconnectAttempt++;
    this._emit('reconnecting', { attempt: this._reconnectAttempt, delay });
    this._reconnectTimer = setTimeout(() => this._connect(), delay);
  }

  /**
   * Send a JSON message through the WebSocket.
   * @param {*} data - Will be JSON.stringify'd
   * @returns {boolean} True if the message was sent
   */
  send(data) {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
      console.warn('[api] WebSocket not open, cannot send');
      return false;
    }
    try {
      this._ws.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    } catch (err) {
      this._emit('error', err);
      return false;
    }
  }

  /**
   * Register an event listener on this connection.
   * @param {string} event - 'open' | 'close' | 'message' | 'error' | 'reconnecting'
   * @param {Function} callback
   * @returns {Function} Unsubscribe function
   */
  on(event, callback) {
    if (!this._listeners.has(event)) {
      this._listeners.set(event, new Set());
    }
    this._listeners.get(event).add(callback);
    return () => {
      const set = this._listeners.get(event);
      if (set) set.delete(callback);
    };
  }

  /**
   * Remove an event listener.
   * @param {string} event
   * @param {Function} callback
   */
  off(event, callback) {
    const set = this._listeners.get(event);
    if (set) set.delete(callback);
  }

  /**
   * Emit an event to all registered listeners.
   * @private
   * @param {string} event
   * @param {*} data
   */
  _emit(event, data) {
    const set = this._listeners.get(event);
    if (set) {
      for (const cb of set) {
        try { cb(data); } catch (e) { console.error('[api] WS listener error:', e); }
      }
    }
  }

  /**
   * Check if the connection is currently open.
   * @returns {boolean}
   */
  get connected() {
    return this._isConnected;
  }

  /**
   * Get the current readyState of the underlying WebSocket.
   * @returns {number}
   */
  get readyState() {
    return this._ws ? this._ws.readyState : WebSocket.CLOSED;
  }

  /**
   * Close the WebSocket connection.  Will not auto-reconnect.
   */
  close() {
    this._isClosing = true;
    this._autoReconnect = false;
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
    this._isConnected = false;
  }
}

/* ── SSE (Server-Sent Events) Manager ───────────────────────────────────── */

/**
 * Manages an EventSource connection for SSE streams.
 * Emits events received from the server.
 *
 * @class SSEConnection
 */
class SSEConnection {
  /**
   * @param {string} url
   * @param {Object} [options]
   * @param {Function} [options.onMessage] - Catch-all message handler
   * @param {Object} [options.eventHandlers] - { 'eventName': handler(data) }
   */
  constructor(url, options = {}) {
    this._url = url;
    this._options = options;
    this._es = null;
    this._listeners = new Map();
    this._connect();
  }

  /**
   * @private
   */
  _connect() {
    try {
      this._es = new EventSource(this._url);
    } catch (err) {
      this._emit('error', err);
      return;
    }

    this._es.onopen = () => {
      this._emit('open', {});
    };

    this._es.onerror = (event) => {
      this._emit('error', event);
    };

    this._es.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        data = event.data;
      }
      this._emit('message', data);
      if (this._options.onMessage) this._options.onMessage(data);
    };

    // Register named event handlers from options
    if (this._options.eventHandlers) {
      for (const [eventName, handler] of Object.entries(this._options.eventHandlers)) {
        this._es.addEventListener(eventName, (event) => {
          let data;
          try {
            data = JSON.parse(event.data);
          } catch {
            data = event.data;
          }
          handler(data);
        });
      }
    }
  }

  /**
   * Register an event listener.
   * @param {string} event - 'open' | 'message' | 'error' | or a named SSE event
   * @param {Function} callback
   * @returns {Function} Unsubscribe function
   */
  on(event, callback) {
    if (event === 'open' || event === 'message' || event === 'error') {
      if (!this._listeners.has(event)) {
        this._listeners.set(event, new Set());
      }
      this._listeners.get(event).add(callback);
      return () => {
        const set = this._listeners.get(event);
        if (set) set.delete(callback);
      };
    }
    // Named SSE event
    if (this._es) {
      this._es.addEventListener(event, callback);
      return () => {
        if (this._es) this._es.removeEventListener(event, callback);
      };
    }
    return () => {};
  }

  /**
   * @private
   */
  _emit(event, data) {
    const set = this._listeners.get(event);
    if (set) {
      for (const cb of set) {
        try { cb(data); } catch (e) { console.error('[api] SSE listener error:', e); }
      }
    }
  }

  /**
   * Close the SSE connection.
   */
  close() {
    if (this._es) {
      this._es.close();
      this._es = null;
    }
  }
}

/* ── API Client Factory ─────────────────────────────────────────────────── */

/**
 * Create the API client instance.
 *
 * @param {Object} [options]
 * @param {string} [options.baseURL='http://localhost:8765']
 * @param {number} [options.timeout=30000]
 * @param {Object} [options.headers={}] - Default headers for all requests
 * @param {Function} [options.onError] - Global error handler: (error) => void
 * @returns {ApiClient}
 */
export function createApi(options = {}) {
  const baseURL = (options.baseURL || DEFAULT_BASE_URL).replace(/\/+$/, '');
  const defaultTimeout = options.timeout || DEFAULT_TIMEOUT;
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...(options.headers || {}),
  };

  /** @type {Function[]} Request interceptors: (config) => config */
  const _requestInterceptors = [];

  /** @type {Function[]} Response interceptors: (response) => response */
  const _responseInterceptors = [];

  /** @type {RequestDedup} */
  const _dedup = new RequestDedup();

  /** @type {Map<string, WSConnection>} Active WebSocket connections */
  const _wsConnections = new Map();

  /** @type {Map<string, SSEConnection>} Active SSE connections */
  const _sseConnections = new Map();

  /**
   * Global error handler.
   * @type {Function|undefined}
   */
  const _onError = options.onError;

  /* ── Request Execution ────────────────────────────────────────────────── */

  /**
   * Execute an HTTP request.
   *
   * @param {string} method - HTTP method
   * @param {string} path - URL path (e.g. '/api/actions')
   * @param {Object} [opts]
   * @param {Object} [opts.params] - Query parameters
   * @param {*} [opts.body] - Request body
   * @param {Object} [opts.headers] - Additional headers
   * @param {number} [opts.timeout] - Timeout in ms
   * @param {AbortSignal} [opts.signal] - External AbortSignal
   * @param {boolean} [opts.deduplicate=false] - Deduplicate identical in-flight requests
   * @param {'json'|'text'|'blob'} [opts.responseType='json'] - Response type
   * @returns {Promise<*>}
   */
  async function _request(method, path, opts = {}) {
    // Build URL
    const queryString = opts.params ? encodeQueryParams(opts.params) : '';
    const url = `${baseURL}${path}${queryString}`;

    // Build config object for interceptors
    const config = {
      method,
      url,
      path,
      headers: { ...defaultHeaders, ...(opts.headers || {}) },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      timeout: opts.timeout || defaultTimeout,
      signal: opts.signal || null,
    };

    // Run request interceptors
    let interceptedConfig = config;
    for (const interceptor of _requestInterceptors) {
      try {
        const result = interceptor(interceptedConfig);
        interceptedConfig = result || interceptedConfig;
      } catch (err) {
        console.error('[api] Request interceptor error:', err);
      }
    }

    // Create timeout signal (with external abort forwarding)
    const timeoutControl = createTimeoutSignal(interceptedConfig.timeout, 
      interceptedConfig.signal ? { signal: interceptedConfig.signal } : null
    );

    /** Merge signals: external + timeout */
    const combinedSignal = interceptedConfig.signal
      ? _combineSignals(interceptedConfig.signal, timeoutControl.signal)
      : timeoutControl.signal;

    const requestFn = async () => {
      let response;
      try {
        response = await fetch(interceptedConfig.url, {
          method: interceptedConfig.method,
          headers: interceptedConfig.headers,
          body: interceptedConfig.body,
          signal: combinedSignal,
        });
      } catch (err) {
        timeoutControl.clear();
        if (err instanceof TimeoutError) throw err;
        if (err.name === 'AbortError') {
          const reason = combinedSignal.reason;
          if (reason instanceof TimeoutError) throw reason;
          throw new NetworkError('Request was aborted', err);
        }
        throw new NetworkError(`Network error: ${err.message}`, err);
      }

      timeoutControl.clear();

      // Run response interceptors
      let interceptedResponse = response;
      for (const interceptor of _responseInterceptors) {
        try {
          const result = interceptor(interceptedResponse);
          interceptedResponse = result || interceptedResponse;
        } catch (err) {
          console.error('[api] Response interceptor error:', err);
        }
      }

      // Parse response body
      let data;
      const responseType = opts.responseType || 'json';
      try {
        if (responseType === 'json') {
          data = await interceptedResponse.json();
        } else if (responseType === 'text') {
          data = await interceptedResponse.text();
        } else if (responseType === 'blob') {
          data = await interceptedResponse.blob();
        } else {
          data = await interceptedResponse.text();
        }
      } catch (parseErr) {
        // If response is not JSON, get text anyway
        try {
          data = await interceptedResponse.text();
        } catch {
          data = null;
        }
      }

      // Handle error responses
      if (!interceptedResponse.ok) {
        const errMsg = data?.error?.message || data?.error || interceptedResponse.statusText || 'Unknown error';
        const apiErr = new ApiError(errMsg, interceptedResponse.status, data);
        if (_onError) _onError(apiErr);
        throw apiErr;
      }

      // Standard envelope: { ok, data, error, meta }
      if (data && typeof data === 'object' && 'ok' in data) {
        if (data.ok === false) {
          const errMsg = data.error?.message || data.error || 'Request failed';
          const apiErr = new ApiError(errMsg, interceptedResponse.status, data);
          if (_onError) _onError(apiErr);
          throw apiErr;
        }
        return data.data !== undefined ? data.data : data;
      }

      return data;
    };

    // Deduplicate if requested
    if (opts.deduplicate) {
      return _dedup.run(method, path, requestFn, opts.body);
    }

    return requestFn();
  }

  /**
   * Combine two AbortSignals into one.
   * @param {AbortSignal} s1
   * @param {AbortSignal} s2
   * @returns {AbortSignal}
   */
  function _combineSignals(s1, s2) {
    if (s1.aborted) return s1;
    if (s2.aborted) return s2;
    const controller = new AbortController();
    const onAbort = () => controller.abort();
    s1.addEventListener('abort', onAbort, { once: true });
    s2.addEventListener('abort', onAbort, { once: true });
    // Clean up listeners when the combined signal aborts
    controller.signal.addEventListener('abort', () => {
      s1.removeEventListener('abort', onAbort);
      s2.removeEventListener('abort', onAbort);
    }, { once: true });
    return controller.signal;
  }

  /* ── Public HTTP Methods ──────────────────────────────────────────────── */

  /**
   * Send a GET request.
   * @param {string} path
   * @param {Object} [params] - Query parameters
   * @param {Object} [opts] - Additional options (timeout, signal, headers, deduplicate, responseType)
   * @returns {Promise<*>}
   */
  function get(path, params = {}, opts = {}) {
    return _request('GET', path, { ...opts, params });
  }

  /**
   * Send a POST request.
   * @param {string} path
   * @param {*} [body]
   * @param {Object} [opts]
   * @returns {Promise<*>}
   */
  function post(path, body, opts = {}) {
    return _request('POST', path, { ...opts, body });
  }

  /**
   * Send a PUT request.
   * @param {string} path
   * @param {*} [body]
   * @param {Object} [opts]
   * @returns {Promise<*>}
   */
  function put(path, body, opts = {}) {
    return _request('PUT', path, { ...opts, body });
  }

  /**
   * Send a DELETE request.
   * @param {string} path
   * @param {Object} [opts]
   * @returns {Promise<*>}
   */
  function del(path, opts = {}) {
    return _request('DELETE', path, opts);
  }

  /* ── Interceptors ─────────────────────────────────────────────────────── */

  /**
   * Register a request interceptor.
   * The interceptor receives a config object and can modify it or return a new one.
   * @param {Function} fn - (config) => config | void
   * @returns {Function} Unregister function
   */
  function onRequest(fn) {
    _requestInterceptors.push(fn);
    return () => {
      const idx = _requestInterceptors.indexOf(fn);
      if (idx >= 0) _requestInterceptors.splice(idx, 1);
    };
  }

  /**
   * Register a response interceptor.
   * The interceptor receives the Response object and can modify it.
   * @param {Function} fn - (response) => response | void
   * @returns {Function} Unregister function
   */
  function onResponse(fn) {
    _responseInterceptors.push(fn);
    return () => {
      const idx = _responseInterceptors.indexOf(fn);
      if (idx >= 0) _responseInterceptors.splice(idx, 1);
    };
  }

  /* ── WebSocket Support ────────────────────────────────────────────────── */

  /**
   * Connect to a WebSocket endpoint.
   * If a connection to the same URL already exists, returns the existing one.
   *
   * @param {string} url - WebSocket URL (e.g. 'ws://localhost:9876/ws')
   * @param {Object} [wsOptions]
   * @param {boolean} [wsOptions.autoReconnect=true]
   * @param {Function} [wsOptions.shouldReconnect]
   * @returns {WSConnection}
   */
  function connect(url, wsOptions = {}) {
    const existing = _wsConnections.get(url);
    if (existing) return existing;

    const conn = new WSConnection(url, {
      ...wsOptions,
      onMessage: (data) => {
        // Forward JSON-RPC notifications to event listeners
        if (data && typeof data === 'object' && data.method && !data.id) {
          _emitWsEvent(data.method, data.params);
        }
      },
    });
    _wsConnections.set(url, conn);
    return conn;
  }

  /** @type {Map<string, Set<Function>>} WebSocket event listeners */
  const _wsEventListeners = new Map();

  /**
   * Register a WebSocket event listener.
   * Listens for JSON-RPC notification methods from the server.
   *
   * @param {string} event - Event name (e.g. 'agent.token', 'system.notification')
   * @param {Function} callback - (params) => void
   * @returns {Function} Unsubscribe function
   */
  function on(event, callback) {
    if (!_wsEventListeners.has(event)) {
      _wsEventListeners.set(event, new Set());
    }
    _wsEventListeners.get(event).add(callback);
    return () => {
      const set = _wsEventListeners.get(event);
      if (set) set.delete(callback);
    };
  }

  /**
   * Remove a WebSocket event listener.
   * @param {string} event
   * @param {Function} callback
   */
  function off(event, callback) {
    const set = _wsEventListeners.get(event);
    if (set) set.delete(callback);
  }

  /**
   * Emit a WebSocket event to all registered listeners.
   * @private
   * @param {string} event
   * @param {*} params
   */
  function _emitWsEvent(event, params) {
    const set = _wsEventListeners.get(event);
    if (set) {
      for (const cb of set) {
        try { cb(params); } catch (e) { console.error('[api] WS event error:', e); }
      }
    }
  }

  /**
   * Send a JSON-RPC message through the first active WebSocket connection.
   * If a URL is provided, sends through that specific connection.
   *
   * @param {string} method - JSON-RPC method name
   * @param {Object} [params]
   * @param {number} [id] - Request ID (omit for notifications)
   * @param {string} [url] - Specific connection URL
   * @returns {boolean}
   */
  function send(method, params = {}, id, url) {
    const msg = {
      jsonrpc: '2.0',
      method,
      params,
    };
    if (id !== undefined) msg.id = id;

    if (url) {
      const conn = _wsConnections.get(url);
      if (conn) return conn.send(msg);
      return false;
    }

    // Send on the first active connection
    for (const conn of _wsConnections.values()) {
      if (conn.connected) return conn.send(msg);
    }
    console.warn('[api] No active WebSocket connection to send on');
    return false;
  }

  /* ── SSE Support ──────────────────────────────────────────────────────── */

  /**
   * Open a Server-Sent Events stream.
   *
   * @param {string} url - Full URL for the SSE endpoint
   * @param {Object} [sseOptions]
   * @param {Object} [sseOptions.eventHandlers] - { eventName: handler }
   * @returns {SSEConnection}
   */
  function stream(url, sseOptions = {}) {
    const existing = _sseConnections.get(url);
    if (existing) return existing;

    const conn = new SSEConnection(url, sseOptions);
    _sseConnections.set(url, conn);
    return conn;
  }

  /* ── Cleanup ──────────────────────────────────────────────────────────── */

  /**
   * Close all WebSocket and SSE connections, clear pending requests.
   */
  function destroy() {
    for (const conn of _wsConnections.values()) {
      conn.close();
    }
    _wsConnections.clear();
    for (const conn of _sseConnections.values()) {
      conn.close();
    }
    _sseConnections.clear();
    _dedup.clear();
    _wsEventListeners.clear();
  }

  /* ── Return Public API ────────────────────────────────────────────────── */

  return {
    // HTTP methods
    get,
    post,
    put,
    del,
    
    // Interceptors
    onRequest,
    onResponse,
    
    // WebSocket
    connect,
    on,
    off,
    send,
    
    // SSE
    stream,
    
    // Lifecycle
    destroy,

    // Expose internals for testing / advanced use
    _getBaseURL: () => baseURL,
    _getConnections: () => ({
      ws: _wsConnections.size,
      sse: _sseConnections.size,
    }),
  };
}
