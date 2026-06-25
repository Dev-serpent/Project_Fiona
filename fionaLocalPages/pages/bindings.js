/* ==========================================================================
   bindings.js — Key Bindings Viewer Page
   ==========================================================================
   Displays QuikTieper application key bindings grouped by app.
   Provides search/filter, inline expandable details, and a dedicated
   detail side panel when a binding is selected. Read-only display with
   a save action to persist the config back to the backend.

   Backend APIs:
     GET  /api/v1/bindings       → { ok, data: { config, apps: [...] } }
     GET  /api/v1/bindings/apps  → { ok, data: { apps: [...] } }
     POST /api/v1/bindings/save  → { ok, data: { path, saved } }

   Exports: { render(container?), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
  skeletonButton,
} from '../js/components/LoadingSkeleton.js';
import { toast } from '../js/components/Toast.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const STORAGE_KEY = 'fiona_bindings_state';

/** Key names that are considered modifiers (rendered as distinct chips). */
const MODIFIER_KEYS = new Set([
  'ctrl', 'control', 'shift', 'alt', 'option', 'meta', 'cmd', 'command',
  'win', 'super',
]);

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  // Raw data
  config: null,           // Full config object from backend
  rawBindings: [],        // All binding entries as received
  groupedBindings: {},    // { appName: [binding, ...] }
  appOrder: [],           // Sorted app names

  // UI state
  searchQuery: '',
  selectedBinding: null,  // The binding object currently selected for detail
  expandedBindings: new Set(),  // Set of binding composite keys expanded inline
  saving: false,

  _boundListeners: [],
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

/**
 * Escape HTML special characters.
 * @param {*} str
 * @returns {string}
 */
function esc(str) {
  if (str == null) return '';
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

/**
 * Persist lightweight UI state to localStorage.
 */
function persistState() {
  try {
    const data = { searchQuery: _state.searchQuery };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    // Silently fail
  }
}

/**
 * Load persisted UI state from localStorage.
 */
function loadPersistedState() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const data = JSON.parse(stored);
      _state.searchQuery = data.searchQuery || '';
    }
  } catch (e) {
    // Silently fail
  }
}

/**
 * Normalize the apps data from the backend into a flat array of binding
 * entries with a unique composite ID assigned to each.
 *
 * Handles both:
 *   - Flat array: [ { name, keys, command, ... }, ... ]
 *   - Grouped object: { "AppName": [ { keys, command, ... }, ... ] }
 *
 * Each entry receives: { _id, _appName, ...originalFields }
 *
 * @param {Array|Object} apps
 * @returns {Array<Object>}
 */
function normalizeBindings(apps) {
  const result = [];

  if (Array.isArray(apps)) {
    // Flat array — each entry has a `name` field for the app
    for (let i = 0; i < apps.length; i++) {
      const entry = { ...apps[i] };
      entry._appName = entry.name || 'Unnamed';
      entry._id = `${entry._appName}::${i}`;
      result.push(entry);
    }
  } else if (apps && typeof apps === 'object') {
    // Grouped object — keys are app names, values are arrays of bindings
    let globalIdx = 0;
    for (const appName of Object.keys(apps)) {
      const bindings = Array.isArray(apps[appName]) ? apps[appName] : [];
      for (let i = 0; i < bindings.length; i++) {
        const entry = { ...bindings[i] };
        entry._appName = appName;
        entry._id = `${appName}::${globalIdx++}`;
        result.push(entry);
      }
    }
  }

  return result;
}

/**
 * Group a flat array of binding entries by app name.
 * @param {Array<Object>} bindings
 * @returns {Object} { appName: [binding, ...] }
 */
function groupByApp(bindings) {
  const groups = {};
  for (const entry of bindings) {
    const app = entry._appName || 'Other';
    if (!groups[app]) groups[app] = [];
    groups[app].push(entry);
  }
  return groups;
}

/**
 * Parse a keys value into an array of key part strings.
 *
 * Accepts:
 *   - String: "Ctrl+Shift+T" → ["Ctrl", "Shift", "T"]
 *   - Object: { key: 't', ctrl: true, shift: true } → ["Ctrl", "Shift", "T"]
 *
 * @param {string|Object} keys
 * @returns {string[]}
 */
