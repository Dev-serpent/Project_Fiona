/* ==========================================================================
   macros.js — Macro Runner Page
   ==========================================================================
   Displays defined macros with expandable step lists, run/dry-run execution,
   and inline result display.  Supports search/filter by macro name.

   Backend APIs:
     GET  /api/v1/macros      → { ok, data: { macroName: [steps] } }
     POST /api/v1/macros/run  → { ok, data: [{ step, command, returncode, stdout, stderr }] }

   Exports: { render(container?), mount(container), destroy() }
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';
import { toast } from '../js/components/Toast.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const STORAGE_KEY = 'fiona_macros_state';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  // Raw data: { macroName: [{ step, command, ... }, ...] }
  macros: {},
  // Processed: [{ name, steps }]
  macrosArray: [],

  // UI state
  expanded: new Set(),
  searchQuery: '',

  // Per-macro execution results: { name: { loading, data, error } }
  results: {},

  // Per-macro dry-run toggle: { name: true/false }
  dryRunEnabled: {},

  _boundListeners: [],
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

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

function persistState() {
  try {
    const data = { searchQuery: _state.searchQuery };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    // Silently fail
  }
}

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
  const filtered = query
    ? _state.macrosArray.filter((entry) =>
        entry.name.toLowerCase().includes(query)
      )
    : _state.macrosArray;

  const totalCount = _state.macrosArray.length;

  // Build macros list content
  let macrosListContent = '';
  if (filtered.length === 0) {
    if (totalCount === 0) {
      macrosListContent = renderEmptyState();
    } else {
      macrosListContent = html`
        <div style="text-align: center; padding: var(--space-8); color: var(--text-muted);">
          <div style="font-size: 28px; margin-bottom: var(--space-3); opacity: 0.3;">${ICONS.search}</div>
          <div style="font-size: var(--font-size-md);">No macros match "${esc(query)}"</div>
        </div>
      `;
    }
  } else {
    macrosListContent = filtered.map((entry) => renderMacroCard(entry)).join('');
  }

  const data = {
    searchIcon: ICONS.search.html,
    searchQuery: esc(_state.searchQuery),
    hasTotalCount: totalCount > 0,
    totalCount,
    singular: totalCount === 1,
    macrosListContent,
  };

  container.innerHTML = await loadTemplate('macros', data);
  mountComponents(container);
}

function renderEmptyState() {
  return html`
    <div style="text-align: center; padding: var(--space-12); color: var(--text-muted);">
      <div style="font-size: 36px; margin-bottom: var(--space-4); opacity: 0.3;">${ICONS.play}</div>
      <div style="font-size: var(--font-size-md); font-weight: var(--font-weight-medium); margin-bottom: var(--space-2);">No macros defined</div>
      <div style="font-size: var(--font-size-sm); color: var(--text-muted);">Create a macro to see it here.</div>
    </div>
  `;
}

function renderMacroCard(entry) {
  const { name, steps } = entry;
  const isExpanded = _state.expanded.has(name);
  const stepCount = Array.isArray(steps) ? steps.length : 0;
  const result = _state.results[name];
  const hasResult = result && result.data && !result.loading;
  const isLoading = result && result.loading;
  const isDryRun = _state.dryRunEnabled[name] || false;
  const hasError = result && result.error && !result.loading;

  return html`
    <div class="c-card macro-card" data-macro-name="${esc(name)}" style="margin-bottom: var(--space-3);">
      <!-- Card Header — always visible, clickable to expand -->
      <div class="c-card__header macro-card-header"
           style="cursor: pointer; display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) var(--space-4);"
           data-action="toggle-expand" data-macro-name="${esc(name)}">
        <div style="display: flex; align-items: center; gap: var(--space-3); min-width: 0;">
          <div style="width: 32px; height: 32px; display: grid; place-items: center; border-radius: var(--radius-md); background: var(--accent-muted); color: var(--accent); flex-shrink: 0;">
            ${ICONS.play}
          </div>
          <div style="min-width: 0;">
            <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary);">
              ${esc(name)}
            </div>
            <div style="font-size: var(--font-size-xxs); color: var(--text-muted);">
              ${stepCount} step${stepCount !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0;">
          ${isLoading ? html`<span class="c-spinner" style="width: 16px; height: 16px;"></span>` : ''}
          <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost expand-btn"
                  data-action="toggle-expand" data-macro-name="${esc(name)}"
                  title="${isExpanded ? 'Collapse' : 'Expand'}"
                  style="pointer-events: none;">
            ${isExpanded ? ICONS.chevronUp : ICONS.chevronDown}
          </button>
        </div>
      </div>

      <!-- Expandable Content -->
      ${isExpanded ? html`
        <div class="macro-expanded-content">
          <!-- Steps List -->
          <div class="c-card__body" style="padding-top: 0; padding-bottom: var(--space-3);">
            ${stepCount > 0 ? html`
              <div style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-muted); margin-bottom: var(--space-2);">
                Steps
              </div>
              ${html.raw(steps.map((step, idx) => renderStepItem(step, idx)).join(''))}
            ` : html`
              <div style="font-size: var(--font-size-xs); color: var(--text-muted); padding: var(--space-2) 0;">
                No steps defined.
              </div>
            `}
          </div>

          <!-- Action Buttons -->
          <div class="c-card__footer" style="border-top: 1px solid var(--border-subtle); padding: var(--space-3) var(--space-4);">
            <div style="display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap;">
              <button class="c-btn c-btn--primary c-btn--sm macro-run-btn"
                      data-action="run-macro" data-macro-name="${esc(name)}"
                      ${isLoading ? 'disabled' : ''}>
                <span class="c-btn__icon">${isLoading ? html`<span class="c-spinner c-spinner--sm"></span>` : ICONS.play}</span>
                ${isDryRun ? 'Preview' : 'Run'}
              </button>

              <label style="display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--text-muted); cursor: pointer; user-select: none;">
                <input type="checkbox" class="macro-dryrun-toggle" data-macro-name="${esc(name)}"
                       ${isDryRun ? 'checked' : ''}
                       style="accent-color: var(--accent);" />
                Dry Run
              </label>

              <button class="c-btn c-btn--sm c-btn--ghost macro-dryrun-btn"
                      data-action="dryrun-macro" data-macro-name="${esc(name)}"
                      ${isLoading ? 'disabled' : ''}>
                <span class="c-btn__icon">${ICONS.eye}</span>
                Dry Run
              </button>

              ${isLoading ? html`
                <span style="font-size: var(--font-size-xs); color: var(--text-muted); display: flex; align-items: center; gap: var(--space-1);">
                  <span class="c-spinner c-spinner--sm"></span>
                  Running…
                </span>
              ` : ''}
            </div>
          </div>

          <!-- Results Section -->
          ${hasResult ? html`
            <div style="border-top: 1px solid var(--border-subtle);">
              ${html.raw(renderResults(result.data, name))}
            </div>
          ` : ''}

          ${hasError ? html`
            <div class="c-card__body" style="border-top: 1px solid var(--border-subtle); color: var(--danger); font-size: var(--font-size-sm); padding-top: var(--space-3);">
              <div style="display: flex; align-items: center; gap: var(--space-2);">
                ${ICONS.error}
                <span>${esc(result.error)}</span>
              </div>
            </div>
          ` : ''}
        </div>
      ` : ''}
    </div>
  `;
}

function renderStepItem(step, idx) {
  const stepNum = step.step || step.step_number || (idx + 1);
  const command = step.command || '';
  const description = step.description || step.desc || '';

  return html`
    <div style="display: flex; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--border-subtle); align-items: flex-start;">
      <span class="c-badge" style="flex-shrink: 0; min-width: 24px; text-align: center; font-size: var(--font-size-xxs);">${stepNum}</span>
      <div style="min-width: 0; flex: 1;">
        <div style="font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--text-primary); white-space: pre-wrap; word-break: break-all;">
          ${esc(command)}
        </div>
        ${description ? html`
          <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 2px;">
            ${esc(description)}
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function renderResults(data, macroName) {
  const steps = Array.isArray(data) ? data : [];

  if (steps.length === 0) {
    return html`
      <div class="c-card__body macro-results" style="padding: var(--space-3); background: var(--surface-alt);">
        <div style="font-size: var(--font-size-xs); color: var(--text-muted);">No output returned.</div>
      </div>
    `;
  }

  return html`
    <div class="c-card__body macro-results" style="padding-top: var(--space-3); padding-bottom: var(--space-3); background: var(--surface-alt);">
      <div style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-muted); margin-bottom: var(--space-2);">
        Results
      </div>
      ${html.raw(steps.map((step, idx) => renderResultRow(step, idx)).join(''))}
    </div>
  `;
}

function renderResultRow(step, idx) {
  const returnCode = step.returncode != null ? step.returncode : step.return_code;
  const command = step.command || '';
  const stdout = step.stdout || '';
  const stderr = step.stderr || '';
  const isSuccess = returnCode === 0;
  const stepLabel = step.step || step.step_number || (idx + 1);
  const stdoutLines = stdout ? stdout.split('\n').length : 0;
  const stderrLines = stderr ? stderr.split('\n').length : 0;

  return html`
    <div style="margin-bottom: var(--space-2); padding: var(--space-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--surface);">
      <!-- Result Header -->
      <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
        <span class="c-badge c-badge--${isSuccess ? 'success' : 'danger'}" style="flex-shrink: 0; display: flex; align-items: center; gap: 2px; font-size: var(--font-size-xxs);">
          ${isSuccess ? ICONS.check : ICONS.close}
          ${returnCode}
        </span>
        <span style="font-family: var(--font-mono); font-size: var(--font-size-xs); color: var(--text-primary); flex: 1; white-space: pre-wrap; word-break: break-all;">
          ${esc(command)}
        </span>
        <span style="font-size: var(--font-size-xxs); color: var(--text-muted); flex-shrink: 0;">Step ${esc(String(stepLabel))}</span>
      </div>

      <!-- Stdout -->
      ${stdout ? html`
        <details style="margin-top: var(--space-1);">
          <summary style="font-size: var(--font-size-xxs); color: var(--text-muted); cursor: pointer; padding: 2px 0; user-select: none;">
            stdout (${stdoutLines} line${stdoutLines !== 1 ? 's' : ''})
          </summary>
          <pre style="margin: var(--space-1) 0 0 0; padding: var(--space-2); background: var(--surface-alt); border-radius: var(--radius-sm); font-size: var(--font-size-xxs); max-height: 200px; overflow: auto; white-space: pre-wrap; word-break: break-all; color: var(--text-secondary);">${esc(stdout)}</pre>
        </details>
      ` : ''}

      <!-- Stderr -->
      ${stderr ? html`
        <details style="margin-top: var(--space-1);">
          <summary style="font-size: var(--font-size-xxs); color: ${isSuccess ? 'var(--text-muted)' : 'var(--danger)'}; cursor: pointer; padding: 2px 0; user-select: none;">
            stderr (${stderrLines} line${stderrLines !== 1 ? 's' : ''})
          </summary>
          <pre style="margin: var(--space-1) 0 0 0; padding: var(--space-2); background: var(--surface-alt); border-radius: var(--radius-sm); font-size: var(--font-size-xxs); max-height: 200px; overflow: auto; white-space: pre-wrap; word-break: break-all; color: var(--danger);">${esc(stderr)}</pre>
        </details>
      ` : ''}
    </div>
  `;
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-5);">
        ${skeletonHeading({ width: '200px' })}
        ${skeletonText({ width: '140px' })}
      </div>
      <div style="margin-bottom: var(--space-4); max-width: 360px;">
        ${skeletonText({ width: '100%' })}
      </div>
      ${Array.from({ length: 3 }, () => skeletonCard({ height: '72px' }))}
    </div>
  `;
}

function renderError(container) {
  container.innerHTML = html`
    <div class="empty-state" style="margin-top: 10vh;">
      <div class="empty-state__icon" style="color: var(--danger);">
        ${ICONS.error}
      </div>
      <div class="empty-state__title">Connection Error</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to fetch macros from backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="macros-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  const retryBtn = container.querySelector('#macros-retry-btn');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      _state.error = false;
      _state.loading = true;
      renderSkeletons(container);
      loadData();
    });
  }
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountComponents(container) {
  const listeners = [];

  // Search input
  const searchEl = container.querySelector('#macros-search-input');
  if (searchEl) {
    const handler = async (e) => {
      _state.searchQuery = e.target.value;
      persistState();
      await renderPage(container);
    };
    searchEl.addEventListener('input', handler);
    listeners.push(() => searchEl.removeEventListener('input', handler));
  }

  // Toggle expand (header click or chevron button)
  const toggleEls = container.querySelectorAll('[data-action="toggle-expand"]');
  toggleEls.forEach((el) => {
    const handler = async () => {
      const name = el.dataset.macroName;
      if (!name) return;
      if (_state.expanded.has(name)) {
        _state.expanded.delete(name);
      } else {
        _state.expanded.add(name);
      }
      await renderPage(container);
    };
    el.addEventListener('click', handler);
    listeners.push(() => el.removeEventListener('click', handler));
  });

  // Dry-run toggle checkboxes
  container.querySelectorAll('.macro-dryrun-toggle').forEach((cb) => {
    const handler = async () => {
      const name = cb.dataset.macroName;
      if (!name) return;
      _state.dryRunEnabled[name] = cb.checked;
      // Re-render so the Run button label updates
      await renderPage(container);
    };
    cb.addEventListener('change', handler);
    listeners.push(() => cb.removeEventListener('change', handler));
  });

  // Run buttons
  container.querySelectorAll('.macro-run-btn').forEach((btn) => {
    const handler = () => {
      const name = btn.dataset.macroName;
      if (!name) return;
      const isDryRun = _state.dryRunEnabled[name] || false;
      executeMacro(name, isDryRun);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  // Dry Run buttons (always dry_run = true regardless of toggle)
  container.querySelectorAll('.macro-dryrun-btn').forEach((btn) => {
    const handler = () => {
      const name = btn.dataset.macroName;
      if (!name) return;
      executeMacro(name, true);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  _state._boundListeners = listeners;
}

/* ── Actions ────────────────────────────────────────────────────────────── */

