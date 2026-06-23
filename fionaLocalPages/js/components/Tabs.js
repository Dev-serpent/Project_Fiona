/* ==========================================================================
   Tabs.js — Tab Navigation Component
   ==========================================================================
   Factory function returning a tab component with horizontal and vertical
   variants, closable tabs, active underline animation, badge counts,
   and optional drag-reorder support.

   Usage:
     import { createTabs } from './Tabs.js';

     const tabs = createTabs('#my-tabs', [
       { id: 'chat',    label: 'Chat',    icon: 'message', badge: 3 },
       { id: 'agents',  label: 'Agents',  icon: 'bot',     closable: true },
       { id: 'settings', label: 'Settings', icon: 'gear',   closable: true },
     ], 'chat', (tabId) => console.log('Tab selected:', tabId));

     // Later
     tabs.addTab({ id: 'new', label: 'New Tab' });
     tabs.removeTab('settings');
     tabs.activate('agents');
     tabs.destroy();
   ========================================================================== */

import { html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  tabs: 'c-tabs',
  tabsVertical: 'c-tabs--vertical',
  pills: 'c-tabs--pills',
  tab: 'c-tab',
  tabActive: 'c-tab--active',
  tabIcon: 'c-tab__icon',
  tabLabel: '',
  tabCount: 'c-tab__count',
};

/**
 * @typedef {Object} TabDef
 * @property {string} id - Unique tab identifier
 * @property {string} label - Tab display text
 * @property {string} [icon] - Icon key from ICONS
 * @property {number} [badge] - Optional badge count
 * @property {boolean} [closable=false] - Show close button
 */

/**
 * Create a tab component.
 *
 * @param {string|Element} container - CSS selector or element
 * @param {TabDef[]} tabs - Array of tab definitions
 * @param {string} [activeTab] - ID of initially active tab
 * @param {Function} [onChange] - Called with (tabId) when selection changes
 * @param {Object} [options]
 * @param {'horizontal'|'vertical'} [options.direction='horizontal']
 * @param {boolean} [options.pills=false] - Use pill-style tabs
 * @param {boolean} [options.draggable=false] - Enable drag reorder
 * @returns {TabsAPI}
 */
