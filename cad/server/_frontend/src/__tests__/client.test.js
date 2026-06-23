/**
 * Tests for RpcClient — JSON-RPC 2.0 over WebSocket.
 *
 * Uses a mock WebSocket to simulate server interactions.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { RpcClient } from '../client.js';

/**
 * Creates a mock WebSocket constructor for testing.
 * Returns an object with { MockWebSocket, lastInstance } so tests
 * can inspect the created WebSocket and simulate server messages.
 */
function createMockWebSocket() {
  const instances = [];
  let openHandler = null;
  let closeHandler = null;
  let messageHandler = null;
  let errorHandler = null;

  class MockWebSocket {
    constructor(url) {
      this.url = url;
      this.readyState = 0; // CONNECTING
      this.inst = instances.length;
      instances.push(this);
    }

    // Simulate server opening the connection
    static simulateOpen() {
      const ws = instances[instances.length - 1];
      if (ws) {
        ws.readyState = 1; // OPEN
        if (ws.onopen) ws.onopen();
      }
    }

    // Simulate server sending a message
    static simulateMessage(data) {
      const ws = instances[instances.length - 1];
      if (ws && ws.onmessage) {
        ws.onmessage({ data: JSON.stringify(data) });
      }
    }

    // Simulate server closing the connection
    static simulateClose(code = 1000, reason = '') {
      const ws = instances[instances.length - 1];
      if (ws) {
        ws.readyState = 3; // CLOSED
        if (ws.onclose) ws.onclose({ code, reason });
      }
    }

    // Simulate server error
    static simulateError(err) {
      const ws = instances[instances.length - 1];
      if (ws && ws.onerror) ws.onerror(err);
    }

    close() {
      this.readyState = 3;
      if (this.onclose) this.onclose({ code: 1000, reason: 'Closed' });
    }

    send(data) {
      this.lastSent = data;
    }

    addEventListener() {}
  }

  MockWebSocket.CONNECTING = 0;
  MockWebSocket.OPEN = 1;
  MockWebSocket.CLOSING = 2;
  MockWebSocket.CLOSED = 3;

  return { MockWebSocket, instances };
}

