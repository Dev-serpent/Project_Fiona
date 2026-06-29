/* ==========================================================================
   plugins.js — Plugin Manager Page
   ==========================================================================
   Manages Fiona plugins: list, enable/disable, configure, uninstall, and
   install new plugins.  Supports category filtering, search, update
   checks, dependency display, and graceful empty-state fallback when
   the backend API is unavailable.
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
  skeletonButton,
} from '../js/components/LoadingSkeleton.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const CATEGORIES = [
  { id: 'all',       label: 'All' },
  { id: 'enabled',   label: 'Enabled' },
  { id: 'disabled',  label: 'Disabled' },
  { id: 'core',      label: 'Core' },
  { id: 'community', label: 'Community' },
];

/* ── (No mock data — live API only) ────────────────────────────────────── */

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  plugins: [],
  filteredPlugins: [],
  category: 'all',
  searchQuery: '',

  // Install modal
  showInstallModal: false,
  installPath: '',
  installLoading: false,

  // Detail expansion
  expandedId: null,

  // Uninstall confirm
  uninstallTarget: null,

  // Update cache: map of plugin id → latest version string (null = up-to-date)
  updateCache: null,
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

function esc(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

/* ── Render ─────────────────────────────────────────────────────────────── */

async function renderPage(container) {
  if (_state.destroyed) return;
  _state.container = container;

  if (_state.loading) {
    renderSkeletons(container);
    return;
  }

  if (_state.error) {
    renderError(container);
    return;
  }

  const total = _state.plugins.length;
  const enabled = _state.plugins.filter((p) => p.status === 'enabled').length;
  const filtered = applyFilters();

  // Build raw HTML sections
  const categoryTabs = CATEGORIES.map((cat) =>
    `<div class="c-tab ${cat.id === _state.category ? 'c-tab--active' : ''}" data-action="filter-category" data-category="${cat.id}" style="cursor: pointer; font-size: var(--font-size-xs);">${esc(cat.label)}</div>`
  ).join('');

  let pluginCards;
  if (filtered.length === 0) {
    pluginCards = `<div style="text-align: center; padding: var(--space-8); color: var(--text-muted); font-size: var(--font-size-sm);">${
      _state.searchQuery
        ? `No plugins matching "${esc(_state.searchQuery)}".`
        : 'No plugins in this category.'
    }</div>`;
  } else {
    pluginCards = filtered.map((plugin) => String(renderPluginRow(plugin))).join('');
  }

  const installModal = _state.showInstallModal ? renderInstallModal().html : '';

  const data = {
    pluginCount: total,
    pluginPlural: total !== 1 ? 's' : '',
    enabledCount: enabled,
    plusIcon: ICONS.plus.html,
    refreshIcon: ICONS.refresh.html,
    searchIcon: ICONS.search.html,
    categoryTabs,
    searchQuery: esc(_state.searchQuery),
    filteredCount: filtered.length,
    pluginCards,
    installModal,
  };

  container.innerHTML = await loadTemplate('plugins', data);
  mountHandlers(container);
}

function renderPluginRow(plugin) {
  const isExpanded = _state.expandedId === plugin.id;
  const isEnabled = plugin.status === 'enabled';

  // Check for available update
  const hasUpdate = _state.updateCache && _state.updateCache[plugin.id];
  const updateVersion = hasUpdate && typeof _state.updateCache[plugin.id] === 'string'
    ? _state.updateCache[plugin.id] : null;

  const depCount = Array.isArray(plugin.dependencies) ? plugin.dependencies.length : 0;

  return html`
    <div class="c-card" style="overflow: visible;">
      <div class="c-card__body" style="padding: var(--space-3) var(--space-4);">
        <!-- Main row -->
        <div style="display: flex; align-items: flex-start; gap: var(--space-3);">
          <!-- Plugin icon placeholder -->
          <div style="width: 36px; height: 36px; border-radius: var(--radius-md);
                      background: ${isEnabled ? 'var(--accent-muted)' : 'var(--bg-tertiary)'};
                      display: flex; align-items: center; justify-content: center;
                      color: ${isEnabled ? 'var(--accent)' : 'var(--text-muted)'};
                      flex-shrink: 0;">
            ${ICONS.puzzle}
          </div>

          <!-- Info -->
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
              <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary);">
                ${esc(plugin.name)}
              </span>
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted); font-family: var(--font-mono);">
                v${esc(plugin.version)}
              </span>
              ${hasUpdate ? html`
                <span class="c-badge c-badge--warning" style="font-size: 9px; padding: 0 6px; cursor: help;"
                      title="${updateVersion ? `Update available: v${esc(updateVersion)}` : 'Update available'}">
                  ${updateVersion ? esc(updateVersion) : 'Update'}
                </span>
              ` : ''}
              <span class="c-badge c-badge--${isEnabled ? 'success' : 'default'}" style="font-size: 9px; padding: 0 6px;">
                ${isEnabled ? 'Enabled' : 'Disabled'}
              </span>
              ${plugin.category === 'core' ? html`
                <span class="c-badge c-badge--accent" style="font-size: 9px; padding: 0 6px;">Core</span>
              ` : html`
                <span class="c-badge c-badge--default" style="font-size: 9px; padding: 0 6px;">Community</span>
              `}
              ${depCount > 0 ? html`
                <span class="c-badge c-badge--info" style="font-size: 9px; padding: 0 6px; cursor: help;"
                      title="${depCount} dependenc${depCount !== 1 ? 'ies' : 'y'}">
                  ${depCount} dep${depCount !== 1 ? 's' : ''}
                </span>
              ` : ''}
            </div>
            <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: 2px; max-width: 500px;">
              ${esc(plugin.description)}
            </div>
            <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 2px;">
              by ${esc(plugin.author)}
            </div>
          </div>

          <!-- Actions -->
          <div style="display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0;">
            <!-- Toggle switch -->
            <label class="c-toggle" style="margin: 0;" title="${isEnabled ? 'Disable' : 'Enable'} plugin">
              <input type="checkbox" class="c-toggle__input" data-action="toggle-plugin" data-plugin-id="${plugin.id}"
                     ${isEnabled ? 'checked' : ''}>
              <span class="c-toggle__track"><span class="c-toggle__thumb"></span></span>
            </label>
            <button class="c-btn c-btn--sm c-btn--ghost" data-action="configure-plugin" data-plugin-id="${plugin.id}"
                    title="Configure" style="padding: 2px 6px;">
              <span class="c-btn__icon">${ICONS.gear}</span>
            </button>
            <button class="c-btn c-btn--sm c-btn--ghost c-btn--danger" data-action="uninstall-plugin" data-plugin-id="${plugin.id}"
                    title="Uninstall" style="padding: 2px 6px;">
              <span class="c-btn__icon">${ICONS.trash}</span>
            </button>
            <button class="c-btn c-btn--sm c-btn--ghost" data-action="expand-plugin" data-plugin-id="${plugin.id}"
                    style="padding: 2px 6px;">
              <span class="c-btn__icon">${isExpanded ? ICONS.chevronUp : ICONS.chevronDown}</span>
            </button>
          </div>
        </div>

        <!-- Expanded details -->
        ${isExpanded ? html`
          <div style="margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border-subtle);">
            <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-bottom: var(--space-2);">
              ${esc(plugin.fullDescription || plugin.description)}
            </div>
            ${depCount > 0 ? html`
              <div style="margin-bottom: var(--space-2);">
                <span style="font-size: var(--font-size-xxs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Dependencies</span>
                <div style="display: flex; flex-wrap: wrap; gap: var(--space-1); margin-top: 4px;">
                  ${html.raw(plugin.dependencies.map((dep) => html`
                    <span style="font-size: var(--font-size-xxs); padding: 2px 8px; background: var(--bg-tertiary); border-radius: var(--radius-sm); color: var(--text-muted); font-family: var(--font-mono);">
                      ${esc(typeof dep === 'string' ? dep : dep.name || dep.id || String(dep))}
                    </span>
                  `).join(''))}
                </div>
              </div>
            ` : ''}
            ${hasUpdate ? html`
              <div style="margin-bottom: var(--space-2);">
                <span style="font-size: var(--font-size-xxs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Update</span>
                <p style="font-size: var(--font-size-xs); color: var(--text-secondary); margin: 4px 0 0;">
                  A newer version${updateVersion ? ` (v${esc(updateVersion)})` : ''} is available.
                  Run <strong>Check Updates</strong> for details.
                </p>
              </div>
            ` : ''}
            ${plugin.config ? html`
              <div>
                <span style="font-size: var(--font-size-xxs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Configuration</span>
                <pre style="margin-top: 4px; padding: var(--space-2); background: var(--bg-tertiary); border-radius: var(--radius-sm);
                            font-size: var(--font-size-xxs); font-family: var(--font-mono); overflow-x: auto;
                            color: var(--text-secondary); white-space: pre-wrap; word-break: break-all;">
${esc(JSON.stringify(plugin.config, null, 2))}
                </pre>
              </div>
            ` : ''}
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function renderInstallModal() {
  return html`
    <div class="c-modal-backdrop" id="install-modal-backdrop" style="display: flex;">
      <div class="c-modal c-modal--sm">
        <div class="c-modal__header">
          <h3 class="c-modal__title">Install Plugin</h3>
          <button class="c-modal__close" data-action="close-install-modal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="c-modal__body">
          <p style="color: var(--text-secondary); font-size: var(--font-size-sm); margin-bottom: var(--space-3);">
            Provide a path to a plugin package or directory.
          </p>
          <div class="c-form-group" style="margin-bottom: var(--space-3);">
            <label class="c-form-group__label">Plugin Path</label>
            <div style="display: flex; gap: var(--space-2);">
              <input type="text" class="c-input" id="install-plugin-path"
                     placeholder="/path/to/plugin.zip or /path/to/plugin/dir"
                     value="${esc(_state.installPath)}"
                     style="flex: 1;">
              <button class="c-btn c-btn--sm c-btn--ghost" id="install-browse-btn" title="Browse">
                <span class="c-btn__icon">${ICONS.folder}</span>
              </button>
            </div>
          </div>
          <div class="c-form-group">
            <label class="c-form-group__label">Or paste a URL</label>
            <input type="text" class="c-input" id="install-plugin-url"
                   placeholder="https://example.com/plugin.zip">
          </div>
        </div>
        <div class="c-modal__footer">
          <button class="c-btn" data-action="close-install-modal">Cancel</button>
          <button class="c-btn c-btn--primary" id="install-confirm-btn"
                  ?disabled="${_state.installLoading}">
            ${_state.installLoading ? 'Installing…' : 'Install'}
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      ${skeletonHeading({ width: '200px' })}
      ${skeletonText({ width: '180px' })}
      <div style="display: flex; gap: var(--space-2); margin: var(--space-4) 0;">
        ${Array.from({ length: 5 }, () => skeletonButton())}
        ${skeletonText({ width: '200px', style: 'height: 32px;' })}
      </div>
      <div style="display: flex; flex-direction: column; gap: var(--space-2);">
        ${Array.from({ length: 4 }, () => skeletonCard({ height: '80px' }))}
      </div>
    </div>
  `;
}

function renderError(container) {
  container.innerHTML = html`
    <div class="empty-state" style="margin-top: 10vh;">
      <div class="empty-state__icon" style="color: var(--danger);">
        ${ICONS.error}
      </div>
      <div class="empty-state__title">Failed to Load Plugins</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to reach the Fiona backend for plugin data.')}
      </div>
      <button class="c-btn c-btn--primary" id="plugin-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#plugin-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Filtering ──────────────────────────────────────────────────────────── */

function applyFilters() {
  let list = _state.plugins;

  // Category filter
  switch (_state.category) {
    case 'enabled':
      list = list.filter((p) => p.status === 'enabled');
      break;
    case 'disabled':
      list = list.filter((p) => p.status === 'disabled');
      break;
    case 'core':
      list = list.filter((p) => p.category === 'core');
      break;
    case 'community':
      list = list.filter((p) => p.category === 'community');
      break;
    default: // 'all'
      break;
  }

  // Search
  if (_state.searchQuery) {
    const q = _state.searchQuery.toLowerCase();
    list = list.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.author.toLowerCase().includes(q),
    );
  }

  _state.filteredPlugins = list;
  return list;
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // Category filter tabs
  container.querySelectorAll('[data-action="filter-category"]').forEach((el) => {
    el.addEventListener('click', async () => {
      _state.category = el.dataset.category;
      if (_state.container) await renderPage(_state.container);
    });
  });

  // Search
  const searchInput = container.querySelector('#plugin-search');
  if (searchInput) {
    searchInput.addEventListener('input', async (e) => {
      _state.searchQuery = e.target.value;
      if (_state.container) await renderPage(_state.container);
    });
  }

  // Install button
  container.querySelector('#plugin-install-btn')?.addEventListener('click', async () => {
    _state.showInstallModal = true;
    _state.installPath = '';
    if (_state.container) await renderPage(_state.container);
    // Focus path input after render
    setTimeout(() => {
      const el = _state.container?.querySelector('#install-plugin-path');
      if (el) el.focus();
    }, 50);
  });

  // Check updates
  container.querySelector('#plugin-check-updates')?.addEventListener('click', checkUpdates);

  // Toggle plugin
  container.querySelectorAll('[data-action="toggle-plugin"]').forEach((el) => {
    el.addEventListener('change', (e) => {
      const pluginId = e.target.dataset.pluginId;
      const enabled = e.target.checked;
      togglePlugin(pluginId, enabled);
    });
  });

  // Configure
  container.querySelectorAll('[data-action="configure-plugin"]').forEach((el) => {
    el.addEventListener('click', (e) => {
      const pluginId = e.target.closest('[data-plugin-id]')?.dataset.pluginId
        || e.target.dataset.pluginId;
      if (pluginId) openConfig(pluginId);
    });
  });

  // Uninstall
  container.querySelectorAll('[data-action="uninstall-plugin"]').forEach((el) => {
    el.addEventListener('click', (e) => {
      const pluginId = e.target.closest('[data-plugin-id]')?.dataset.pluginId
        || e.target.dataset.pluginId;
      if (pluginId) confirmUninstall(pluginId);
    });
  });

  // Expand/collapse
  container.querySelectorAll('[data-action="expand-plugin"]').forEach((el) => {
    el.addEventListener('click', async (e) => {
      const pluginId = e.target.closest('[data-plugin-id]')?.dataset.pluginId
        || e.target.dataset.pluginId;
      _state.expandedId = _state.expandedId === pluginId ? null : pluginId;
      if (_state.container) await renderPage(_state.container);
    });
  });

  // Install modal actions
  if (_state.showInstallModal) {
    const backdrop = container.querySelector('#install-modal-backdrop');
    backdrop?.addEventListener('click', (e) => {
      if (e.target === e.currentTarget) closeInstallModal();
    });
    container.querySelector('[data-action="close-install-modal"]')?.addEventListener('click', closeInstallModal);
    container.querySelector('#install-confirm-btn')?.addEventListener('click', doInstall);
    container.querySelector('#install-browse-btn')?.addEventListener('click', browseForPlugin);
    // Enter key in path input
    container.querySelector('#install-plugin-path')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') doInstall();
    });
    container.querySelector('#install-plugin-url')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') doInstall();
    });
  }
}

/* ── Plugin Actions ─────────────────────────────────────────────────────── */

async function togglePlugin(pluginId, enabled) {
  const api = getApi();
  const plugin = _state.plugins.find((p) => p.id === pluginId);
  if (!plugin) return;

  // Optimistic update
  plugin.status = enabled ? 'enabled' : 'disabled';
  if (_state.container) await renderPage(_state.container);

  if (api) {
    try {
      const endpoint = enabled
        ? `/api/v1/plugins/${encodeURIComponent(pluginId)}/enable`
        : `/api/v1/plugins/${encodeURIComponent(pluginId)}/disable`;
      await api.post(endpoint);
    } catch (err) {
      // Revert on failure
      plugin.status = enabled ? 'disabled' : 'enabled';
      if (_state.container) await renderPage(_state.container);
      showToast('error', `Failed to ${enabled ? 'enable' : 'disable'} plugin: ${err.message}`);
    }
  } else {
    // No API — revert the optimistic update
    plugin.status = enabled ? 'disabled' : 'enabled';
    if (_state.container) await renderPage(_state.container);
    showToast('error', 'Backend API is not available.');
  }
}

async function confirmUninstall(pluginId) {
  const plugin = _state.plugins.find((p) => p.id === pluginId);
  if (!plugin) return;

  _state.uninstallTarget = pluginId;

  const modalContainer = document.getElementById('modal-container');
  if (!modalContainer) return;

  modalContainer.innerHTML = `
    <div class="c-modal-backdrop" id="uninstall-backdrop">
      <div class="c-modal c-modal--sm">
        <div class="c-modal__header">
          <h3 class="c-modal__title">Uninstall Plugin</h3>
          <button class="c-modal__close" data-action="close-modal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="c-modal__body">
          <p style="color: var(--text-secondary); font-size: var(--font-size-sm);">
            Are you sure you want to uninstall <strong>${esc(plugin.name)}</strong>?
          </p>
          <p style="color: var(--text-muted); font-size: var(--font-size-xs); margin-top: var(--space-2);">
            This will remove the plugin and all its configuration.
          </p>
        </div>
        <div class="c-modal__footer">
          <button class="c-btn" data-action="cancel-uninstall">Cancel</button>
          <button class="c-btn c-btn--danger-solid" data-action="confirm-uninstall" data-plugin-id="${esc(pluginId)}">
            Uninstall
          </button>
        </div>
      </div>
    </div>
  `;

  modalContainer.style.display = 'flex';

  const close = () => {
    modalContainer.innerHTML = '';
    modalContainer.style.display = 'none';
    _state.uninstallTarget = null;
  };

  modalContainer.querySelector('[data-action="close-modal"]')?.addEventListener('click', close);
  modalContainer.querySelector('[data-action="cancel-uninstall"]')?.addEventListener('click', close);
  modalContainer.querySelector('#uninstall-backdrop')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) close();
  });
  modalContainer.querySelector('[data-action="confirm-uninstall"]')?.addEventListener('click', async (e) => {
    const id = e.target.dataset.pluginId;
    close();
    await doUninstall(id);
  });
}

async function doUninstall(pluginId) {
  const api = getApi();
  const idx = _state.plugins.findIndex((p) => p.id === pluginId);
  if (idx === -1) return;
  const plugin = _state.plugins[idx];

  // Optimistic removal
  _state.plugins.splice(idx, 1);
  if (_state.container) await renderPage(_state.container);

  if (api) {
    try {
      await api.del(`/api/v1/plugins/${encodeURIComponent(pluginId)}`);
      showToast('success', `${plugin.name} uninstalled.`);
    } catch (err) {
      // Revert
      _state.plugins.splice(idx, 0, plugin);
      if (_state.container) await renderPage(_state.container);
      showToast('error', `Failed to uninstall: ${err.message}`);
    }
  } else {
    // No API — revert
    _state.plugins.splice(idx, 0, plugin);
    if (_state.container) await renderPage(_state.container);
    showToast('error', 'Backend API is not available.');
  }
}

async function openConfig(pluginId) {
  const plugin = _state.plugins.find((p) => p.id === pluginId);
  if (!plugin) return;

  const api = getApi();
  if (api) {
    try {
      await api.get(`/api/v1/plugins/${encodeURIComponent(pluginId)}/config`, {}, { responseType: 'json' }).catch(() => {});
    } catch { /* fall through to showing local config */ }
  }

  // Show config in expanded view
  _state.expandedId = pluginId;
  if (_state.container) await renderPage(_state.container);
  showToast('info', `Configuration for ${plugin.name} — edit in expanded view.`);
}

/* ── Install Flow ───────────────────────────────────────────────────────── */

function closeInstallModal() {
  _state.showInstallModal = false;
  _state.installPath = '';
  _state.installLoading = false;
  if (_state.container) renderPage(_state.container);
}

async function browseForPlugin() {
  // Try using the backend file dialog, fallback to manual entry
  const api = getApi();
  if (api) {
    try {
      const res = await api.post('/api/v1/files/dialog', { type: 'open', filters: [{ name: 'Plugins', extensions: ['zip', 'tgz', 'gz'] }] });
      const path = res?.data?.path || res?.path;
      if (path) {
        _state.installPath = path;
        const input = _state.container?.querySelector('#install-plugin-path');
        if (input) input.value = path;
      }
      return;
    } catch { /* fallback to manual */ }
  }
  showToast('info', 'Enter the plugin path or URL manually.');
}

async function doInstall() {
  const pathInput = _state.container?.querySelector('#install-plugin-path');
  const urlInput = _state.container?.querySelector('#install-plugin-url');
  const path = pathInput?.value?.trim() || _state.installPath?.trim();
  const url = urlInput?.value?.trim();

  if (!path && !url) {
    showToast('error', 'Please enter a plugin path or URL.');
    return;
  }

  const source = url || path;
  _state.installLoading = true;
  if (_state.container) renderPage(_state.container);

  const api = getApi();
  if (!api) {
    _state.installLoading = false;
    if (_state.container) renderPage(_state.container);
    showToast('error', 'Backend API is not available for installation.');
    return;
  }

  try {
    const result = await api.post('/api/v1/plugins/install', { path: source });
    const plugin = result?.data || result;
    if (plugin && plugin.id) {
      _state.plugins.push({
        id: plugin.id,
        name: plugin.name || plugin.id,
        version: plugin.version || '0.0.0',
        author: plugin.author || 'Unknown',
        description: plugin.description || '',
        status: 'enabled',
        category: plugin.category || 'community',
        dependencies: plugin.dependencies || [],
        config: plugin.config || {},
        fullDescription: plugin.fullDescription || plugin.description || '',
      });
    }
    closeInstallModal();
    showToast('success', `Plugin installed: ${plugin?.name || source}`);
    if (_state.container) renderPage(_state.container);
  } catch (err) {
    _state.installLoading = false;
    if (_state.container) renderPage(_state.container);
    showToast('error', `Installation failed: ${err.message}`);
  }
}

/* ── Check Updates ──────────────────────────────────────────────────────── */

async function fetchUpdates() {
  const api = getApi();
  if (!api) return null;

  try {
    const result = await api.get('/api/v1/plugins/updates');
    const updates = result?.data || result;
    if (Array.isArray(updates)) {
      // Convert to a map: plugin id → latest version string
      const updateMap = {};
      for (const u of updates) {
        if (u && u.id) {
          updateMap[u.id] = u.latestVersion || u.version || true;
        }
      }
      return updateMap;
    }
  } catch { /* fallback */ }
  return null;
}

async function checkUpdates() {
  try {
    _state.updateCache = await fetchUpdates();
  } catch {
    _state.updateCache = null;
  }

  if (_state.updateCache && Object.keys(_state.updateCache).length > 0) {
    const count = Object.keys(_state.updateCache).length;
    showToast('info', `${count} update(s) available.`);
  } else {
    showToast('success', 'All plugins are up to date.');
  }

  if (_state.container) renderPage(_state.container);
}

/* ── Toast ───────────────────────────────────────────────────────────────── */

function showToast(type, message) {
  const toast = document.createElement('div');
  toast.className = `c-toast c-toast--${type || 'info'} animate-slide-right`;
  toast.style.cssText = 'position: fixed; bottom: 60px; right: 20px; z-index: 9999; max-width: 360px;';
  toast.innerHTML = `
    <div class="c-toast__icon">${ICONS[type === 'success' ? 'check' : type === 'error' ? 'error' : 'info']}</div>
    <div class="c-toast__content"><div class="c-toast__message">${esc(message)}</div></div>
    <button class="c-toast__dismiss" data-toast-dismiss style="flex-shrink:0;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  `;
  document.body.appendChild(toast);
  toast.querySelector('[data-toast-dismiss]')?.addEventListener('click', () => toast.remove());
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.2s';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadData() {
  if (_state.destroyed) return;

  const api = getApi();
  _state.plugins = [];
  _state.error = false;
  _state.errorMessage = '';

  if (api) {
    try {
      const result = await api.get('/api/v1/plugins');
      let plugins = result?.data || result;
      if (Array.isArray(plugins)) {
        _state.plugins = plugins;
      }
    } catch (err) {
      console.log('[plugins] Backend unavailable:', err.message);
      // Graceful fallback — empty state instead of mock data
      _state.plugins = [];
      _state.loading = false;
      if (!_state.destroyed && _state.container) {
        renderPage(_state.container);
      }
      return;
    }
  } else {
    // No API available — graceful empty fallback
    _state.plugins = [];
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
    return;
  }

  // After loading plugins, check for updates
  try {
    _state.updateCache = await fetchUpdates();
  } catch {
    _state.updateCache = null;
  }

  _state.loading = false;
  _state.error = false;

  if (!_state.destroyed && _state.container) {
    renderPage(_state.container);
  }
}

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;
  _state.expandedId = null;
  _state.showInstallModal = false;

  renderSkeletons(container);
  loadData();
}

export function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && _state.container) {
    renderPage(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;
  _state.container = null;
  _state.plugins = [];
  _state.filteredPlugins = [];
  _state.expandedId = null;
  _state.showInstallModal = false;
  _state.uninstallTarget = null;
  _state.updateCache = null;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="plugins-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#plugins-root') || container;
      render(root);
    },
    destroy,
  };
}
