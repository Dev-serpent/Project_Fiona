/* ==========================================================================
   bindings.js — Key Bindings Management Page
   ==========================================================================
   Full CRUD display of QuikTieper application key bindings.
   Provides search/filter, inline expandable details, detail side panel,
   create/edit/delete operations, enable/disable toggle, import/export,
   conflict detection, and category-based grouping/filtering.

   Backend APIs:
     GET  /api/v1/bindings              → { ok, data: { config, apps } }
     GET  /api/v1/bindings/apps         → { ok, data: { apps } }
     POST /api/v1/bindings/save         → { ok, data: { path, saved } }
     POST /api/v1/bindings/create       → { ok, data: { binding, app } }
     POST /api/v1/bindings/update       → { ok, data: { binding, app } }
     DELETE /api/v1/bindings/delete     → { ok, data: { deleted } }
     POST /api/v1/bindings/toggle       → { ok, data: { enabled } }
     GET  /api/v1/bindings/export       → JSON file download
     POST /api/v1/bindings/import       → { ok, data: { count } }
     POST /api/v1/bindings/check-conflicts → { ok, data: { conflicts } }

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
import { modal } from '../js/components/Modal.js';

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
  categoryFilter: '',      // Current category filter value
  groupByCategory: false,  // True = group by category, false = group by app
  categoryNames: [],       // Unique category names extracted from bindings
  working: false,          // Generic busy flag for async operations

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
    const data = {
      searchQuery: _state.searchQuery,
      categoryFilter: _state.categoryFilter,
      groupByCategory: _state.groupByCategory,
    };
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
      _state.categoryFilter = data.categoryFilter || '';
      _state.groupByCategory = data.groupByCategory || false;
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

/**
 * Extract unique category names from all bindings.
 * @param {Array<Object>} bindings
 * @returns {string[]}
 */
function extractCategories(bindings) {
  const cats = new Set();
  for (const b of bindings) {
    if (b.category) cats.add(b.category);
  }
  return Array.from(cats).sort((a, b) => a.localeCompare(b));
}

/**
 * Group a flat array of bindings by category name.
 * Bindings without a category go into "General".
 * @param {Array<Object>} bindings
 * @returns {Object} { categoryName: [binding, ...] }
 */
function groupByCategory(bindings) {
  const groups = {};
  for (const entry of bindings) {
    const cat = entry.category || 'General';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(entry);
  }
  return groups;
}

/**
 * Build a key string from an array of key parts or a keys field.
 * Normalises to a sorted, lower-case, joined string for comparison.
 * @param {string|string[]|Object} keys
 * @returns {string}
 */
function normalizeKeyString(keys) {
  const parts = parseKeys(keys);
  return parts.map((k) => k.toLowerCase().replace(/[^a-z0-9]/g, '')).sort().join('+');
}

/**
 * Serialise the current rawBindings into the config { apps: [...] } format
 * expected by the backend save endpoint.
 * @returns {Object}
 */
