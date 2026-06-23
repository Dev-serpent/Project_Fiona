/**
 * Toolbar — Top toolbar with File, Create, Actions, and View buttons.
 *
 * Each button triggers an RPC call or a store/scene operation.
 * The create buttons show a dropdown with primitive types.
 */

export class Toolbar {
  /**
   * @param {HTMLElement} container - The #toolbar element.
   * @param {import('../client.js').RpcClient} client
   * @param {import('../store.js').CadStore} store
   * @param {import('../scene/SceneManager.js').SceneManager} sceneManager
   * @param {object} [options]
   * @param {function} [options.onToast] - Callback for showing toast messages.
   */
  constructor(container, client, store, sceneManager, options = {}) {
    this.container = container;
    this.client = client;
    this.store = store;
    this.sceneManager = sceneManager;
    this.onToast = options.onToast || ((msg, type) => console.log(msg));

    /** @type {HTMLElement|null} Currently open dropdown */
    this._activeDropdown = null;

    this._build();
    this._bindGlobalClose();
  }

  // ── Build ─────────────────────────────────────────────────────────

  _build() {
    this.container.innerHTML = '';

    this._addGroup('File', [
      { label: 'New', action: () => this._fileNew(), primary: true },
      { label: 'Open', action: () => this._fileOpen() },
      { label: 'Save', action: () => this._fileSave(), primary: true },
    ]);

    this._addCreateDropdown();

    this._addGroup('Actions', [
      { label: 'Undo', action: () => this._undo(), primary: true },
      { label: 'Redo', action: () => this._redo(), primary: true },
      { label: 'Recompute', action: () => this._recompute() },
    ]);

    this._addGroup('View', [
      { label: 'Grid', action: () => this._toggleGrid() },
      { label: 'Reset View', action: () => this._resetView() },
    ]);
  }

