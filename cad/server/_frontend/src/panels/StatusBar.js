/**
 * StatusBar — Bottom status bar showing connection state,
 * object count, mode, and status messages.
 */

export class StatusBar {
  /**
   * @param {HTMLElement} container - The #status-bar element.
   * @param {import('../store.js').CadStore} store
   */
  constructor(container, store) {
    this.container = container;
    this.store = store;

    /** @type {number|null} Timeout ID for temporary messages */
    this._messageTimer = null;

    this._build();
    this._subscribe();
  }

  // ── Build ─────────────────────────────────────────────────────────

  _build() {
    this.container.innerHTML = '';

    // Object count
    this._objCountEl = this._createItem('Objects:', '0');

    // Document name
    this._docNameEl = this._createItem('Document:', '-');

    // Spacer
    const spacer = document.createElement('span');
    spacer.className = 'status-spacer';
    this.container.appendChild(spacer);

    // Connection status
    this._statusEl = document.createElement('span');
    this._statusEl.className = 'status-item';
    this._updateStatusDisplay('disconnected');
    this.container.appendChild(this._statusEl);

    // Mode
    this._modeEl = this._createItem('Mode:', 'Orbit');

    // Status message
    this._messageEl = document.createElement('span');
    this._messageEl.className = 'status-message';
    this._messageEl.textContent = 'Ready';
    this.container.appendChild(this._messageEl);
  }

  /**
   * Create a labeled status item.
   * @param {string} label
   * @param {string} value
   * @returns {HTMLElement}
   */
  _createItem(label, value) {
    const el = document.createElement('span');
    el.className = 'status-item';

    const labelSpan = document.createElement('span');
    labelSpan.className = 'status-label';
    labelSpan.textContent = label;
    el.appendChild(labelSpan);

    const valueSpan = document.createElement('span');
    valueSpan.className = 'status-value';
    valueSpan.textContent = value;
    el.appendChild(valueSpan);

    this.container.appendChild(el);
    return valueSpan;
  }

  // ── Store Subscription ────────────────────────────────────────────

  _subscribe() {
    this._unsub = this.store.subscribe(() => this._refresh());
  }

  // ── Refresh ───────────────────────────────────────────────────────

  /** Refresh from store state. */
  _refresh() {
    this._objCountEl.textContent = String(this.store.objectCount);
    this._docNameEl.textContent = this.store.documentName || '-';
    this._updateStatusDisplay(this.store.status);
  }

  /**
   * Update the connection status indicator.
   * @param {string} status - 'disconnected' | 'connecting' | 'connected' | 'error'
   */
  _updateStatusDisplay(status) {
    const icon = status === 'connected' ? '⬟' : '⬡';
    const cls = status === 'connected' ? 'status-connected' : 'status-disconnected';
    this._statusEl.innerHTML = `<span class="${cls}">${icon}</span> ${status}`;
  }

  // ── Messages ──────────────────────────────────────────────────────

  /**
   * Set a temporary status message.
   * @param {string} msg - Message text.
   * @param {number} [durationMs=5000] - How long to show it (0 = permanent).
   */
  setMessage(msg, durationMs = 5000) {
    if (this._messageTimer) {
      clearTimeout(this._messageTimer);
      this._messageTimer = null;
    }

    this._messageEl.textContent = msg;

    if (durationMs > 0) {
      this._messageTimer = setTimeout(() => {
        this._messageEl.textContent = 'Ready';
        this._messageTimer = null;
      }, durationMs);
    }
  }

  /**
   * Update the mode indicator (Orbit/Pan/Select).
   * @param {string} mode
   */
  setMode(mode) {
    this._modeEl.textContent = mode;
  }

  /**
   * Clean up.
   */
  dispose() {
    if (this._unsub) this._unsub();
    if (this._messageTimer) clearTimeout(this._messageTimer);
  }
}
