/**
 * PropertyEditor — Editable property panel for the selected object.
 *
 * Shows property groups (categories) as defined by the CAD property
 * system.  Supports float (number input), int (number input, step=1),
 * string (text input), bool (checkbox), and color (simple text).
 *
 * An "Apply" button sends the modified properties back to the server
 * via command.execute.
 */

// Which property types get which input widget
const INPUT_TYPE_MAP = {
  float:  'number',
  int:    'number',
  string: 'text',
  bool:   'checkbox',
  color:  'text',
  enum:   'select',
};

export class PropertyEditor {
  /**
   * @param {HTMLElement} container - The #property-editor element.
   * @param {import('../client.js').RpcClient} client
   * @param {import('../store.js').CadStore} store
   */
  constructor(container, client, store) {
    this.container = container;
    this.client = client;
    this.store = store;

    /** @type {object|null} Currently displayed object data */
    this._currentObject = null;

    /** @type {Array<{name: string, el: HTMLElement, getValue: function}>} */
    this._fields = [];

    this._build();
    this._subscribe();
  }

  // ── Build ─────────────────────────────────────────────────────────

  _build() {
    this.container.innerHTML = '';
    this._formEl = document.createElement('div');
    this._formEl.id = 'prop-form';
    this.container.appendChild(this._formEl);

    this._showEmpty();
  }

  // ── Store Subscription ────────────────────────────────────────────

  _subscribe() {
    this._unsub = this.store.subscribe(() => this._onStoreChange());
  }

  _onStoreChange() {
    const obj = this.store.getSelectedObject();
    if (obj) {
      this.showObject(obj);
    } else {
      this.clear();
    }
  }

  // ── Display ───────────────────────────────────────────────────────

  /**
   * Show the properties of an object.
   * @param {object} objData - Object data from store (with .properties).
   */
  showObject(objData) {
    if (!objData) {
      this.clear();
      return;
    }

    this._currentObject = objData;
    this._fields = [];
    this._formEl.innerHTML = '';

    // Object name / type header
    const header = document.createElement('div');
    header.style.cssText = 'padding: 4px 0 8px; font-size: 13px; font-weight: 600; color: #e0e0f0;';
    header.textContent = `${objData.name || objData.label || 'Unnamed'}  (${objData.type || '?'})`;
    this._formEl.appendChild(header);

    // Group properties by category
    const props = objData.properties || {};
    const grouped = {};

    for (const [propName, propData] of Object.entries(props)) {
      const cat = propData.category || 'General';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push({ name: propName, ...propData });
    }

    // Render each category
    for (const [category, catProps] of Object.entries(grouped)) {
      this._renderCategory(category, catProps);
    }

    // Apply button
    const applyBtn = document.createElement('button');
    applyBtn.className = 'prop-apply-btn';
    applyBtn.textContent = 'Apply Changes';
    applyBtn.addEventListener('click', () => this.applyChanges());
    this._formEl.appendChild(applyBtn);
  }

  /**
   * Render a property category section.
   * @param {string} category
   * @param {Array<object>} catProps
   */
  _renderCategory(category, catProps) {
    const section = document.createElement('div');
    section.style.marginBottom = '8px';

    const header = document.createElement('div');
    header.className = 'prop-header';
    header.textContent = category;
    section.appendChild(header);

    for (const prop of catProps) {
      // Skip non-visible properties
      if (prop.visible === false) continue;

      const row = document.createElement('div');
      row.className = 'prop-row';

      // Label
      const label = document.createElement('span');
      label.className = 'prop-label';
      label.textContent = prop.name;
      label.title = prop.description || prop.name;
      row.appendChild(label);

      // Input widget
      const input = this._createInput(prop);
      row.appendChild(input);

      // Unit
      if (prop.unit) {
        const unitEl = document.createElement('span');
        unitEl.className = 'prop-unit';
        unitEl.textContent = prop.unit;
        row.appendChild(unitEl);
      }

      // Store field reference for applyChanges()
      this._fields.push({
        name: prop.name,
        el: input,
        getValue: () => this._getInputValue(input, prop.type),
      });

      section.appendChild(row);
    }

    this._formEl.appendChild(section);
  }