  /**
   * Add a labeled group of buttons.
   * @param {string} label
   * @param {Array<{label: string, action: function, primary?: boolean}>} buttons
   */
  _addGroup(label, buttons) {
    const group = document.createElement('div');
    group.className = 'toolbar-group';

    const labelEl = document.createElement('span');
    labelEl.className = 'toolbar-label';
    labelEl.textContent = label;
    group.appendChild(labelEl);

    for (const btn of buttons) {
      const el = document.createElement('button');
      el.className = 'toolbar-btn' + (btn.primary ? ' primary' : '');
      el.textContent = btn.label;
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        btn.action();
      });
      group.appendChild(el);
    }

    this.container.appendChild(group);
  }

  _addCreateDropdown() {
    const group = document.createElement('div');
    group.className = 'toolbar-group';

    const labelEl = document.createElement('span');
    labelEl.className = 'toolbar-label';
    labelEl.textContent = 'Create';
    group.appendChild(labelEl);

    const dropdown = document.createElement('div');
    dropdown.className = 'dropdown';

    const trigger = document.createElement('button');
    trigger.className = 'toolbar-btn primary';
    trigger.textContent = '▼ Primitive';
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this._toggleDropdown(dropdown);
    });
    dropdown.appendChild(trigger);

    const content = document.createElement('div');
    content.className = 'dropdown-content';

    const types = ['Box', 'Cylinder', 'Sphere', 'Cone', 'Torus'];
    for (const type of types) {
      const item = document.createElement('button');
      item.className = 'dropdown-item';
      item.textContent = type;
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        this._closeDropdown();
        this.createPrimitive(type);
      });
      content.appendChild(item);
    }

    dropdown.appendChild(content);
    group.appendChild(dropdown);
    this.container.appendChild(group);
    this._createDropdownEl = dropdown;
  }

  // ── Dropdown Management ───────────────────────────────────────────

  _toggleDropdown(dropdown) {
    if (this._activeDropdown === dropdown) {
      this._closeDropdown();
    } else {
      this._closeDropdown();
      const content = dropdown.querySelector('.dropdown-content');
      if (content) content.classList.add('show');
      this._activeDropdown = dropdown;
    }
  }

  _closeDropdown() {
    if (this._activeDropdown) {
      const content = this._activeDropdown.querySelector('.dropdown-content');
      if (content) content.classList.remove('show');
      this._activeDropdown = null;
    }
  }

  _bindGlobalClose() {
    document.addEventListener('click', () => this._closeDropdown());
  }

  // ── Actions ───────────────────────────────────────────────────────

  /**
   * Create a primitive via RPC.
   * @param {string} type - One of Box, Cylinder, Sphere, Cone, Torus.
   */
  async createPrimitive(type) {
    const defaults = Toolbar.getDefaultProps(type);
    const docId = this.store.docId;
    if (!docId) {
      this.onToast('No document open. Create or open one first.', 'error');
      return;
    }

    try {
      const result = await this.client.call('command.execute', {
        doc_id: docId,
        name: `create_${type.toLowerCase()}`,
        kwargs: defaults,
      });
      this.onToast(`Created ${type}`, 'success');
      return result;
    } catch (err) {
      this.onToast(`Failed to create ${type}: ${err.message}`, 'error');
      console.error('Create primitive error:', err);
    }
  }

  async _fileNew() {
    try {
      const result = await this.client.call('document.create', { name: 'Untitled' });
      if (result && result.doc_id) {
        this.store.docId = result.doc_id;
      }
      this.onToast('New document created', 'success');
    } catch (err) {
      this.onToast(`Failed to create document: ${err.message}`, 'error');
    }
  }

  async _fileOpen() {
    // For now, the server handles file dialogs or this opens a prompt
    const path = prompt('Enter file path to open:');
    if (!path) return;
    try {
      const result = await this.client.call('document.open', { path });
      if (result && result.doc_id) {
        this.store.docId = result.doc_id;
      }
      this.onToast(`Opened: ${path}`, 'success');
    } catch (err) {
      this.onToast(`Failed to open: ${err.message}`, 'error');
    }
  }

  async _fileSave() {
    const docId = this.store.docId;
    if (!docId) {
      this.onToast('No document open', 'error');
      return;
    }
    try {
      await this.client.call('document.save', { doc_id: docId });
      this.onToast('Document saved', 'success');
    } catch (err) {
      this.onToast(`Failed to save: ${err.message}`, 'error');
    }
  }

  async _undo() {
    const docId = this.store.docId;
    if (!docId) return;
    try {
      await this.client.call('command.undo', { doc_id: docId });
    } catch (err) {
      this.onToast(`Undo failed: ${err.message}`, 'error');
    }
  }

  async _redo() {
    const docId = this.store.docId;
    if (!docId) return;
    try {
      await this.client.call('command.redo', { doc_id: docId });
    } catch (err) {
      this.onToast(`Redo failed: ${err.message}`, 'error');
    }
  }

  async _recompute() {
    const docId = this.store.docId;
    if (!docId) return;
    try {
      await this.client.call('command.execute', {
        doc_id: docId,
        name: 'recompute',
        kwargs: {},
      });
      this.onToast('Recomputed', 'success');
    } catch (err) {
      this.onToast(`Recompute failed: ${err.message}`, 'error');
    }
  }

  _toggleGrid() {
    const scene = this.sceneManager;
    scene.showGrid = !scene.showGrid;
    this.onToast(`Grid ${scene.showGrid ? 'on' : 'off'}`, 'info');
  }

  _resetView() {
    this.sceneManager.resetCamera();
    this.onToast('View reset', 'info');
  }

  // ── Default Properties ────────────────────────────────────────────

  /**
   * Get default creation properties for a primitive type.
   * Matches Fiona's primitives.py defaults.
   * @param {string} type
   * @returns {object}
   */
  static getDefaultProps(type) {
    const defaults = {
      Box:      { width: 10, height: 10, depth: 10, x: 0, y: 0, z: 0 },
      Cylinder: { radius: 10, height: 25, x: 0, y: 0, z: 0 },
      Sphere:   { radius: 10, x: 0, y: 0, z: 0 },
      Cone:     { radius: 10, height: 25, x: 0, y: 0, z: 0 },
      Torus:    { major_radius: 20, minor_radius: 5, x: 0, y: 0, z: 0 },
    };
    return defaults[type] || {};
  }
}