function parseKeys(keys) {
  if (!keys) return [];

  if (typeof keys === 'string') {
    return keys.split(/\+/).map((k) => k.trim()).filter(Boolean);
  }

  if (typeof keys === 'object') {
    const parts = [];
    if (keys.ctrl) parts.push('Ctrl');
    if (keys.shift) parts.push('Shift');
    if (keys.alt) parts.push('Alt');
    if (keys.meta) parts.push('Cmd');
    if (keys.super) parts.push('Super');
    const keyVal = keys.key || keys.keys || '';
    if (keyVal) {
      // Split compound key values just in case
      const sub = String(keyVal).split(/\+/).map((k) => k.trim()).filter(Boolean);
      parts.push(...sub);
    }
    return parts;
  }

  return [String(keys)];
}

/**
 * Render key combination parts as styled chips.
 * Modifier keys get a distinct style; regular keys get monospace text.
 *
 * @param {string|Object} keys
 * @returns {Array} Array of html raw wrappers (for use with html.raw)
 */
function renderKeyChips(keys) {
  const parts = parseKeys(keys);
  return parts.map((part) => {
    const normalized = part.toLowerCase().replace(/[^a-z0-9]/g, '');
    const isModifier = MODIFIER_KEYS.has(normalized);
    return html`
      <span class="c-badge key-chip${isModifier ? ' key-chip--mod' : ' key-chip--key'}"
            style="font-family: ${isModifier ? 'var(--font-ui)' : 'var(--font-mono)'};
                   font-size: var(--font-size-xxs);
                   padding: 1px 7px;
                   margin: 1px 2px;
                   ${isModifier
                     ? 'background: var(--accent-muted); color: var(--accent); border: 1px solid var(--accent);'
                     : 'background: var(--surface-alt); color: var(--text-primary); border: 1px solid var(--border);'};
                   border-radius: var(--radius-sm);
                   display: inline-flex;
                   align-items: center;
                   white-space: nowrap;
                   text-transform: ${isModifier ? 'none' : 'lowercase'};
                   font-weight: ${isModifier ? 'var(--font-weight-medium)' : 'var(--font-weight-normal)'};">${esc(part)}</span>
    `;
  });
}

/**
 * Get a human-readable label for a binding type value.
 * @param {string} type
 * @returns {string}
 */
function bindingTypeLabel(type) {
  if (!type) return '—';
  const labels = {
    'keyboard': 'Keyboard Shortcut',
    'mouse': 'Mouse Binding',
    'gesture': 'Gesture',
    'chord': 'Chord',
    'sequence': 'Sequence',
    'global': 'Global Shortcut',
  };
  return labels[type.toLowerCase()] || type;
}

/**
 * Format a cooldown value for display.
 * @param {number|string} seconds
 * @returns {string}
 */
function formatCooldown(seconds) {
  if (seconds == null || seconds === '') return 'None';
  const s = Number(seconds);
  if (isNaN(s) || s <= 0) return 'None';
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
}