export function createTabs(container, tabs, activeTab, onChange, options = {}) {
  /** @type {Element} */
  let _container = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (!_container) {
    console.error('[Tabs] Container not found:', container);
    return null;
  }

  /** @type {TabDef[]} Internal tab data */
  let _tabs = [...tabs];

  /** @type {string|null} Active tab ID */
  let _activeId = activeTab || (tabs.length > 0 ? tabs[0].id : null);

  /** @type {Function|null} */
  let _onChange = onChange || null;

  /** @type {Object} Options */
  const _opts = {
    direction: options.direction || 'horizontal',
    pills: options.pills || false,
    draggable: options.draggable || false,
  };

  /** @type {boolean} */
  let _destroyed = false;

  /* ── Render ──────────────────────────────────────────────────────────── */

  /**
   * Render the tab bar.
   * @private
   */
  function _render() {
    if (_destroyed) return;

    const directionClass = _opts.direction === 'vertical' ? CSS.tabsVertical : '';
    const pillsClass = _opts.pills ? CSS.pills : '';

    _container.innerHTML = html`
      <div class="${CSS.tabs} ${directionClass} ${pillsClass}" role="tablist">
        ${_tabs.map((tab) => {
          const isActive = tab.id === _activeId;
          return html`
            <div class="${CSS.tab} ${isActive ? CSS.tabActive : ''}"
                 role="tab"
                 aria-selected="${isActive ? 'true' : 'false'}"
                 data-tab-id="${tab.id}"
                 draggable="${_opts.draggable ? 'true' : 'false'}">
              ${tab.icon ? html`<span class="${CSS.tabIcon}">${ICONS[tab.icon] || ''}</span>` : ''}
              <span>${tab.label}</span>
              ${tab.badge != null ? html`<span class="${CSS.tabCount}">${tab.badge}</span>` : ''}
              ${tab.closable ? html`
                <span class="c-tab__close" data-tab-close="${tab.id}"
                      style="display: inline-flex; align-items: center; justify-content: center;
                             width: 16px; height: 16px; border-radius: 4px; cursor: pointer;
                             margin-left: 4px; color: var(--text-muted);"
                      title="Close ${tab.label}">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="2" width="12" height="12"
                       stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </span>
              ` : ''}
            </div>
          `;
        })}
      </div>
    `;

    _bindEvents();
  }

  /* ── Events ──────────────────────────────────────────────────────────── */

  /**
   * Bind tab interaction events.
   * @private
   */
  function _bindEvents() {
    // Tab click
    _container.querySelectorAll('[data-tab-id]').forEach((el) => {
      el.addEventListener('click', () => {
        const id = el.dataset.tabId;
        if (id && id !== _activeId) {
          activate(id);
        }
      });
    });

    // Close button click
    _container.querySelectorAll('[data-tab-close]').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = el.dataset.tabClose;
        if (id) {
          removeTab(id);
        }
      });
    });

    // Drag reorder
    if (_opts.draggable) {
      _setupDragReorder();
    }
  }

  /* ── Drag Reorder ────────────────────────────────────────────────────── */

  /**
   * Set up drag-and-drop tab reordering.
   * @private
   */
  function _setupDragReorder() {
    let dragEl = null;

    _container.addEventListener('dragstart', (e) => {
      const tab = e.target.closest('[data-tab-id]');
      if (!tab) return;
      dragEl = tab;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', tab.dataset.tabId);
      tab.style.opacity = '0.5';
    });

    _container.addEventListener('dragend', (e) => {
      const tab = e.target.closest('[data-tab-id]');
      if (tab) tab.style.opacity = '';
      dragEl = null;
    });

    _container.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const target = e.target.closest('[data-tab-id]');
      if (!target || target === dragEl) return;

      const rect = target.getBoundingClientRect();
      const mid = _opts.direction === 'vertical'
        ? rect.top + rect.height / 2
        : rect.left + rect.width / 2;
      const pos = _opts.direction === 'vertical' ? e.clientY : e.clientX;

      if (pos < mid) {
        target.parentNode.insertBefore(dragEl, target);
      } else {
        target.parentNode.insertBefore(dragEl, target.nextSibling);
      }
    });

    _container.addEventListener('drop', (e) => {
      e.preventDefault();
      // Re-sync _tabs from DOM order
      const tabEls = _container.querySelectorAll('[data-tab-id]');
      const newOrder = Array.from(tabEls).map((el) => el.dataset.tabId);
      _tabs.sort((a, b) => newOrder.indexOf(a.id) - newOrder.indexOf(b.id));
    });
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Activate a tab by ID.
   * @param {string} id
   */
  function activate(id) {
    if (_destroyed) return;
    if (id === _activeId) return;
    if (!_tabs.find((t) => t.id === id)) return;

    _activeId = id;
    _renderTabActiveState();

    if (_onChange) {
      _onChange(id);
    }
  }

  /**
   * Efficiently update just the active class on tabs without full re-render.
   * @private
   */
  function _renderTabActiveState() {
    _container.querySelectorAll('[data-tab-id]').forEach((el) => {
      const isActive = el.dataset.tabId === _activeId;
      el.classList.toggle(CSS.tabActive, isActive);
      el.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
  }

  /**
   * Add a new tab.
   * @param {TabDef} tabDef
   * @param {boolean} [activateNew=false] - Whether to activate the new tab
   */
  function addTab(tabDef, activateNew = false) {
    if (_destroyed) return;
    // Don't add duplicate IDs
    if (_tabs.find((t) => t.id === tabDef.id)) return;
    _tabs.push({ ...tabDef });
    _render();
    if (activateNew) {
      _activeId = tabDef.id;
      _renderTabActiveState();
      if (_onChange) _onChange(tabDef.id);
    }
  }

  /**
   * Remove a tab by ID.
   * @param {string} id
   */
  function removeTab(id) {
    if (_destroyed) return;
    const idx = _tabs.findIndex((t) => t.id === id);
    if (idx === -1) return;

    _tabs.splice(idx, 1);

    // If active tab was removed, activate the nearest tab
    if (_activeId === id) {
      const newIdx = Math.min(idx, _tabs.length - 1);
      _activeId = _tabs.length > 0 ? _tabs[newIdx].id : null;
      if (_onChange) _onChange(_activeId);
    }

    _render();
  }

  /**
   * Update a tab's properties.
   * @param {string} id
   * @param {Partial<TabDef>} updates
   */
  function updateTab(id, updates) {
    if (_destroyed) return;
    const tab = _tabs.find((t) => t.id === id);
    if (!tab) return;
    Object.assign(tab, updates);
    _render();
  }

  /**
   * Get the currently active tab ID.
   * @returns {string|null}
   */
  function getActiveTab() {
    return _activeId;
  }

  /**
   * Get all tabs.
   * @returns {TabDef[]}
   */
  function getTabs() {
    return [..._tabs];
  }

  /**
   * Replace all tabs.
   * @param {TabDef[]} newTabs
   * @param {string} [activateId] - Tab ID to activate
   */
  function setTabs(newTabs, activateId) {
    if (_destroyed) return;
    _tabs = [...newTabs];
    if (activateId && _tabs.find((t) => t.id === activateId)) {
      _activeId = activateId;
    } else if (_tabs.length > 0 && !_tabs.find((t) => t.id === _activeId)) {
      _activeId = _tabs[0].id;
    }
    _render();
  }

  /**
   * Update the onChange callback.
   * @param {Function} callback
   */
  function onChange(callback) {
    _onChange = callback;
  }

  /**
   * Remove the component from the DOM.
   */
  function destroy() {
    _destroyed = true;
    _container.innerHTML = '';
    _tabs = [];
    _activeId = null;
    _onChange = null;
  }

  // Initial render
  _render();

  return {
    activate,
    addTab,
    removeTab,
    updateTab,
    getActiveTab,
    getTabs,
    setTabs,
    onChange,
    destroy,
  };
}

/**
 * @typedef {Object} TabsAPI
 * @property {(id: string) => void} activate
 * @property {(tabDef: TabDef, activateNew?: boolean) => void} addTab
 * @property {(id: string) => void} removeTab
 * @property {(id: string, updates: Partial<TabDef>) => void} updateTab
 * @property {() => string|null} getActiveTab
 * @property {() => TabDef[]} getTabs
 * @property {(newTabs: TabDef[], activateId?: string) => void} setTabs
 * @property {(callback: Function) => void} onChange
 * @property {() => void} destroy
 */

export default createTabs;
