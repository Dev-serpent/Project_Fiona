/**
 * ProjectTree — Scrollable list of document objects.
 *
 * Shows all objects in the current document.  Click to select,
 * double-click to focus.  A search/filter box at the top allows
 * narrowing the list.
 *
 * Events emitted:
 *   'select' (uid)  — when an item is clicked
 *   'delete' (uid)  — when Delete key pressed on selected item
 */

export class ProjectTree {
  /**
   * @param {HTMLElement} container - The #project-tree element.
   * @param {import('../client.js').RpcClient} client
   * @param {import('../store.js').CadStore} store
   */
  constructor(container, client, store) {
    this.container = container;
    this.client = client;
    this.store = store;

    /** @type {Object<string, HTMLElement>} uid -> DOM element */
    this._elements = {};

    /** @type {Array<function>} External event listeners */
    this._eventListeners = { select: [], delete: [] };

    this._build();
    this._subscribe();
  }

  /**
   * Register a callback for tree events.
   * @param {'select'|'delete'} event
   * @param {function} callback
   * @returns {function} Unsubscribe function.
   */
  on(event, callback) {
    if (!this._eventListeners[event]) return () => {};
    this._eventListeners[event].push(callback);
    return () => {
      const arr = this._eventListeners[event];
      const idx = arr.indexOf(callback);
      if (idx !== -1) arr.splice(idx, 1);
    };
  }

  // ── Build ─────────────────────────────────────────────────────────

  _build() {
    this.container.innerHTML = '';

    // Search box
    const search = document.createElement('input');
    search.id = 'tree-search';
    search.type = 'text';
    search.placeholder = 'Filter objects...';
    search.addEventListener('input', () => this._filter(search.value));
    this.container.appendChild(search);

    // Scrollable list
    this._listEl = document.createElement('div');
    this._listEl.style.flex = '1';
    this._listEl.style.overflowY = 'auto';
    this.container.appendChild(this._listEl);

    // Keyboard bindings
    this.container.addEventListener('keydown', (e) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (this.store.selection.size > 0) {
          const uid = this.store.selection.values().next().value;
          this._emit('delete', uid);
        }
      }
    });
  }

  // ── Store Subscription ────────────────────────────────────────────

  _subscribe() {
    this._unsub = this.store.subscribe(() => this._onStoreChange());
  }

  _onStoreChange() {
    this.refresh();
  }

  // ── Refresh ───────────────────────────────────────────────────────

  /**
   * Rebuild the tree from the store's current document state.
   * Preserves scroll position.
   */
  refresh() {
    const objects = this.store.objects;
    const selectedUid = this.store.selection.size > 0
      ? this.store.selection.values().next().value
      : null;

    // Store current filter value
    const filterValue = this.container.querySelector('#tree-search')?.value || '';

    // Rebuild list
    this._listEl.innerHTML = '';
    this._elements = {};

    if (!objects || objects.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'tree-empty';
      empty.textContent = 'No objects';
      this._listEl.appendChild(empty);
      return;
    }

    for (const obj of objects) {
      const el = this._createItem(obj, selectedUid === obj.uid);
      this._elements[obj.uid] = el;
      this._listEl.appendChild(el);
    }

    // Apply current filter
    if (filterValue) this._filter(filterValue);
  }

  /**
   * Create a single tree item element.
   * @param {object} obj - Object data from store.
   * @param {boolean} selected - Whether this item is currently selected.
   * @returns {HTMLElement}
   */
  _createItem(obj, selected) {
    const el = document.createElement('div');
    el.className = 'tree-item' + (selected ? ' selected' : '');
    el.dataset.uid = obj.uid;
    el.tabIndex = 0;

    // Icon (using a simple symbol based on type)
    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = this._getTypeIcon(obj.type);
    el.appendChild(icon);

    // Name label
    const label = document.createElement('span');
    label.className = 'tree-label';
    label.textContent = obj.name || obj.label || 'Unnamed';
    el.appendChild(label);

    // Type badge
    const typeBadge = document.createElement('span');
    typeBadge.className = 'tree-type';
    typeBadge.textContent = obj.type || '?';
    el.appendChild(typeBadge);

    // Click to select
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      this.store.selectObject(obj.uid);
      this._emit('select', obj.uid);
    });

    // Double-click to focus (reset camera on object)
    el.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      this._emit('focus', obj.uid);
    });

    return el;
  }

  // ── Filter ────────────────────────────────────────────────────────

  /**
   * Filter tree items by text.
   * @param {string} query
   */
  _filter(query) {
    const lower = query.toLowerCase().trim();
    for (const [uid, el] of Object.entries(this._elements)) {
      const label = el.querySelector('.tree-label')?.textContent || '';
      const type = el.querySelector('.tree-type')?.textContent || '';
      const match = !lower || label.toLowerCase().includes(lower) || type.toLowerCase().includes(lower);
      el.style.display = match ? '' : 'none';
    }
  }

  // ── Selection Highlight ───────────────────────────────────────────

  /**
   * Update which item is visually highlighted.
   * @param {string|null} uid
   */
  highlightSelected(uid) {
    for (const [itemUid, el] of Object.entries(this._elements)) {
      el.classList.toggle('selected', itemUid === uid);
    }
  }

  // ── Utility ───────────────────────────────────────────────────────

  /**
   * Get an icon character for a CAD type.
   * @param {string} type
   * @returns {string}
   */
  _getTypeIcon(type) {
    const icons = {
      Box:      '◇',
      Cylinder: '○',
      Sphere:   '●',
      Cone:     '△',
      Torus:    '◎',
      Sketch:   '✎',
      Assembly: '⊞',
      Pad:      '▣',
      Pocket:   '⊟',
      Revolve:  '↻',
      PartInstance: '⊡',
    };
    return icons[type] || '□';
  }

  _emit(event, data) {
    const listeners = this._eventListeners[event];
    if (listeners) {
      for (const cb of listeners) {
        try { cb(data); } catch (err) { console.warn(`Tree event error (${event}):`, err); }
      }
    }
  }

  /**
   * Clean up store subscription.
   */
  dispose() {
    if (this._unsub) this._unsub();
  }
}