/* ── HTML Renderers ─────────────────────────────────────────────────────── */

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

  // Filter by search query
  const query = _state.searchQuery.toLowerCase().trim();
  const filteredBindings = query
    ? _state.rawBindings.filter((entry) => {
        const appName = (entry._appName || '').toLowerCase();
        const keys = (entry.keys || '').toLowerCase();
        const command = (entry.command || '').toLowerCase();
        const instruction = (entry.instruction || '').toLowerCase();
        const name = (entry.name || '').toLowerCase();
        return (
          appName.includes(query) ||
          keys.includes(query) ||
          command.includes(query) ||
          instruction.includes(query) ||
          name.includes(query)
        );
      })
    : _state.rawBindings;

  // Re-group filtered results
  const filteredGroups = groupByApp(filteredBindings);
  const filteredAppOrder = Object.keys(filteredGroups).sort((a, b) =>
    a.localeCompare(b)
  );

  const totalCount = _state.rawBindings.length;

  // Build dynamic content sections
  let appListContent = '';
  if (filteredBindings.length === 0) {
    if (totalCount === 0) {
      appListContent = String(renderEmptyState());
    } else {
      appListContent = html`
        <div style="text-align: center; padding: var(--space-10); color: var(--text-muted);">
          <div style="font-size: 28px; margin-bottom: var(--space-3); opacity: 0.3;">${ICONS.search}</div>
          <div style="font-size: var(--font-size-md);">No bindings match &quot;${esc(query)}&quot;</div>
        </div>
      `;
    }
  } else {
    appListContent = html.raw(filteredAppOrder.map((appName) =>
      renderAppSection(appName, filteredGroups[appName])
    ).join(''));
  }

  const detailPanelContent = renderDetailPanel();

  const saveBtnIcon = _state.saving
    ? html`<span class="c-spinner c-spinner--sm" style="width:14px;height:14px;"></span>`
    : ICONS.check;
  const saveBtnText = _state.saving ? 'Saving&hellip;' : 'Save';

  const data = {
    keyboardIcon: ICONS.keyboard.html,
    searchIcon: ICONS.search.html,
    totalCount: String(totalCount),
    singular: totalCount === 1,
    saving: _state.saving,
    saveBtnIcon,
    saveBtnText,
    searchQuery: esc(_state.searchQuery),
    appListContent,
    detailPanelContent,
  };

  container.innerHTML = await loadTemplate('bindings', data);
  mountComponents(container);
}

/**
 * Render an empty state when no bindings exist at all.
 * @returns {string} HTML
 */
function renderEmptyState() {
  return html`
    <div style="text-align: center; padding: var(--space-12); color: var(--text-muted);">
      <div style="font-size: 36px; margin-bottom: var(--space-4); opacity: 0.3;">${ICONS.keyboard}</div>
      <div style="font-size: var(--font-size-md); font-weight: var(--font-weight-medium); margin-bottom: var(--space-2);">No bindings configured</div>
      <div style="font-size: var(--font-size-sm); color: var(--text-muted);">Key bindings will appear here once they are configured in the backend.</div>
    </div>
  `;
}

/**
 * Render a single app section with its bindings.
 * @param {string} appName
 * @param {Array<Object>} bindings
 * @returns {string} HTML
 */
function renderAppSection(appName, bindings) {
  return html`
    <div class="c-card binding-app-section" style="margin-bottom: var(--space-3); overflow: hidden;">
      <!-- App Header -->
      <div class="binding-app-header"
           style="display: flex; align-items: center; justify-content: space-between;
                  padding: var(--space-2) var(--space-3);
                  background: var(--surface);
                  border-bottom: 1px solid var(--border-subtle);
                  cursor: default;
                  user-select: none;">
        <div style="display: flex; align-items: center; gap: var(--space-2); min-width: 0;">
          <span style="width: 16px; height: 16px; display: inline-flex; color: var(--text-muted); flex-shrink: 0;">${ICONS.terminal}</span>
          <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary);">${esc(appName)}</span>
        </div>
        <span class="c-badge" style="font-size: var(--font-size-xxs); padding: 0 6px; line-height: 18px;">
          ${bindings.length}
        </span>
      </div>

      <!-- Binding List -->
      <div class="binding-list" style="padding: 0;">
        ${html.raw(bindings.map((binding, idx) => renderBindingRow(binding, appName, idx)).join(''))}
      </div>
    </div>
  `;
}

/**
 * Render a single binding row within an app section.
 * @param {Object} binding
 * @param {string} appName
 * @param {number} idx
 * @returns {string} HTML
 */