describe('RpcClient', () => {
  let client;
  let mockWS;

  beforeEach(() => {
    mockWS = createMockWebSocket();
    vi.stubGlobal('WebSocket', mockWS.MockWebSocket);
    client = new RpcClient('ws://test:8765/ws');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // ── Constructor ──────────────────────────────────────────────────

  describe('constructor', () => {
    it('initializes with default state', () => {
      expect(client.url).toBe('ws://test:8765/ws');
      expect(client.ws).toBeNull();
      expect(client.requestId).toBe(0);
      expect(client.pending.size).toBe(0);
      expect(client.listeners.size).toBe(0);
      expect(client.reconnectAttempts).toBe(0);
      expect(client.maxRetries).toBe(10);
      expect(client.isConnected).toBe(false);
    });
  });

  // ── Connection ───────────────────────────────────────────────────

  describe('connect', () => {
    it('creates a WebSocket and resolves on open', async () => {
      const connectPromise = client.connect();
      expect(client.ws).toBeTruthy();
      mockWS.MockWebSocket.simulateOpen();
      await expect(connectPromise).resolves.toBeUndefined();
      expect(client.isConnected).toBe(true);
    });

    it('rejects on WebSocket error', async () => {
      const connectPromise = client.connect();
      mockWS.MockWebSocket.simulateError(new Error('Connection refused'));
      await expect(connectPromise).rejects.toThrow();
    });

    it('resolves immediately if already connected', async () => {
      const connectPromise = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await connectPromise;
      // Second connect should resolve immediately
      await expect(client.connect()).resolves.toBeUndefined();
    });

    it('dispatches connection_open event', async () => {
      const events = [];
      client.on('connection_open', (p) => events.push(p));
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;
      expect(events.length).toBe(1);
    });
  });

  // ── Disconnect ──────────────────────────────────────────────────

  describe('disconnect', () => {
    it('stops reconnection and cleans up', async () => {
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;
      client.disconnect();
      expect(client.isConnected).toBe(false);
      expect(client._shouldReconnect).toBe(false);
    });

    it('rejects all pending requests', async () => {
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;
      // Hijack ws with a minimal mock that has close()
      client.ws = { readyState: 1, send: () => {}, close: () => {} };
      client._isConnected = true;
      const callPromise = client.call('test.method', {});
      client.disconnect();
      await expect(callPromise).rejects.toThrow('Client disconnected');
    });
  });

  // ── RPC Calls ────────────────────────────────────────────────────

  describe('call', () => {
    it('rejects if not connected', async () => {
      await expect(client.call('test', {})).rejects.toThrow('Not connected');
    });

    it('sends a JSON-RPC 2.0 request and resolves with result', async () => {
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      const callPromise = client.call('document.list', { filter: 'all' });
      // Simulate server response
      mockWS.MockWebSocket.simulateMessage({
        jsonrpc: '2.0',
        id: 1,
        result: { documents: ['doc1'] },
      });

      const result = await callPromise;
      expect(result).toEqual({ documents: ['doc1'] });
    });

    it('rejects on RPC error response', async () => {
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      const callPromise = client.call('fail.method', {});
      mockWS.MockWebSocket.simulateMessage({
        jsonrpc: '2.0',
        id: 1,
        error: { message: 'Method not found', code: -32601 },
      });

      await expect(callPromise).rejects.toThrow('Method not found');
    });

    it('rejects on timeout', async () => {
      vi.useFakeTimers();
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      const callPromise = client.call('slow.method', {}, 100);
      vi.advanceTimersByTime(150);
      await expect(callPromise).rejects.toThrow('RPC timeout');
      vi.useRealTimers();
    });

    it('strips stale response (duplicate id)', async () => {
      vi.useFakeTimers();
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      // First call times out
      const p1 = client.call('method', {}, 50);
      vi.advanceTimersByTime(60);
      await expect(p1).rejects.toThrow('RPC timeout');

      // Response arrives late for the timed-out id — should be ignored
      mockWS.MockWebSocket.simulateMessage({
        jsonrpc: '2.0',
        id: 1,
        result: 'late',
      });
      // No crash expected
      vi.useRealTimers();
    });
  });

  // ── Notifications ────────────────────────────────────────────────

  describe('notify', () => {
    it('sends a notification without id', async () => {
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      client.ws.send = vi.fn();
      client.notify('camera_moved', { x: 1 });
      const sent = JSON.parse(client.ws.send.mock.calls[0][0]);
      expect(sent.jsonrpc).toBe('2.0');
      expect(sent.method).toBe('camera_moved');
      expect(sent.id).toBeUndefined();
    });

    it('silently fails when not connected', () => {
      expect(() => client.notify('test', {})).not.toThrow();
    });
  });

  // ── Event Subscriptions ─────────────────────────────────────────

  describe('event subscriptions', () => {
    it('on subscribes and returns unsubscribe function', () => {
      const cb = vi.fn();
      const unsub = client.on('document_updated', cb);
      expect(typeof unsub).toBe('function');
    });

    it('calls registered listeners on server events', async () => {
      const cb = vi.fn();
      client.on('document_updated', cb);

      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      mockWS.MockWebSocket.simulateMessage({
        jsonrpc: '2.0',
        method: 'document_updated',
        params: { document: { name: 'Test' } },
      });

      expect(cb).toHaveBeenCalledWith({ document: { name: 'Test' } });
    });

    it('unsubscribed listener is not called', async () => {
      const cb = vi.fn();
      const unsub = client.on('document_updated', cb);
      unsub();

      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      mockWS.MockWebSocket.simulateMessage({
        jsonrpc: '2.0',
        method: 'document_updated',
        params: {},
      });

      expect(cb).not.toHaveBeenCalled();
    });

    it('once subscribes for a single invocation', async () => {
      const cb = vi.fn();
      client.once('connection_open', cb);

      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      expect(cb).toHaveBeenCalledTimes(1);

      // Second dispatch should not trigger
      mockWS.MockWebSocket.simulateMessage({
        jsonrpc: '2.0',
        method: 'connection_open',
        params: {},
      });
      expect(cb).toHaveBeenCalledTimes(1);
    });
  });

  // ── Reconnection ─────────────────────────────────────────────────

  describe('reconnection', () => {
    it('schedules reconnect on unexpected close', async () => {
      vi.useFakeTimers();
      const reconnectCb = vi.fn();
      client.on('reconnecting', reconnectCb);

      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      mockWS.MockWebSocket.simulateClose(1006, 'Abnormal closure');

      // Should schedule a reconnect
      expect(reconnectCb).toHaveBeenCalled();
      expect(reconnectCb.mock.calls[0][0].attempt).toBe(1);

      vi.useRealTimers();
    });

    it('tracks reconnect attempts and exhausts after maxRetries', () => {
      const exhaustedCb = vi.fn();
      const reconnectingCb = vi.fn();
      client.on('reconnect_exhausted', exhaustedCb);
      client.on('reconnecting', reconnectingCb);
      client.maxRetries = 3;

      // First 3 calls: increments attempts from 0 to 3, dispatches 'reconnecting'
      client._scheduleReconnect();
      expect(reconnectingCb).toHaveBeenCalledTimes(1);
      expect(reconnectingCb.mock.calls[0][0].attempt).toBe(1);
      expect(client.reconnectAttempts).toBe(1);

      client._scheduleReconnect();
      expect(reconnectingCb).toHaveBeenCalledTimes(2);
      expect(reconnectingCb.mock.calls[1][0].attempt).toBe(2);
      expect(client.reconnectAttempts).toBe(2);

      client._scheduleReconnect();
      expect(reconnectingCb).toHaveBeenCalledTimes(3);
      expect(reconnectingCb.mock.calls[2][0].attempt).toBe(3);
      expect(client.reconnectAttempts).toBe(3);

      // Call 4: attempts >= maxRetries (3 >= 3), dispatches exhausted
      client._scheduleReconnect();
      expect(exhaustedCb).toHaveBeenCalledTimes(1);
      expect(exhaustedCb.mock.calls[0][0].attempts).toBe(3);
      expect(client.reconnectAttempts).toBe(3); // not incremented

      // Call 5: still exhausted
      client._scheduleReconnect();
      expect(exhaustedCb).toHaveBeenCalledTimes(2);

      // No additional 'reconnecting' events after exhaustion
      expect(reconnectingCb).toHaveBeenCalledTimes(3);
    });
  });

  // ── Handshake ────────────────────────────────────────────────────

  describe('handshake', () => {
    it('calls handshake method with client info', async () => {
      // We'll test that call() works by verifying the RPC structure
      const origCall = client.call;
      client.call = vi.fn().mockResolvedValue({ server_version: '1.0', protocol: '1.0' });

      const result = await client.handshake();
      expect(result.server_version).toBe('1.0');
      expect(client.call).toHaveBeenCalledWith('handshake', {
        client_name: 'fiona-cad-frontend',
        client_version: '0.1.0',
        protocol_version: '1.0',
        capabilities: ['full_state', 'incremental_updates', 'camera_sync'],
      });

      client.call = origCall;
    });
  });

  // ── Message Routing ──────────────────────────────────────────────

  describe('message routing', () => {
    it('ignores invalid JSON messages', async () => {
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      // Directly invoke onmessage with bad JSON
      const ws = client.ws;
      expect(() => {
        ws.onmessage({ data: 'not json {{{' });
      }).not.toThrow();
    });

    it('ignores unrecognized message shapes', async () => {
      const cp = client.connect();
      mockWS.MockWebSocket.simulateOpen();
      await cp;

      const ws = client.ws;
      expect(() => {
        ws.onmessage({ data: JSON.stringify({ unknown: true }) });
      }).not.toThrow();
    });
  });

  // ── Pending Request Cleanup ──────────────────────────────────────

  describe('_rejectAllPending', () => {
    it('rejects and clears all pending requests', async () => {
      client._isConnected = true;
      client.ws = { readyState: 1, send: () => {} };
      const p1 = client.call('method1', {});
      const p2 = client.call('method2', {});

      client._rejectAllPending(new Error('Shutdown'));

      await expect(p1).rejects.toThrow('Shutdown');
      await expect(p2).rejects.toThrow('Shutdown');
      expect(client.pending.size).toBe(0);
    });
  });
});
