/* ==========================================================================
   desktop.js — SeeOnDesk (Desktop Awareness) Page
   ==========================================================================
   Displays the current active window and a snapshot of all visible
   desktop windows.  Active window auto-refreshes every 2 seconds;
   the snapshot is manually refreshed.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const ACTIVE_POLL_INTERVAL = 2000;

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,

  // Active window state
  activeLoading: true,
  activeError: false,
  activeErrorMessage: '',
  activeData: null,
  autoRefresh: false,
  pollTimer: null,

  // Snapshot state
  snapshotLoading: true,
  snapshotError: false,
  snapshotErrorMessage: '',
  snapshotData: null,
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

function formatTimestamp(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  const s = date.getSeconds().toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function timeAgo(timestamp) {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;
  const sec = Math.floor(diff / 1000);
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

/* ── HTML Renderers ─────────────────────────────────────────────────────── */

async function renderPage(container) {
  if (_state.destroyed) return;
  _state.container = container;

  const data = {
    activeColumnContent: renderActiveWindowCard(),
    snapshotColumnContent: renderSnapshotCard(),
  };

  container.innerHTML = await loadTemplate('desktop', data);
  mountComponents(container);
}

/* ── Active Window Card ─────────────────────────────────────────────────── */

function renderActiveWindowCard() {
  if (_state.activeLoading) {
    return renderActiveSkeleton();
  }

  if (_state.activeError) {
    return renderActiveError();
  }

  const data = _state.activeData || {};

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.eye}
            </span>
            Active Window
          </span>
        </span>
        <div style="display: flex; align-items: center; gap: var(--space-3);">
          <label style="display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--text-muted); cursor: pointer; user-select: none;">
            <input type="checkbox" id="desktop-auto-refresh" ${_state.autoRefresh ? 'checked' : ''}
                   style="accent-color: var(--accent);">
            Auto-refresh
          </label>
          <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-active-refresh-btn" title="Refresh active window">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body">
        <div style="display: grid; grid-template-columns: auto 1fr; gap: var(--space-2) var(--space-4); font-size: var(--font-size-sm);">
          <div style="color: var(--text-muted); white-space: nowrap;">Window Title</div>
          <div style="color: var(--text-primary); font-weight: var(--font-weight-medium); word-break: break-word;">
            ${data.title ? esc(data.title) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>

          <div style="color: var(--text-muted); white-space: nowrap;">Application</div>
          <div style="color: var(--text-primary); display: flex; align-items: center; gap: var(--space-2);">
            <span style="width: 16px; height: 16px; display: inline-flex; align-items: center; justify-content: center; color: var(--text-muted); flex-shrink: 0;">
              ${ICONS.puzzle}
            </span>
            ${data.app_name ? esc(data.app_name) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>

          <div style="color: var(--text-muted); white-space: nowrap;">Window ID</div>
          <div style="color: var(--text-primary); font-family: var(--font-mono); font-size: var(--font-size-xs);">
            ${data.window_id ? esc(data.window_id) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>

          <div style="color: var(--text-muted); white-space: nowrap;">Geometry</div>
          <div style="color: var(--text-primary); font-family: var(--font-mono); font-size: var(--font-size-xs);">
            ${data.geometry ? renderGeometry(data.geometry) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderGeometry(geom) {
  if (typeof geom === 'object' && geom !== null) {
    const x = geom.x ?? geom.left ?? '?';
    const y = geom.y ?? geom.top ?? '?';
    const w = geom.width ?? geom.w ?? '?';
    const h = geom.height ?? geom.h ?? '?';
    return html`x: ${esc(String(x))}, y: ${esc(String(y))} · ${esc(String(w))}×${esc(String(h))}`;
  }
  if (typeof geom === 'string') {
    return esc(geom);
  }
  return html`<span style="color: var(--text-muted); font-style: italic;">—</span>`;
}

function renderActiveSkeleton() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="width: 18px; height: 18px;"></span>
            Active Window
          </span>
        </span>
      </div>
      <div class="c-card__body">
        <div style="display: flex; flex-direction: column; gap: var(--space-3);">
          ${skeletonText({ lines: 4 })}
        </div>
      </div>
    </div>
  `;
}

function renderActiveError() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--danger); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.eye}
            </span>
            Active Window
          </span>
        </span>
        <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-active-refresh-btn" title="Retry">
          <span class="c-btn__icon">${ICONS.refresh}</span>
        </button>
      </div>
      <div class="c-card__body">
        <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
          <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
            ${esc(_state.activeErrorMessage || 'Failed to fetch active window.')}
          </span>
        </div>
      </div>
    </div>
  `;
}

/* ── Desktop Snapshot Card ──────────────────────────────────────────────── */

function renderSnapshotCard() {
  if (_state.snapshotLoading) {
    return renderSnapshotSkeleton();
  }

  if (_state.snapshotError) {
    return renderSnapshotError();
  }

  const data = _state.snapshotData || {};
  const windows = Array.isArray(data.windows) ? data.windows : [];
  const focusedWindowId = data.focused_window || null;
  const timestamp = data.timestamp || null;

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.maximize}
            </span>
            Desktop Snapshot
          </span>
        </span>
        <div style="display: flex; align-items: center; gap: var(--space-3);">
          ${timestamp ? html`
            <span style="font-size: var(--font-size-xs); color: var(--text-muted); display: flex; align-items: center; gap: 4px;">
              <span style="width: 12px; height: 12px; display: inline-flex; align-items: center; justify-content: center;">${ICONS.clock}</span>
              ${timeAgo(timestamp)}
            </span>
          ` : ''}
          <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-snapshot-refresh-btn" title="Refresh snapshot">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body" style="padding: var(--space-2);">
        ${windows.length === 0 ? renderSnapshotEmpty() : html`
          <div style="display: flex; flex-direction: column; gap: 1px; max-height: 420px; overflow-y: auto;">
            ${html.raw(windows.map((win) => renderWindowItem(win, focusedWindowId)).join(''))}
          </div>
        `}
      </div>
    </div>
  `;
}

function renderWindowItem(win, focusedWindowId) {
  const isFocused = win.window_id && focusedWindowId && String(win.window_id) === String(focusedWindowId);
  const geom = win.geometry;

  return html`
    <div style="display: flex; gap: var(--space-3); padding: var(--space-2) var(--space-3);
                border-left: ${isFocused ? '3px solid var(--accent)' : '3px solid transparent'};
                background: ${isFocused ? 'var(--accent-muted)' : 'transparent'};
                border-radius: var(--radius-sm);
                transition: background var(--transition-fast);">
      <div style="width: 20px; height: 20px; display: flex; align-items: center; justify-content: center;
                  flex-shrink: 0; color: var(--text-muted); margin-top: 1px;">
        ${ICONS.puzzle}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <span style="font-size: var(--font-size-sm); font-weight: ${isFocused ? 'var(--font-weight-semibold)' : 'var(--font-weight-medium)'};
                       color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${win.title ? esc(win.title) : html`<span style="color: var(--text-muted); font-style: italic;">Untitled</span>`}
          </span>
          ${isFocused ? html`
            <span class="c-badge c-badge--accent" style="font-size: 9px; padding: 0 6px; flex-shrink: 0; line-height: 16px;">Focused</span>
          ` : ''}
        </div>
        <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 1px; display: flex; align-items: center; gap: var(--space-2);">
          <span>${win.app_name ? esc(win.app_name) : '—'}</span>
          ${geom ? html`
            <span>·</span>
            <span style="font-family: var(--font-mono); font-size: var(--font-size-xxs);">
              ${renderGeometryInline(geom)}
            </span>
          ` : ''}
        </div>
      </div>
    </div>
  `;
}

function renderGeometryInline(geom) {
  if (typeof geom === 'object' && geom !== null) {
    const x = geom.x ?? geom.left ?? '?';
    const y = geom.y ?? geom.top ?? '?';
    const w = geom.width ?? geom.w ?? '?';
    const h = geom.height ?? geom.h ?? '?';
    return `${esc(String(x))},${esc(String(y))} ${esc(String(w))}×${esc(String(h))}`;
  }
  if (typeof geom === 'string') {
    return esc(geom);
  }
  return '';
}

function renderSnapshotEmpty() {
  return html`
    <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-8) var(--space-4); text-align: center;">
      <span style="color: var(--text-muted); width: 40px; height: 40px;">${ICONS.maximize}</span>
      <div style="font-size: var(--font-size-sm); color: var(--text-muted);">
        No windows detected.
      </div>
      <div style="font-size: var(--font-size-xs); color: var(--text-muted);">
        The snapshot returned an empty window list.
      </div>
    </div>
  `;
}

function renderSnapshotSkeleton() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="width: 18px; height: 18px;"></span>
            Desktop Snapshot
          </span>
        </span>
      </div>
      <div class="c-card__body" style="padding: var(--space-2);">
        <div style="display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-2);">
          ${Array.from({ length: 4 }, () => skeletonText({ width: '90%' }))}
        </div>
      </div>
    </div>
  `;
}

function renderSnapshotError() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="width: 18px; height: 18px;"></span>
            Desktop Snapshot
          </span>
        </span>
        <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-snapshot-refresh-btn" title="Retry">
          <span class="c-btn__icon">${ICONS.refresh}</span>
        </button>
      </div>
      <div class="c-card__body">
        <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
          <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
            ${esc(_state.snapshotErrorMessage || 'Failed to fetch desktop snapshot.')}
          </span>
        </div>
      </div>
    </div>
  `;
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountComponents(container) {
  // Active window refresh button (both normal and retry states use same id)
  container.querySelectorAll('#desktop-active-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadActiveWindow());
  });

  // Auto-refresh toggle
  const autoToggle = container.querySelector('#desktop-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', (e) => {
      _state.autoRefresh = e.target.checked;
      if (_state.autoRefresh) {
        startPolling();
      } else {
        stopPolling();
      }
    });
  }

  // Snapshot refresh button
  container.querySelectorAll('#desktop-snapshot-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadSnapshot());
  });
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadActiveWindow() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.activeError = true;
    _state.activeErrorMessage = 'API client not available.';
    _state.activeLoading = false;
    reRenderActiveColumn();
    return;
  }

  try {
    const result = await api.get('/api/v1/desktop/active');
    if (_state.destroyed) return;

    _state.activeData = result?.data || result;
    _state.activeError = false;
    _state.activeErrorMessage = '';
    _state.activeLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch active window:', err);
    _state.activeError = true;
    _state.activeErrorMessage = err.message || 'Failed to fetch active window.';
    _state.activeLoading = false;
  }

  if (!_state.destroyed) {
    reRenderActiveColumn();
  }
}

async function loadSnapshot() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.snapshotError = true;
    _state.snapshotErrorMessage = 'API client not available.';
    _state.snapshotLoading = false;
    reRenderSnapshotColumn();
    return;
  }

  try {
    const result = await api.get('/api/v1/desktop/snapshot');
    if (_state.destroyed) return;

    _state.snapshotData = result?.data || result;
    _state.snapshotError = false;
    _state.snapshotErrorMessage = '';
    _state.snapshotLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch snapshot:', err);
    _state.snapshotError = true;
    _state.snapshotErrorMessage = err.message || 'Failed to fetch desktop snapshot.';
    _state.snapshotLoading = false;
  }

  if (!_state.destroyed) {
    reRenderSnapshotColumn();
  }
}

function reRenderActiveColumn() {
  const col = _state.container?.querySelector('#desktop-active-column');
  if (!col) return;
  col.innerHTML = renderActiveWindowCard();
  // Re-bind active column events
  col.querySelectorAll('#desktop-active-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadActiveWindow());
  });
  const autoToggle = col.querySelector('#desktop-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', (e) => {
      _state.autoRefresh = e.target.checked;
      if (_state.autoRefresh) {
        startPolling();
      } else {
        stopPolling();
      }
    });
  }
}

function reRenderSnapshotColumn() {
  const col = _state.container?.querySelector('#desktop-snapshot-column');
  if (!col) return;
  col.innerHTML = renderSnapshotCard();
  // Re-bind snapshot refresh
  col.querySelectorAll('#desktop-snapshot-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadSnapshot());
  });
}

/* ── Polling ─────────────────────────────────────────────────────────────── */

function startPolling() {
  stopPolling();
  _state.pollTimer = setInterval(silentActivePoll, ACTIVE_POLL_INTERVAL);
}

function stopPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
}

async function silentActivePoll() {
  if (_state.destroyed || !_state.autoRefresh) return;
  const api = getApi();
  if (!api) return;

  try {
    const result = await api.get('/api/v1/desktop/active');
    if (_state.destroyed || !_state.autoRefresh) return;

    _state.activeData = result?.data || result;
    _state.activeError = false;
    _state.activeErrorMessage = '';
    _state.activeLoading = false;

    reRenderActiveColumn();
  } catch (err) {
    // Silently fail on poll — don't show error state, keep last valid data
    if (!_state.activeData) {
      _state.activeError = true;
      _state.activeErrorMessage = err.message || 'Poll failed.';
      reRenderActiveColumn();
    }
  }
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Full render — called from outside the router or from mount().
 * @param {Element} container
 */
export async function render(container) {
  _state.destroyed = false;
  _state.activeLoading = true;
  _state.activeError = false;
  _state.activeErrorMessage = '';
  _state.snapshotLoading = true;
  _state.snapshotError = false;
  _state.snapshotErrorMessage = '';
  _state.container = container;

  // Render skeleton layout immediately
  const data = {
    activeColumnContent: renderActiveSkeleton(),
    snapshotColumnContent: renderSnapshotSkeleton(),
  };
  container.innerHTML = await loadTemplate('desktop', data);

  // Fetch both in parallel
  Promise.all([loadActiveWindow(), loadSnapshot()]);
}

/**
 * Re-mount (re-attach events) without full re-render.
 * Called by the router after the HTML is already in the DOM.
 * @param {Element} container
 */
export function mount(container) {
  _state.container = container;
  mountComponents(container);
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();
  _state.container = null;
  _state.activeData = null;
  _state.snapshotData = null;
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
      return '<div id="desktop-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#desktop-root') || container;
      await render(root);
    },
    destroy,
  };
}