function renderBindingRow(binding, appName, idx) {
  const isSelected =
    _state.selectedBinding && _state.selectedBinding._id === binding._id;
  const isExpanded = _state.expandedBindings.has(binding._id);
  const keysChips = renderKeyChips(binding.keys);
  const command = binding.command || '';
  const instruction = binding.instruction || '';

  return html`
    <div class="binding-row${isSelected ? ' binding-row--selected' : ''}"
         data-binding-id="${esc(binding._id)}"
         style="border-bottom: 1px solid var(--border-subtle);
                cursor: pointer;
                transition: background var(--transition-fast);
                ${isSelected ? 'background: var(--accent-muted);' : ''}
                ${isSelected ? '' : 'background: transparent;'}"
         data-action="select-binding">
      <!-- Compact row -->
      <div style="display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); min-width: 0;">
        <!-- Key chips -->
        <div style="display: flex; align-items: center; gap: 1px; flex-shrink: 0; min-width: 60px; flex-wrap: wrap;">
          ${html.raw(keysChips.join(''))}
        </div>
        <!-- Command -->
        <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-primary); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(command)}
        </span>
        <!-- Instruction (truncated) -->
        ${instruction ? html`
          <span class="binding-instruction" style="font-size: var(--font-size-xxs); color: var(--text-muted); flex: 0 1 auto; max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${esc(instruction)}
          </span>
        ` : ''}
        <!-- Expand toggle -->
        <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost expand-binding-btn"
                data-action="toggle-expand-binding"
                data-binding-id="${esc(binding._id)}"
                title="${isExpanded ? 'Collapse details' : 'Expand details'}"
                style="pointer-events: auto; flex-shrink: 0; width: 20px; height: 20px; padding: 0;">
          ${isExpanded ? ICONS.chevronUp : ICONS.chevronDown}
        </button>
      </div>

      <!-- Expanded details (inline) -->
      ${isExpanded ? html`
        <div class="binding-expanded-details"
             style="padding: 0 var(--space-3) var(--space-2) var(--space-3); border-top: 1px solid var(--border-subtle); background: var(--surface-alt); font-size: var(--font-size-xxs); color: var(--text-secondary);">
          <div style="display: grid; grid-template-columns: auto 1fr; gap: 2px var(--space-3); padding: var(--space-2) 0;">
            ${binding.window_match != null ? html`
              <span style="color: var(--text-muted);">Window Match</span>
              <span style="font-family: var(--font-mono); word-break: break-all;">${esc(binding.window_match)}</span>
            ` : ''}
            ${binding.binding_type != null ? html`
              <span style="color: var(--text-muted);">Type</span>
              <span>${esc(bindingTypeLabel(binding.binding_type))}</span>
            ` : ''}
            ${binding.cooldown_seconds != null ? html`
              <span style="color: var(--text-muted);">Cooldown</span>
              <span>${esc(formatCooldown(binding.cooldown_seconds))}</span>
            ` : ''}
            ${instruction ? html`
              <span style="color: var(--text-muted);">Instruction</span>
              <span>${esc(instruction)}</span>
            ` : ''}
          </div>
        </div>
      ` : ''}
    </div>
  `;
}

/**
 * Render the binding detail side panel.
 * Shows full details of the currently selected binding or a placeholder.
 * @returns {string} HTML
 */
function renderDetailPanel() {
  const binding = _state.selectedBinding;

  if (!binding) {
    return html`
      <div class="c-card binding-detail-panel"
           style="padding: var(--space-6); text-align: center; color: var(--text-muted); height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-3);">
        <div style="font-size: 28px; opacity: 0.2;">${ICONS.keyboard}</div>
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium);">Select a binding</div>
        <div style="font-size: var(--font-size-xxs); max-width: 180px; line-height: 1.5;">
          Click any binding in the list to view its full details here.
        </div>
      </div>
    `;
  }

  const keysChips = renderKeyChips(binding.keys);
  const command = binding.command || '';
  const instruction = binding.instruction || '';
  const appName = binding._appName || binding.name || '';
  const windowMatch = binding.window_match;
  const bindingType = binding.binding_type;
  const cooldown = binding.cooldown_seconds;
  const bindingName = binding.name || binding.command || 'Binding';

  return html`
    <div class="c-card binding-detail-panel" style="overflow: hidden;">
      <!-- Detail header -->
      <div style="padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);">
        <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
          <span style="width: 16px; height: 16px; display: inline-flex; color: var(--accent);">${ICONS.keyboard}</span>
          <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary);">
            ${esc(bindingName)}
          </span>
        </div>
        <div style="display: flex; align-items: center; gap: 2px; flex-wrap: wrap;">
          ${html.raw(keysChips.join(''))}
        </div>
      </div>

      <!-- Detail body -->
      <div style="padding: var(--space-3) var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); font-size: var(--font-size-xs);">

        <!-- Command -->
        ${command ? html`
          <div>
            <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.5px;">Command</div>
            <div style="font-family: var(--font-mono); color: var(--text-primary); word-break: break-all; background: var(--surface-alt); padding: var(--space-1) var(--space-2); border-radius: var(--radius-sm);">
              ${esc(command)}
            </div>
          </div>
        ` : ''}

        <!-- Instruction -->
        ${instruction ? html`
          <div>
            <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.5px;">Instruction</div>
            <div style="color: var(--text-secondary); line-height: 1.5;">${esc(instruction)}</div>
          </div>
        ` : ''}

        <!-- Property list -->
        <div style="display: grid; grid-template-columns: auto 1fr; gap: 4px var(--space-3); font-size: var(--font-size-xs);">
          <span style="color: var(--text-muted);">App</span>
          <span style="color: var(--text-primary);">${esc(appName)}</span>

          ${windowMatch != null ? html`
            <span style="color: var(--text-muted);">Window Match</span>
            <span style="font-family: var(--font-mono); font-size: var(--font-size-xxs); color: var(--text-secondary); word-break: break-all;">${esc(windowMatch)}</span>
          ` : ''}

          ${bindingType != null ? html`
            <span style="color: var(--text-muted);">Type</span>
            <span>${esc(bindingTypeLabel(bindingType))}</span>
          ` : ''}

          ${cooldown != null ? html`
            <span style="color: var(--text-muted);">Cooldown</span>
            <span>${esc(formatCooldown(cooldown))}</span>
          ` : ''}
        </div>
      </div>
    </div>
  `;
}