async function executeMacro(name, dryRun = false) {
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  // Set loading state
  _state.results[name] = { loading: true, data: null, error: null };
  // Ensure expanded so results are visible
  _state.expanded.add(name);

  if (_state.container) await renderPage(_state.container);

  try {
    const result = await api.post('/api/v1/macros/run', { name, dry_run: dryRun });

    if (result && result.ok) {
      _state.results[name] = {
        loading: false,
        data: result.data || [],
        error: null,
      };
      toast.showToast(
        'success',
        dryRun ? 'Preview Complete' : 'Macro Executed',
        dryRun
          ? `Dry run completed for "${name}".`
          : `Macro "${name}" executed successfully.`,
      );
    } else {
      const msg =
        (result && result.data && result.data.error) ||
        (result && result.message) ||
        'Unknown error';
      _state.results[name] = {
        loading: false,
        data: null,
        error: msg,
      };
      toast.showToast('error', 'Execution Failed', msg);
    }
  } catch (err) {
    console.error('[macros] Execute error:', err);
    _state.results[name] = {
      loading: false,
      data: null,
      error: err.message || 'Failed to execute macro.',
    };
    toast.showToast(
      'error',
      'Execution Failed',
      err.message || 'Could not run macro.',
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
    const result = await api.get('/api/v1/macros');

    // Expected: { ok: true, data: { macroName: [{ step, command, ... }, ...] } }
    const rawMacros =
      result && result.ok && result.data ? result.data : {};

    // Convert to sorted array
    const entries = Object.keys(rawMacros)
      .filter((name) => Array.isArray(rawMacros[name]))
      .map((name) => ({
        name,
        steps: rawMacros[name],
      }))
      .sort((a, b) => a.name.localeCompare(b.name));

    _state.macros = rawMacros;
    _state.macrosArray = entries;
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  } catch (err) {
    console.error('[macros] Failed to load macros:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch macros.';
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
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;

  // Remove bound listeners
  for (const fn of _state._boundListeners) {
    try {
      fn();
    } catch (e) {
      /* ignore */
    }
  }
  _state._boundListeners = [];

  _state.container = null;
  _state.macros = {};
  _state.macrosArray = [];
  _state.results = {};
  _state.expanded = new Set();
  _state.dryRunEnabled = {};
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
      return '<div id="macros-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#macros-root') || container;
      render(root);
    },
    destroy,
  };
}
