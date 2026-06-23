/* ==========================================================================
   TabPanel.js — Tab-Based Panel Container
   ==========================================================================
   Creates a tabbed panel container with tabs at the top and lazy-loaded
   content panels below.  Supports dynamic tab add/remove and content
   that is rendered only when the tab becomes active.

   Usage:
     import { createTabPanel } from './TabPanel.js';

     const panel = createTabPanel('#container', [
       {
         id: 'editor',
         label: 'Editor',
         icon: 'edit',
         render: () => '<div>Editor content</div>',
       },
       {
         id: 'preview',
         label: 'Preview',
         icon: 'eye',
         render: async () => {
           // Lazy load
           const html = await fetch('/preview');
           return html;
         },
       },
     ], {
       activeTab: 'editor',
       closable: true,
     });

     panel.addTab({ id: 'settings', label: 'Settings', render: () => '...' });
     panel.removeTab('preview');
     panel.destroy();
   ========================================================================== */

import { BaseComponent, html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/**
 * @typedef {Object} TabPanelDef
 * @property {string} id - Unique tab ID
 * @property {string} label - Display label
 * @property {string} [icon] - Icon key from ICONS
 * @property {Function|Function} render - () => string | Promise<string>
 *        Called when tab becomes active (for lazy loading).
 * @property {boolean} [closable=false] - Show close button on tab
 * @property {boolean} [lazy=true] - Only render content when tab is active
 */

/**
 * Create a tab panel component.
 *
 * @param {string|Element} container - Container element
 * @param {TabPanelDef[]} tabs - Tab definitions
 * @param {Object} [options]
 * @param {string} [options.activeTab] - Initially active tab ID
 * @param {boolean} [options.closable=false] - Allow tabs to be closed
 * @param {Function} [options.onChange] - (tabId) => void
 * @returns {TabPanelAPI}
 */
export function createTabPanel(container, tabs, options = {}) {
  /** @type {Element} */
  let _container = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (!_container) {
    console.error('[TabPanel] Container not found:', container);
    return null;
  }

  /** @type {TabPanelDef[]} */
  let _tabs = [...tabs];

  /** @type {string|null} */
  let _activeId = options.activeTab || (tabs.length > 0 ? tabs[0].id : null);

  /** @type {boolean} */
  let _closable = options.closable === true;

  /** @type {Function|null} */
  let _onChange = options.onChange || null;

  /** @type {Set<string>} IDs of tabs whose content has been rendered */
  let _renderedTabs = new Set();

  /** @type {boolean} */
  let _destroyed = false;

  /* ── Render ──────────────────────────────────────────────────────────── */

  function _render() {
    if (_destroyed) return;

    _container.innerHTML = html`
      <div style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
        <!-- Tab bar -->
        <div class="c-tabs" style="flex-shrink: 0;">
          ${_tabs.map((tab) => {
            const isActive = tab.id === _activeId;
            return html`
              <div class="c-tab ${isActive ? 'c-tab--active' : ''}"
                   role="tab"
                   aria-selected="${isActive ? 'true' : 'false'}"
                   data-tab-id="${tab.id}">
                ${tab.icon ? html`<span class="c-tab__icon">${ICONS[tab.icon] || ''}</span>` : ''}
                <span>${tab.label}</span>
                ${(tab.closable || _closable) ? html`
                  <span class="c-tab__close" data-close-tab="${tab.id}"
                        style="display: inline-flex; align-items: center; justify-content: center;
                               width: 16px; height: 16px; border-radius: 4px; cursor: pointer;
                               margin-left: 4px; color: var(--text-muted);"
                        title="Close ${tab.label}">
                    ${ICONS.close}
                  </span>
                ` : ''}
              </div>
            `;
          })}
        </div>

        <!-- Content area -->
        <div style="flex: 1; overflow-y: auto; position: relative; background: var(--bg-secondary);">
          ${_tabs.map((tab) => {
            const isActive = tab.id === _activeId;
            const shouldRender = isActive || tab.lazy === false || _renderedTabs.has(tab.id);
            // Mark as rendered if it will be shown
            if (isActive && !_renderedTabs.has(tab.id)) {
              _renderedTabs.add(tab.id);
            }
            return html`
              <div data-panel-id="${tab.id}"
                   style="display: ${isActive ? 'block' : 'none'}; height: 100%; overflow-y: auto;">
                ${shouldRender ? html`<div data-panel-content="${tab.id}"></div>` : ''}
              </div>
            `;
          })}
        </div>
      </div>
    `;

    _bindEvents();
    _renderActiveContent();
  }

  /**
   * Render the content for the active tab (supports async).
   * @private
   */
  async function _renderActiveContent() {
    if (_destroyed) return;

    const activeTab = _tabs.find((t) => t.id === _activeId);
    if (!activeTab) return;

    const contentEl = _container.querySelector(`[data-panel-content="${activeTab.id}"]`);
    if (!contentEl) return;

    // If content is already rendered, skip
    if (contentEl.dataset.rendered === 'true') return;

    try {
      let content = activeTab.render();
      // Support async render functions
      if (content && typeof content.then === 'function') {
        contentEl.innerHTML = '<div style="padding: 16px; text-align: center;"><span class="c-spinner c-spinner--sm c-spinner--accent">'
          + ICONS.refresh.html + '</span></div>';
        content = await content;
      }
      contentEl.innerHTML = content || '';
      contentEl.dataset.rendered = 'true';
    } catch (err) {
      console.error(`[TabPanel] Error rendering tab "${activeTab.id}":`, err);
      contentEl.innerHTML = `<div style="padding: 16px; color: var(--danger);">Failed to load content.</div>`;
    }
  }

  /* ── Events ──────────────────────────────────────────────────────────── */

  function _bindEvents() {
    // Tab click
    _container.querySelectorAll('[data-tab-id]').forEach((el) => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('[data-close-tab]')) return;
        const id = el.dataset.tabId;
        if (id && id !== _activeId) {
          activate(id);
        }
      });
    });

    // Close button
    _container.querySelectorAll('[data-close-tab]').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = el.dataset.closeTab;
        if (id) {
          removeTab(id);
        }
      });
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
    _render();

    if (_onChange) {
      _onChange(id);
    }
  }

  /**
   * Add a new tab.
   * @param {TabPanelDef} tabDef
   * @param {boolean} [activateNew=false] - Switch to the new tab
   */
  function addTab(tabDef, activateNew = false) {
    if (_destroyed) return;
    if (_tabs.find((t) => t.id === tabDef.id)) return;
    _tabs.push({ ...tabDef, lazy: tabDef.lazy !== false });
    if (activateNew) _activeId = tabDef.id;
    _render();
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
    _renderedTabs.delete(id);

    // If active tab was removed, activate the nearest tab
    if (_activeId === id) {
      const newIdx = Math.min(idx, _tabs.length - 1);
      _activeId = _tabs.length > 0 ? _tabs[newIdx].id : null;
      if (_onChange) _onChange(_activeId);
    }

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
   * Get all tab definitions.
   * @returns {TabPanelDef[]}
   */
  function getTabs() {
    return [..._tabs];
  }

  /**
   * Replace all tabs.
   * @param {TabPanelDef[]} newTabs
   * @param {string} [activateId]
   */
  function setTabs(newTabs, activateId) {
    if (_destroyed) return;
    _tabs = [...newTabs];
    _renderedTabs.clear();
    if (activateId && _tabs.find((t) => t.id === activateId)) {
      _activeId = activateId;
    } else if (_tabs.length > 0) {
      _activeId = _tabs[0].id;
    }
    _render();
  }

  /**
   * Set the onChange callback.
   * @param {Function} callback
   */
  function onChange(callback) {
    _onChange = callback;
  }

  /**
   * Re-render the active tab's content (useful for refreshes).
   */
  function refreshActiveTab() {
    if (_destroyed) return;
    const contentEl = _container.querySelector(`[data-panel-content="${_activeId}"]`);
    if (contentEl) {
      contentEl.dataset.rendered = 'false';
    }
    _renderedTabs.delete(_activeId);
    _renderActiveContent();
  }

  /**
   * Remove the component from the DOM.
   */
  function destroy() {
    _destroyed = true;
    _container.innerHTML = '';
    _tabs = [];
    _renderedTabs.clear();
    _activeId = null;
    _onChange = null;
  }

  // Initial render
  _render();

  return {
    activate,
    addTab,
    removeTab,
    getActiveTab,
    getTabs,
    setTabs,
    onChange,
    refreshActiveTab,
    destroy,
  };
}

/**
 * @typedef {Object} TabPanelAPI
 * @property {(id: string) => void} activate
 * @property {(tabDef: TabPanelDef, activateNew?: boolean) => void} addTab
 * @property {(id: string) => void} removeTab
 * @property {() => string|null} getActiveTab
 * @property {() => TabPanelDef[]} getTabs
 * @property {(newTabs: TabPanelDef[], activateId?: string) => void} setTabs
 * @property {(callback: Function) => void} onChange
 * @property {() => void} refreshActiveTab
 * @property {() => void} destroy
 */

export default createTabPanel;