/**
 * Render skeleton loading placeholders.
 * @param {Element} container
 */
function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2); height: 100%; display: flex; flex-direction: column;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--space-4);">
        <div>
          ${skeletonHeading({ width: '200px' })}
          ${skeletonText({ width: '160px' })}
        </div>
        ${skeletonButton({ width: '80px' })}
      </div>
      <div style="margin-bottom: var(--space-4); max-width: 400px;">
        ${skeletonText({ width: '100%' })}
      </div>
      <div style="display: flex; gap: var(--space-4); flex: 1;">
        <div style="flex: 1; display: flex; flex-direction: column; gap: var(--space-3);">
          ${Array.from({ length: 3 }, () => skeletonCard({ height: '120px' }))}
        </div>
        <div style="width: 320px; flex-shrink: 0;">
          ${skeletonCard({ height: '200px' })}
        </div>
      </div>
    </div>
  `;
}

/**
 * Render error state with retry button.
 * @param {Element} container
 */
function renderError(container) {
  container.innerHTML = html`
    <div class="empty-state" style="margin-top: 10vh;">
      <div class="empty-state__icon" style="color: var(--danger);">
        ${ICONS.error}
      </div>
      <div class="empty-state__title">Connection Error</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to fetch bindings from backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="bindings-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  const retryBtn = container.querySelector('#bindings-retry-btn');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      _state.error = false;
      _state.loading = true;
      renderSkeletons(container);
      loadData();
    });
  }
}

/* ── Component Mounting / Event Binding ─────────────────────────────────── */

