/**
 * CameraSync — Bidirectional camera state between frontend and server.
 *
 * Periodically polls the Three.js OrbitControls camera and sends its
 * state to the server.  When the server sends a camera update, applies
 * it to the local camera.
 *
 * The camera model mirrors Fiona's Camera class:
 *   position: [x, y, z]  (default [50, 50, 100])
 *   target:   [x, y, z]  (default [0, 0, 0])
 *   up:       [0, 0, 1]  (Z-up, constant)
 */

export class CameraSync {
  /**
   * @param {import('three').PerspectiveCamera} camera
   * @param {import('three').OrbitControls} controls
   * @param {import('../client.js').RpcClient} client
   * @param {object} [options]
   * @param {number} [options.syncInterval=1000] - ms between camera polls
   * @param {boolean} [options.sendToServer=true]
   * @param {boolean} [options.receiveFromServer=true]
   */
  constructor(camera, controls, client, options = {}) {
    this.camera = camera;
    this.controls = controls;
    this.client = client;
    this.syncInterval = options.syncInterval || 1000;
    this.sendToServer = options.sendToServer !== false;
    this.receiveFromServer = options.receiveFromServer !== false;

    /** @type {number|null} */
    this._timerId = null;

    /** @type {number} Last known hash of camera state (avoid redundant sends) */
    this._lastHash = 0;

    // Subscribe to server camera events
    this._unsub = null;
  }

  // ── Lifecycle ────────────────────────────────────────────────────

  /** Start periodic camera sync. */
  start() {
    if (this.receiveFromServer) {
      this._unsub = this.client.on('camera_updated', (payload) => {
        this.applyCameraState(payload);
      });
    }

    if (this.sendToServer) {
      this._poll();
    }
  }

  /** Stop periodic camera sync. */
  stop() {
    if (this._timerId !== null) {
      clearTimeout(this._timerId);
      this._timerId = null;
    }
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
  }

  // ── Outgoing: local → server ─────────────────────────────────────

  _poll() {
    // Send current camera state to server
    const state = this.getCameraState();
    const hash = CameraSync._hashState(state);

    if (hash !== this._lastHash) {
      this._lastHash = hash;
      this.client.notify('camera_update', state);
    }

    this._timerId = setTimeout(() => this._poll(), this.syncInterval);
  }

  /**
   * Serialize the current camera/controls state.
   * @returns {{position: number[], target: number[]}}
   */
  getCameraState() {
    return {
      position: [
        this.camera.position.x,
        this.camera.position.y,
        this.camera.position.z,
      ],
      target: [
        this.controls.target.x,
        this.controls.target.y,
        this.controls.target.z,
      ],
    };
  }

  // ── Incoming: server → local ─────────────────────────────────────

  /**
   * Apply a camera state received from the server.
   * @param {{position: number[], target: number[]}} state
   */
  applyCameraState(state) {
    if (!state) return;

    if (state.position && state.position.length === 3) {
      this.camera.position.set(state.position[0], state.position[1], state.position[2]);
    }
    if (state.target && state.target.length === 3) {
      this.controls.target.set(state.target[0], state.target[1], state.target[2]);
    }
    this.controls.update();

    // Update hash to avoid echo
    this._lastHash = CameraSync._hashState(this.getCameraState());
  }

  /**
   * Force-send the current camera state immediately.
   */
  syncNow() {
    this._lastHash = 0;
    const state = this.getCameraState();
    this.client.notify('camera_update', state);
  }

  // ── Utility ──────────────────────────────────────────────────────

  /**
   * Simple hash of camera state to detect changes.
   * @param {{position: number[], target: number[]}} state
   * @returns {number}
   */
  static _hashState(state) {
    let h = 0;
    const str = `${state.position.join(',')}|${state.target.join(',')}`;
    for (let i = 0; i < str.length; i++) {
      const c = str.charCodeAt(i);
      h = ((h << 5) - h) + c;
      h |= 0;
    }
    return h;
  }
}