  /**
   * Create appropriate input widget for a property.
   * @param {object} propData
   * @returns {HTMLElement}
   */
  _createInput(propData) {
    const type = propData.type || 'float';
    const value = propData.value;
    const htmlType = INPUT_TYPE_MAP[type] || 'text';
    const readonly = propData.readonly || false;

    if (htmlType === 'checkbox') {
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!value;
      cb.disabled = readonly;
      cb.className = 'prop-input';
      return cb;
    }

    if (htmlType === 'select') {
      const sel = document.createElement('select');
      sel.className = 'prop-input';
      sel.disabled = readonly;
      if (propData.choices && Array.isArray(propData.choices)) {
        for (const [label, val] of propData.choices) {
          const opt = document.createElement('option');
          opt.value = val;
          opt.textContent = label;
          if (val === value) opt.selected = true;
          sel.appendChild(opt);
        }
      }
      return sel;
    }

    // Default: text/number input
    const input = document.createElement('input');
    input.className = 'prop-input';
    input.type = htmlType;
    input.disabled = readonly;

    if (type === 'int') {
      input.step = '1';
    } else if (type === 'float') {
      input.step = '0.1';
    }

    input.value = value !== null && value !== undefined ? String(value) : '';
    input.placeholder = propData.default !== null && propData.default !== undefined
      ? String(propData.default) : '';

    return input;
  }

  /**
   * Read the current value from an input widget.
   * @param {HTMLElement} input
   * @param {string} type
   * @returns {*}
   */
  _getInputValue(input, type) {
    if (input.type === 'checkbox') return input.checked;
    if (input.tagName === 'SELECT') return input.value;

    const raw = input.value;
    if (type === 'float') {
      const n = parseFloat(raw);
      return isNaN(n) ? 0 : n;
    }
    if (type === 'int') {
      const n = parseInt(raw, 10);
      return isNaN(n) ? 0 : n;
    }
    return raw;
  }

  /** Hide the property form. */
  clear() {
    this._currentObject = null;
    this._fields = [];
    this._showEmpty();
  }

  _showEmpty() {
    this._formEl.innerHTML = '';
    const empty = document.createElement('div');
    empty.className = 'prop-empty';
    empty.textContent = 'No object selected';
    this._formEl.appendChild(empty);
  }

  // ── Apply ─────────────────────────────────────────────────────────

  /**
   * Collect changed properties and send them to the server.
   */
  async applyChanges() {
    if (!this._currentObject) return;

    const docId = this.store.docId;
    if (!docId) return;

    const updatedProps = {};
    for (const field of this._fields) {
      const newValue = field.getValue();
      const propData = (this._currentObject.properties || {})[field.name];
      // Always send the full set; the server diffs
      if (propData) {
        // Send as a plain value (not the full property dict)
        updatedProps[field.name] = newValue;
      }
    }

    if (Object.keys(updatedProps).length === 0) return;

    try {
      await this.client.call('command.execute', {
        doc_id: docId,
        name: 'modify_properties',
        kwargs: {
          uid: this._currentObject.uid,
          properties: updatedProps,
        },
      });
      this._showToast('Properties updated', 'success');
    } catch (err) {
      this._showToast(`Update failed: ${err.message}`, 'error');
      console.error('Property update error:', err);
    }
  }

  _showToast(msg, type) {
    // Dispatch a custom event for the main app to pick up
    this.container.dispatchEvent(new CustomEvent('toast', {
      bubbles: true,
      detail: { message: msg, type },
    }));
  }

  /**
   * Clean up.
   */
  dispose() {
    if (this._unsub) this._unsub();
  }
}