function mountComponents(container) {
  const listeners = [];

  // Search input
  const searchEl = container.querySelector('#bindings-search-input');
  if (searchEl) {
    const handler = async (e) => {
      _state.searchQuery = e.target.value;
      persistState();
      await renderPage(container);
    };
    searchEl.addEventListener('input', handler);
    listeners.push(() => searchEl.removeEventListener('input', handler));
  }

  // Select binding (click on a binding row)
  const bindingRows = container.querySelectorAll('[data-action="select-binding"]');
  bindingRows.forEach((row) => {
    const handler = async (e) => {
      // Ignore if the click was on the expand button
      if (e.target.closest('[data-action="toggle-expand-binding"]')) return;
      const id = row.dataset.bindingId;
      if (!id) return;
      const binding = _state.rawBindings.find((b) => b._id === id);
      if (binding) {
        if (_state.selectedBinding && _state.selectedBinding._id === id) {
          _state.selectedBinding = null;
        } else {
          _state.selectedBinding = binding;
        }
        await renderPage(container);
      }
    };
    row.addEventListener('click', handler);
    listeners.push(() => row.removeEventListener('click', handler));
  });

  // Toggle inline expand of a binding
  const expandBtns = container.querySelectorAll('[data-action="toggle-expand-binding"]');
  expandBtns.forEach((btn) => {
    const handler = async (e) => {
      e.stopPropagation();
      const id = btn.dataset.bindingId;
      if (!id) return;
      if (_state.expandedBindings.has(id)) {
        _state.expandedBindings.delete(id);
      } else {
        _state.expandedBindings.add(id);
      }
      await renderPage(container);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  // Save button
  const saveBtn = container.querySelector('#bindings-save-btn');
  if (saveBtn) {
    const handler = () => {
      saveBindings();
    };
    saveBtn.addEventListener('click', handler);
    listeners.push(() => saveBtn.removeEventListener('click', handler));
  }

  _state._boundListeners = listeners;
}

/* ── Actions ────────────────────────────────────────────────────────────── */

/**
 * Save the current bindings config back to the backend via POST.
 * Since the UI is read-only, this re-sends the data as it was fetched.
 */
async function saveBindings() {
  if (_state.saving) return;
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  _state.saving = true;
  if (_state.container) await renderPage(_state.container);

  try {
    // Build the payload from the current data
    const apps = _state.rawBindings.map((b) => {
      // Strip internal fields before sending back
      const { _id, _appName, ...rest } = b;
      return rest;
    });

    const payload = {
      apps,
      version: 1,
    };

    const result = await api.post('/api/v1/bindings/save', payload);

    if (result && result.ok) {
      _state.saving = false;
      toast.showToast(
        'success',
        'Bindings Saved',
        result.data?.path
          ? `Saved to ${result.data.path}`
          : 'Key bindings configuration saved successfully.',
      );
    } else {
      const msg =
        (result && result.data && result.data.error) ||
        (result && result.message) ||
        'Unknown error';
      _state.saving = false;
      toast.showToast('error', 'Save Failed', msg);
    }
  } catch (err) {
    console.error('[bindings] Save error:', err);
    _state.saving = false;
    toast.showToast(
      'error',
      'Save Failed',
      err.message || 'Could not save bindings.',
    );
  }

  if (!_state.destroyed && _state.container) {
    await renderPage(_state.container);
  }
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadData() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.error = true;
    _state.errorMessage = 'API client not available.';
    _state.loading = false;
    if (_state.container) await renderPage(_state.container);
    return;
  }

  try {
    const result = await api.get('/api/v1/bindings');

    if (!result || !result.ok) {
      const msg =
        (result && result.data && result.data.error) ||
        (result && result.message) ||
        'Invalid response from backend.';
      throw new Error(msg);
    }

    const rawData = result.data || {};
    const apps = rawData.apps || [];

    // Normalize binding entries
    const bindings = normalizeBindings(apps);

    _state.config = rawData.config || null;
    _state.rawBindings = bindings;
    _state.groupedBindings = groupByApp(bindings);
    _state.appOrder = Object.keys(_state.groupedBindings).sort((a, b) =>
      a.localeCompare(b)
    );

    // Clear stale selections
    _state.selectedBinding = null;
    _state.expandedBindings = new Set();
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  } catch (err) {
    console.error('[bindings] Failed to load bindings:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch bindings.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  }
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Full render — called from outside the router or from mount().
 * @param {Element} container
 */
export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;

  loadPersistedState();
  renderSkeletons(container);
  loadData();
}

/**
 * Mount — called by router after render() inserts HTML.
 * @param {Element} container
 */
export async function mount(container) {
  _state.container = container;
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;

  // Remove bound listeners
  for (const fn of _state._boundListeners) {
    try { fn(); } catch (e) { /* ignore */ }
  }
  _state._boundListeners = [];

  _state.container = null;
  _state.config = null;
  _state.rawBindings = [];
  _state.groupedBindings = {};
  _state.appOrder = [];
  _state.selectedBinding = null;
  _state.expandedBindings = new Set();
  _state.saving = false;
}

/* ── Router-compatible default export ────────────────────────────────────── */

/**
 * Factory function for the SPA router.
 * Returns { render, mount, destroy } lifecycle object.
 * @param {Object} _routeInfo
 * @returns {{ render: Function, mount: Function, destroy: Function }}
 */
export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="bindings-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#bindings-root') || container;
      render(root);
    },
    destroy,
  };
}