function buildConfigPayload() {
  // Group by app
  const appMap = {};
  for (const b of _state.rawBindings) {
    const appName = b._appName || 'Unnamed';
    if (!appMap[appName]) {
      appMap[appName] = { name: appName, window_match: '', launch: {}, shortcuts: [] };
    }
  }
  // Populate launch & shortcuts
  for (const b of _state.rawBindings) {
    const appName = b._appName || 'Unnamed';
    const app = appMap[appName];
    const bindingType = b.binding_type || 'shortcut';
    const shortName = b.name && b.name.includes(':') ? b.name.split(':').slice(1).join(':') : (b.name || 'binding');

    const entry = {
      name: shortName,
      keys: Array.isArray(b.keys) ? b.keys.map((k) => k.toLowerCase()) : [],
      cmd: b.command || '',
      instruction: b.instruction || '',
      fiona_cmds: b.fiona_cmds || [],
      cooldown_seconds: b.cooldown_seconds || 0.8,
      enabled: b.enabled !== false,
      category: b.category || '',
    };

    if (bindingType === 'launch') {
      app.launch = entry;
    } else {
      app.shortcuts.push(entry);
    }
  }
  return { apps: Object.values(appMap) };
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

  // Filter by search query and category
  const query = _state.searchQuery.toLowerCase().trim();
  const catFilter = _state.categoryFilter;

  const filteredBindings = _state.rawBindings.filter((entry) => {
    // Category filter
    if (catFilter && (entry.category || '') !== catFilter) return false;
    // Search query
    if (query) {
      const appName = (entry._appName || '').toLowerCase();
      const keys = (entry.keys || '').toLowerCase();
      const command = (entry.command || '').toLowerCase();
      const instruction = (entry.instruction || '').toLowerCase();
      const name = (entry.name || '').toLowerCase();
      const category = (entry.category || '').toLowerCase();
      return (
        appName.includes(query) ||
        keys.includes(query) ||
        command.includes(query) ||
        instruction.includes(query) ||
        name.includes(query) ||
        category.includes(query)
      );
    }
    return true;
  });

  // Re-group filtered results (by app or by category)
  let filteredGroups, filteredOrder;
  if (_state.groupByCategory) {
    filteredGroups = groupByCategory(filteredBindings);
    filteredOrder = Object.keys(filteredGroups).sort((a, b) =>
      a.localeCompare(b)
    );
  } else {
    filteredGroups = groupByApp(filteredBindings);
    filteredOrder = Object.keys(filteredGroups).sort((a, b) =>
      a.localeCompare(b)
    );
  }

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
          <div style="font-size: var(--font-size-md);">No bindings match${query ? ` &quot;${esc(query)}&quot;` : ''}${catFilter ? ` in category &quot;${esc(catFilter)}&quot;` : ''}</div>
        </div>
      `;
    }
  } else {
    appListContent = html.raw(filteredOrder.map((groupName) =>
      renderAppSection(groupName, filteredGroups[groupName])
    ).join(''));
  }

  const detailPanelContent = renderDetailPanel();

  const saveBtnIcon = _state.saving
    ? html`<span class="c-spinner c-spinner--sm" style="width:14px;height:14px;"></span>`
    : ICONS.check;
  const saveBtnText = _state.saving ? 'Saving&hellip;' : 'Save';

  // Category options for filter dropdown
  const categoryOptions = _state.categoryNames.map((cat) => html`
    <option value="${esc(cat)}" ${_state.categoryFilter === cat ? 'selected' : ''}>${esc(cat)}</option>
  `).join('');

  const groupLabel = _state.groupByCategory ? 'By Category' : 'By App';

  const data = {
    keyboardIcon: ICONS.keyboard.html,
    searchIcon: ICONS.search.html,
    plusIcon: ICONS.plus.html,
    downloadIcon: ICONS.download.html,
    uploadIcon: ICONS.upload.html,
    groupIcon: (_state.groupByCategory ? ICONS.folder : ICONS.terminal).html,
    groupLabel,
    categoryOptions,
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
function renderAppSection(sectionName, bindings) {
  // Determine icon based on grouping mode
  const isCategoryGroup = _state.groupByCategory;
  const sectionIcon = isCategoryGroup ? ICONS.folder : ICONS.terminal;

  return html`
    <div class="c-card binding-app-section" style="margin-bottom: var(--space-3); overflow: hidden;">
      <!-- Section Header -->
      <div class="binding-app-header"
           style="display: flex; align-items: center; justify-content: space-between;
                  padding: var(--space-2) var(--space-3);
                  background: var(--surface);
                  border-bottom: 1px solid var(--border-subtle);
                  cursor: default;
                  user-select: none;">
        <div style="display: flex; align-items: center; gap: var(--space-2); min-width: 0;">
          <span style="width: 16px; height: 16px; display: inline-flex; color: var(--text-muted); flex-shrink: 0;">${sectionIcon}</span>
          <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary);">${esc(sectionName)}</span>
          ${isCategoryGroup ? html`
            <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">category</span>
          ` : ''}
        </div>
        <span class="c-badge" style="font-size: var(--font-size-xxs); padding: 0 6px; line-height: 18px;">
          ${bindings.length}
        </span>
      </div>

      <!-- Binding List -->
      <div class="binding-list" style="padding: 0;">
        ${html.raw(bindings.map((binding, idx) => renderBindingRow(binding, sectionName, idx)).join(''))}
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
  const enabled = binding.enabled !== false;
  const category = binding.category || '';

  return html`
    <div class="binding-row${isSelected ? ' binding-row--selected' : ''}${enabled ? '' : ' binding-row--disabled'}"
         data-binding-id="${esc(binding._id)}"
         style="border-bottom: 1px solid var(--border-subtle);
                cursor: pointer;
                transition: background var(--transition-fast);
                ${isSelected ? 'background: var(--accent-muted);' : ''}
                ${isSelected ? '' : 'background: transparent;'}
                ${enabled ? '' : 'opacity: 0.55;'}"
         data-action="select-binding">
      <!-- Compact row -->
      <div style="display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); min-width: 0;">
        <!-- Toggle -->
        <button class="c-toggle-btn binding-toggle-btn"
                data-action="toggle-binding"
                data-binding-id="${esc(binding._id)}"
                title="${enabled ? 'Disable' : 'Enable'}"
                style="flex-shrink: 0; width: 22px; height: 22px; padding: 0; border: none; background: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; color: ${enabled ? 'var(--success, #22c55e)' : 'var(--text-muted)'};">
          <svg viewBox="0 0 24 24" fill="${enabled ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;">
            <rect x="1" y="5" width="22" height="14" rx="7" ry="7"/>
            <circle cx="${enabled ? '16' : '8'}" cy="12" r="5" fill="${enabled ? 'var(--surface)' : 'currentColor'}"/>
          </svg>
        </button>

        <!-- Key chips -->
        <div style="display: flex; align-items: center; gap: 1px; flex-shrink: 0; min-width: 60px; flex-wrap: wrap;">
          ${html.raw(keysChips.join(''))}
        </div>

        <!-- Disabled badge -->
        ${enabled ? '' : html`
          <span class="c-badge" style="font-size: var(--font-size-xxs); padding: 0 5px; line-height: 16px; background: var(--surface-alt); color: var(--text-muted); border: 1px solid var(--border);">Disabled</span>
        `}

        <!-- Command -->
        <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-primary); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(command)}
        </span>
        <!-- Category badge -->
        ${category ? html`
          <span class="c-badge" style="font-size: var(--font-size-xxs); padding: 0 5px; line-height: 16px; background: var(--accent-muted); color: var(--accent); border: 1px solid var(--accent);">${esc(category)}</span>
        ` : ''}
        <!-- Instruction (truncated) -->
        ${instruction ? html`
          <span class="binding-instruction" style="font-size: var(--font-size-xxs); color: var(--text-muted); flex: 0 1 auto; max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${esc(instruction)}
          </span>
        ` : ''}
        <!-- Action buttons -->
        <div style="display: flex; align-items: center; gap: 2px; flex-shrink: 0;">
          <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost binding-edit-btn"
                  data-action="edit-binding"
                  data-binding-id="${esc(binding._id)}"
                  title="Edit binding"
                  style="pointer-events: auto; width: 20px; height: 20px; padding: 0;">
            ${ICONS.edit}
          </button>
          <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost binding-delete-btn"
                  data-action="delete-binding"
                  data-binding-id="${esc(binding._id)}"
                  title="Delete binding"
                  style="pointer-events: auto; width: 20px; height: 20px; padding: 0; color: var(--danger, #ef4444);">
            ${ICONS.trash}
          </button>
        </div>
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
            ${category ? html`
              <span style="color: var(--text-muted);">Category</span>
              <span>${esc(category)}</span>
            ` : ''}
            ${binding.enabled !== undefined ? html`
              <span style="color: var(--text-muted);">Status</span>
              <span style="color: ${enabled ? 'var(--success, #22c55e)' : 'var(--text-muted)'};">${enabled ? 'Active' : 'Disabled'}</span>
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
  const enabled = binding.enabled !== false;
  const category = binding.category || '';

  return html`
    <div class="c-card binding-detail-panel" style="overflow: hidden;">
      <!-- Detail header -->
      <div style="padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);">
        <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
          <span style="width: 16px; height: 16px; display: inline-flex; color: var(--accent);">${ICONS.keyboard}</span>
          <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary);">
            ${esc(bindingName)}
          </span>
          ${enabled ? '' : html`
            <span class="c-badge" style="font-size: var(--font-size-xxs); padding: 0 5px; line-height: 16px; background: var(--surface-alt); color: var(--text-muted); border: 1px solid var(--border);">Disabled</span>
          `}
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

          ${category ? html`
            <span style="color: var(--text-muted);">Category</span>
            <span>${esc(category)}</span>
          ` : ''}

          <span style="color: var(--text-muted);">Status</span>
          <span style="color: ${enabled ? 'var(--success, #22c55e)' : 'var(--text-muted)'}; display: flex; align-items: center; gap: 4px;">
            <span style="width: 8px; height: 8px; border-radius: 50%; display: inline-block; background: ${enabled ? 'var(--success, #22c55e)' : 'var(--text-muted)'};"></span>
            ${enabled ? 'Active' : 'Disabled'}
          </span>
        </div>

        <!-- Detail action buttons -->
        <div style="display: flex; gap: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-subtle);">
          <button class="c-btn c-btn--sm c-btn--ghost binding-toggle-btn"
                  data-action="toggle-binding"
                  data-binding-id="${esc(binding._id)}"
                  style="flex: 1;">
            ${enabled ? 'Disable' : 'Enable'}
          </button>
          <button class="c-btn c-btn--sm c-btn--ghost"
                  data-action="edit-binding"
                  data-binding-id="${esc(binding._id)}"
                  style="flex: 1;">
            <span class="c-btn__icon">${ICONS.edit}</span>
            Edit
          </button>
          <button class="c-btn c-btn--sm c-btn--ghost"
                  data-action="delete-binding"
                  data-binding-id="${esc(binding._id)}"
                  style="flex: 1; color: var(--danger, #ef4444);">
            <span class="c-btn__icon">${ICONS.trash}</span>
            Delete
          </button>
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

  // Category filter
  const catFilter = container.querySelector('#bindings-category-filter');
  if (catFilter) {
    const handler = async (e) => {
      _state.categoryFilter = e.target.value;
      await renderPage(container);
    };
    catFilter.addEventListener('change', handler);
    listeners.push(() => catFilter.removeEventListener('change', handler));
  }

  // Group toggle (by app / by category)
  const groupToggle = container.querySelector('#bindings-group-toggle');
  if (groupToggle) {
    const handler = async () => {
      _state.groupByCategory = !_state.groupByCategory;
      await renderPage(container);
    };
    groupToggle.addEventListener('click', handler);
    listeners.push(() => groupToggle.removeEventListener('click', handler));
  }

  // Select binding (click on a binding row) — skip clicks on action buttons
  const bindingRows = container.querySelectorAll('[data-action="select-binding"]');
  bindingRows.forEach((row) => {
    const handler = async (e) => {
      // Ignore clicks on action buttons, toggle, expand
      if (e.target.closest('[data-action="toggle-expand-binding"]')) return;
      if (e.target.closest('[data-action="toggle-binding"]')) return;
      if (e.target.closest('[data-action="edit-binding"]')) return;
      if (e.target.closest('[data-action="delete-binding"]')) return;
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

  // Toggle binding enable/disable
  const toggleBtns = container.querySelectorAll('[data-action="toggle-binding"]');
  toggleBtns.forEach((btn) => {
    const handler = async (e) => {
      e.stopPropagation();
      const id = btn.dataset.bindingId;
      if (!id) return;
      await handleToggleBinding(id);
      await renderPage(container);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  // Edit binding
  const editBtns = container.querySelectorAll('[data-action="edit-binding"]');
  editBtns.forEach((btn) => {
    const handler = async (e) => {
      e.stopPropagation();
      const id = btn.dataset.bindingId;
      if (!id) return;
      await handleEditBinding(id);
      await renderPage(container);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  // Delete binding
  const deleteBtns = container.querySelectorAll('[data-action="delete-binding"]');
  deleteBtns.forEach((btn) => {
    const handler = async (e) => {
      e.stopPropagation();
      const id = btn.dataset.bindingId;
      if (!id) return;
      await handleDeleteBinding(id);
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

  // Create button
  const createBtn = container.querySelector('#bindings-create-btn');
  if (createBtn) {
    const handler = async () => {
      await handleCreateBinding();
      await renderPage(container);
    };
    createBtn.addEventListener('click', handler);
    listeners.push(() => createBtn.removeEventListener('click', handler));
  }

  // Export button
  const exportBtn = container.querySelector('#bindings-export-btn');
  if (exportBtn) {
    const handler = () => {
      handleExportBindings();
    };
    exportBtn.addEventListener('click', handler);
    listeners.push(() => exportBtn.removeEventListener('click', handler));
  }

  // Import button
  const importBtn = container.querySelector('#bindings-import-btn');
  const importInput = container.querySelector('#bindings-import-input');
  if (importBtn && importInput) {
    const clickHandler = () => {
      importInput.click();
    };
    importBtn.addEventListener('click', clickHandler);
    listeners.push(() => importBtn.removeEventListener('click', clickHandler));

    const changeHandler = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      await handleImportBindings(file);
      importInput.value = '';
      await renderPage(container);
    };
    importInput.addEventListener('change', changeHandler);
    listeners.push(() => importInput.removeEventListener('change', changeHandler));
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

/* ── CRUD: Create / Edit / Delete / Toggle ──────────────────────────────── */

/**
 * Show the create binding modal and handle submission.
 */
async function handleCreateBinding() {
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  const data = await showBindingFormModal(null);
  if (!data) return; // cancelled

  // Check for conflicts
  const conflicts = await checkConflicts(data.keys, null);
  if (conflicts.length > 0) {
    const override = await showConflictModal(conflicts);
    if (!override) return; // user cancelled
  }

  try {
    const result = await api.post('/api/v1/bindings/create', data);
    if (result && result.ok) {
      toast.showToast('success', 'Created', `Binding "${data.name}" created.`);
      await loadData();
    } else {
      const msg = (result && result.data && result.data.error) || (result && result.message) || 'Unknown error';
      toast.showToast('error', 'Create Failed', msg);
    }
  } catch (err) {
    console.error('[bindings] Create error:', err);
    toast.showToast('error', 'Create Failed', err.message || 'Could not create binding.');
  }
}

/**
 * Show the edit binding modal and handle submission.
 * @param {string} bindingId
 */
async function handleEditBinding(bindingId) {
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  const binding = _state.rawBindings.find((b) => b._id === bindingId);
  if (!binding) {
    toast.showToast('error', 'Error', 'Binding not found.');
    return;
  }

  // Preserve original name for backend lookup (in case user renamed it)
  const origShortName = binding.name && binding.name.includes(':')
    ? binding.name.split(':').slice(1).join(':')
    : binding.name || '';
  const data = await showBindingFormModal(binding);
  if (!data) return; // cancelled

  // Add original identifier for backend lookup
  data.origName = origShortName;

  // Check for conflicts (excluding this binding)
  const conflicts = await checkConflicts(data.keys, { app: binding._appName, name: binding.name });
  if (conflicts.length > 0) {
    const override = await showConflictModal(conflicts);
    if (!override) return;
  }

  try {
    const result = await api.post('/api/v1/bindings/update', data);
    if (result && result.ok) {
      toast.showToast('success', 'Updated', `Binding "${data.name}" updated.`);
      await loadData();
    } else {
      const msg = (result && result.data && result.data.error) || (result && result.message) || 'Unknown error';
      toast.showToast('error', 'Update Failed', msg);
    }
  } catch (err) {
    console.error('[bindings] Update error:', err);
    toast.showToast('error', 'Update Failed', err.message || 'Could not update binding.');
  }
}

/**
 * Show delete confirmation and handle deletion.
 * @param {string} bindingId
 */
async function handleDeleteBinding(bindingId) {
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  const binding = _state.rawBindings.find((b) => b._id === bindingId);
  if (!binding) {
    toast.showToast('error', 'Error', 'Binding not found.');
    return;
  }

  const confirmed = await modal.showModal({
    title: 'Delete Binding',
    content: html`
      <p style="color: var(--text-secondary); line-height: 1.5;">
        Are you sure you want to delete the binding
        <strong style="color: var(--text-primary);">${esc(binding.name || binding.command)}</strong>?
      </p>
      <p style="color: var(--text-muted); font-size: var(--font-size-xs); margin-top: var(--space-2);">
        App: ${esc(binding._appName)} &middot;
        Keys: ${esc(Array.isArray(binding.keys) ? binding.keys.join(' + ') : binding.keys)}
      </p>
    `,
    size: 'sm',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Delete', value: 'delete', variant: 'danger' },
    ],
  });

  if (confirmed !== 'delete') return;

  _state.working = true;
  if (_state.container) await renderPage(_state.container);

  try {
    const result = await api.del('/api/v1/bindings/delete', {
      body: {
        app: binding._appName,
        name: binding.name,
      },
    });
    if (result && result.ok) {
      toast.showToast('success', 'Deleted', `Binding "${binding.name}" deleted.`);
      _state.selectedBinding = null;
      await loadData();
    } else {
      const msg = (result && result.data && result.data.error) || (result && result.message) || 'Unknown error';
      toast.showToast('error', 'Delete Failed', msg);
    }
  } catch (err) {
    console.error('[bindings] Delete error:', err);
    toast.showToast('error', 'Delete Failed', err.message || 'Could not delete binding.');
  }

  _state.working = false;
  if (_state.container) await renderPage(_state.container);
}

/**
 * Toggle a binding's enabled/disabled state.
 * @param {string} bindingId
 */
async function handleToggleBinding(bindingId) {
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  const binding = _state.rawBindings.find((b) => b._id === bindingId);
  if (!binding) return;

  const newEnabled = binding.enabled === false;

  try {
    const result = await api.post('/api/v1/bindings/toggle', {
      app: binding._appName,
      name: binding.name,
      enabled: newEnabled,
    });
    if (result && result.ok) {
      binding.enabled = newEnabled;
      toast.showToast('success', newEnabled ? 'Enabled' : 'Disabled',
        `Binding "${binding.name}" ${newEnabled ? 'enabled' : 'disabled'}.`);
    } else {
      const msg = (result && result.data && result.data.error) || (result && result.message) || 'Unknown error';
      toast.showToast('error', 'Toggle Failed', msg);
    }
  } catch (err) {
    console.error('[bindings] Toggle error:', err);
    toast.showToast('error', 'Toggle Failed', err.message || 'Could not toggle binding.');
  }
}


/* ── Import / Export ────────────────────────────────────────────────────── */

/**
 * Export bindings as a JSON file download.
 */
async function handleExportBindings() {
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  try {
    // Use raw API fetch if available, otherwise use GET
    const response = await fetch('/api/v1/bindings/export');
    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fiona-bindings.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.showToast('success', 'Exported', 'Bindings exported as JSON.');
  } catch (err) {
    console.error('[bindings] Export error:', err);
    toast.showToast('error', 'Export Failed', err.message || 'Could not export bindings.');
  }
}

/**
 * Import bindings from a JSON file.
 * @param {File} file
 */
async function handleImportBindings(file) {
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  try {
    const text = await file.text();
    let json;
    try {
      json = JSON.parse(text);
    } catch (e) {
      toast.showToast('error', 'Import Failed', 'Invalid JSON file.');
      return;
    }

    // Validate basic structure
    if (!json || !json.apps || !Array.isArray(json.apps)) {
      // Try wrapping if the file contains a flat bindings array
      if (Array.isArray(json)) {
        json = { apps: json };
      } else {
        toast.showToast('error', 'Import Failed',
          'JSON must contain an "apps" array. See export format.');
        return;
      }
    }

    // Confirm before replacing
    const confirmed = await modal.showModal({
      title: 'Import Bindings',
      content: html`
        <p style="color: var(--text-secondary); line-height: 1.5;">
          This will <strong style="color: var(--text-primary);">replace</strong> all existing bindings
          with the imported data. This action cannot be undone.
        </p>
        <p style="color: var(--text-muted); font-size: var(--font-size-xs);">
          File: ${esc(file.name)}
        </p>
      `,
      size: 'sm',
      buttons: [
        { label: 'Cancel', value: 'cancel', variant: 'ghost' },
        { label: 'Import', value: 'import', variant: 'primary' },
      ],
    });

    if (confirmed !== 'import') return;

    _state.working = true;
    if (_state.container) await renderPage(_state.container);

    const result = await api.post('/api/v1/bindings/import', json);
    if (result && result.ok) {
      toast.showToast('success', 'Imported',
        `${result.data?.count || '?'} binding(s) imported successfully.`);
      await loadData();
    } else {
      const msg = (result && result.data && result.data.error) || (result && result.message) || 'Unknown error';
      toast.showToast('error', 'Import Failed', msg);
    }
  } catch (err) {
    console.error('[bindings] Import error:', err);
    toast.showToast('error', 'Import Failed', err.message || 'Could not import bindings.');
  }

  _state.working = false;
  if (_state.container) await renderPage(_state.container);
}


/* ── Conflict Detection ─────────────────────────────────────────────────── */

/**
 * Check for key combo conflicts with existing bindings.
 * @param {string[]|string} keys
 * @param {Object|null} exclude - { app, name } to exclude from check
 * @returns {Promise<Array>} Array of conflicting binding objects
 */
async function checkConflicts(keys, exclude) {
  const api = getApi();
  if (!api) return [];

  try {
    const keysArray = Array.isArray(keys) ? keys : (typeof keys === 'string' ? keys.split('+').map(k => k.trim()) : []);
    if (keysArray.length === 0) return [];

    const payload = { keys: keysArray };
    if (exclude) {
      payload.exclude = exclude;
    }

    const result = await api.post('/api/v1/bindings/check-conflicts', payload);
    if (result && result.ok && result.data) {
      return result.data.conflicts || [];
    }
    return [];
  } catch (err) {
    console.error('[bindings] Conflict check error:', err);
    return [];
  }
}

/**
 * Show a conflict warning modal allowing the user to override.
 * @param {Array} conflicts
 * @returns {Promise<boolean>} true if user chooses to override
 */
async function showConflictModal(conflicts) {
  const conflictList = conflicts.map((c) => html`
    <div style="display: flex; align-items: center; gap: var(--space-2); padding: 4px 0; font-size: var(--font-size-xs); border-bottom: 1px solid var(--border-subtle);">
      <span style="width: 16px; height: 16px; flex-shrink: 0; color: var(--warning, #f59e0b);">${ICONS.warning}</span>
      <span style="flex: 1; min-width: 0;">
        <strong>${esc(c.app || c._appName || '?')}</strong>:
        ${esc(c.name || '?')}
      </span>
      <span style="font-family: var(--font-mono); color: var(--text-muted); font-size: var(--font-size-xxs);">
        ${esc(Array.isArray(c.keys) ? c.keys.join(' + ') : c.keys)}
      </span>
    </div>
  `).join('');

  const result = await modal.showModal({
    title: 'Key Conflict Detected',
    content: html`
      <p style="color: var(--text-secondary); line-height: 1.5; margin-bottom: var(--space-3);">
        The following binding(s) already use this key combination:
      </p>
      <div style="max-height: 200px; overflow-y: auto;">
        ${html.raw(conflictList)}
      </div>
      <p style="color: var(--text-muted); font-size: var(--font-size-xs); margin-top: var(--space-3);">
        You can still save this binding, but the conflicting bindings will share the same keys.
      </p>
    `,
    size: 'md',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Save Anyway', value: 'override', variant: 'warning' },
    ],
  });

  return result === 'override';
}


/* ── Create / Edit Form Modal ────────────────────────────────────────────── */

/**
 * Show the create/edit binding form modal.
 * @param {Object|null} binding - Existing binding to edit, or null for create
 * @returns {Promise<Object|null>} Form data object, or null if cancelled
 */
function showBindingFormModal(binding) {
  return new Promise((resolve) => {
    const isEdit = !!binding;
    const appName = binding ? binding._appName : '';
    const shortName = binding && binding.name ? (binding.name.includes(':') ? binding.name.split(':').slice(1).join(':') : binding.name) : '';
    const keysStr = binding ? (Array.isArray(binding.keys) ? binding.keys.join(' + ') : (binding.keys || '')) : '';
    const command = binding ? (binding.command || '') : '';
    const description = binding ? (binding.instruction || binding.description || '') : '';
    const category = binding ? (binding.category || '') : '';
    const enabled = binding ? (binding.enabled !== false) : true;

    const formId = 'binding-form-' + Date.now();

    const content = html`
      <form id="${formId}" class="binding-form" style="display: flex; flex-direction: column; gap: var(--space-3);">
        <div>
          <label style="display: block; font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: 4px;">
            App Name <span style="color: var(--danger);">*</span>
          </label>
          <input type="text" class="c-input" name="app"
                 value="${esc(appName)}"
                 placeholder="e.g. brave, vscode, terminal"
                 required
                 style="width: 100%; height: 34px; font-size: var(--font-size-sm);" />
        </div>
        <div>
          <label style="display: block; font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: 4px;">
            Binding Name <span style="color: var(--danger);">*</span>
          </label>
          <input type="text" class="c-input" name="name"
                 value="${esc(shortName)}"
                 placeholder="e.g. search, new-tab, open-file"
                 required
                 style="width: 100%; height: 34px; font-size: var(--font-size-sm);" />
        </div>
        <div>
          <label style="display: block; font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: 4px;">
            Keys / Chord <span style="color: var(--danger);">*</span>
          </label>
          <input type="text" class="c-input" name="keys"
                 value="${esc(keysStr)}"
                 placeholder="e.g. alt + s or Ctrl + Shift + T"
                 required
                 style="width: 100%; height: 34px; font-size: var(--font-size-sm); font-family: var(--font-mono);" />
          <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 2px;">
            Separate key names with <code>+</code> (e.g. <code>alt + s</code>)
          </div>
        </div>
        <div>
          <label style="display: block; font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: 4px;">
            Command <span style="color: var(--danger);">*</span>
          </label>
          <input type="text" class="c-input" name="command"
                 value="${esc(command)}"
                 placeholder="e.g. ydotool key 29:1 33:1 33:0 29:0"
                 required
                 style="width: 100%; height: 34px; font-size: var(--font-size-sm); font-family: var(--font-mono);" />
        </div>
        <div>
          <label style="display: block; font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: 4px;">
            Description
          </label>
          <textarea class="c-input" name="description"
                    placeholder="Optional description or instruction"
                    style="width: 100%; min-height: 54px; font-size: var(--font-size-sm); resize: vertical;">${esc(description)}</textarea>
        </div>
        <div>
          <label style="display: block; font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: 4px;">Category</label>
          <select class="c-input" name="category" style="width: 100%; height: 34px; font-size: var(--font-size-sm);">
            <option value="">General</option>
            <option value="Navigation" ${category === 'Navigation' ? 'selected' : ''}>Navigation</option>
            <option value="Editing" ${category === 'Editing' ? 'selected' : ''}>Editing</option>
            <option value="System" ${category === 'System' ? 'selected' : ''}>System</option>
            <option value="Custom" ${category === 'Custom' ? 'selected' : ''}>Custom</option>
            ${_state.categoryNames.filter((c) => !['Navigation', 'Editing', 'System', 'Custom', ''].includes(c)).map((c) => html`
              <option value="${esc(c)}" ${category === c ? 'selected' : ''}>${esc(c)}</option>
            `).join('')}
          </select>
        </div>
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <label class="c-toggle" style="display: flex; align-items: center; gap: var(--space-2); cursor: pointer; font-size: var(--font-size-xs); color: var(--text-secondary);">
            <input type="checkbox" name="enabled" value="1" ${enabled ? 'checked' : ''} style="accent-color: var(--accent);" />
            Enabled
          </label>
        </div>
      </form>
      <div style="display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); padding-top: var(--space-2); border-top: 1px solid var(--border);">
        <button class="c-btn c-btn--ghost" data-action="binding-cancel">Cancel</button>
        <button class="c-btn c-btn--primary" data-action="binding-save">
          ${isEdit ? 'Update Binding' : 'Create Binding'}
        </button>
      </div>
    `;

    modal.showModal({
      title: isEdit ? 'Edit Binding' : 'Create Binding',
      content,
      size: 'md',
      closeable: false,
      closeOnBackdrop: false,
      closeOnEscape: false,
      buttons: [], // We use our own buttons inside the content
    });

    // After modal renders, attach form handlers
    requestAnimationFrame(() => {
      const container = document.getElementById('modal-container');
      const form = container.querySelector(`#${formId}`);
      const saveBtn = container.querySelector('[data-action="binding-save"]');
      const cancelBtn = container.querySelector('[data-action="binding-cancel"]');

      if (!form || !saveBtn || !cancelBtn) return;

      saveBtn.addEventListener('click', () => {
        const fd = new FormData(form);

        // Build keys array from the key string
        const keysRaw = (fd.get('keys') || '').trim();
        const app = (fd.get('app') || '').trim();
        const name = (fd.get('name') || '').trim();
        const commandVal = (fd.get('command') || '').trim();

        // Validate required fields
        if (!app) {
          toast.showToast('warning', 'Validation', 'App name is required.');
          return;
        }
        if (!name) {
          toast.showToast('warning', 'Validation', 'Binding name is required.');
          return;
        }
        if (!keysRaw) {
          toast.showToast('warning', 'Validation', 'Keys/chord is required.');
          return;
        }
        if (!commandVal) {
          toast.showToast('warning', 'Validation', 'Command is required.');
          return;
        }

        // Parse keys: split by '+' delimiter, trim each part
        const keysList = keysRaw.split('+').map((k) => k.trim().toLowerCase()).filter(Boolean);

        const formData = {
          app,
          name,
          keys: keysList,
          command: commandVal,
          description: (fd.get('description') || '').trim(),
          category: fd.get('category') || '',
          enabled: fd.get('enabled') === '1',
        };

        modal.closeModal();
        resolve(formData);
      });

      cancelBtn.addEventListener('click', () => {
        modal.closeModal();
        resolve(null);
      });

      // Handle Enter key in form fields
      form.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          saveBtn.click();
        }
      });

      // Focus first field
      const firstInput = form.querySelector('input');
      if (firstInput) setTimeout(() => firstInput.focus(), 100);
    });
  });
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
    const result = await api.get('/api/v1/bindings?parsed=true');

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

    // Extract categories
    _state.categoryNames = extractCategories(bindings);

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
  _state.categoryFilter = '';
  _state.groupByCategory = false;
  _state.categoryNames = [];
  _state.working = false;
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
