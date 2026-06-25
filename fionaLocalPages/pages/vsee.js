/* ==========================================================================
   vsee.js — Vsee Holography Visual Scene Viewer
   ==========================================================================
   Status, launch, and data preview for the Vsee holography workspace.
   Fetches backend status, allows launching the viewer with optional
   file paths, and displays the default model points/edges data.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const API_STATUS  = '/api/v1/vsee/status';
const API_LAUNCH  = '/api/v1/vsee/launch';
const API_MODEL   = '/api/v1/vsee/model';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,

  // General
  loading: true,
  error: false,
  errorMessage: '',

  // Status
  available: false,
  hasGui: false,

  // Model
  modelLoading: false,
  modelError: false,
  modelErrorMessage: '',
  pointsText: '',
  edgesText: '',

  // Launch
  pointsPath: '',
  edgesPath: '',
  launching: false,
  launchMessage: '',
  launchOk: false,
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api || window.__fiona?.api;
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

  // Build model preview content
  let modelPreviewContent = '';
  if (_state.modelLoading) {
    modelPreviewContent = html`
      <div style="padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-4);">
        <div class="c-skeleton" style="height: 20px; width: 60%;"></div>
        <div class="c-skeleton" style="height: 120px; width: 100%;"></div>
        <div class="c-skeleton" style="height: 20px; width: 40%; margin-top: var(--space-3);"></div>
        <div class="c-skeleton" style="height: 120px; width: 100%;"></div>
      </div>
    `;
  } else if (_state.modelError) {
    modelPreviewContent = html`
      <div style="padding: var(--space-6); text-align: center;">
        <div style="color: var(--danger); font-size: var(--font-size-sm); margin-bottom: var(--space-3);">
          ${esc(_state.modelErrorMessage || 'Failed to load model data.')}
        </div>
        <button class="c-btn c-btn--sm" id="vsee-retry-model">
          <span class="c-btn__icon">${ICONS.refresh}</span>
          Retry
        </button>
      </div>
    `;
  } else {
    modelPreviewContent = html`
      <div style="max-height: 500px; overflow-y: auto;">
        <div style="padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2);">
            <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-primary);">Points</span>
            <button class="c-btn c-btn--sm c-btn--ghost" data-action="copy-points" title="Copy points text">
              <span class="c-btn__icon">${ICONS.copy}</span>
            </button>
          </div>
          <pre style="margin: 0; padding: var(--space-3); background: var(--bg-tertiary); border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: var(--font-size-xxs); line-height: 1.6; color: var(--text-secondary); white-space: pre-wrap; word-break: break-all; overflow-x: auto; max-height: 180px;">${esc(_state.pointsText || 'No points data available.')}</pre>
        </div>
        <div style="padding: var(--space-3) var(--space-4);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2);">
            <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-primary);">Edges</span>
            <button class="c-btn c-btn--sm c-btn--ghost" data-action="copy-edges" title="Copy edges text">
              <span class="c-btn__icon">${ICONS.copy}</span>
            </button>
          </div>
          <pre style="margin: 0; padding: var(--space-3); background: var(--bg-tertiary); border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: var(--font-size-xxs); line-height: 1.6; color: var(--text-secondary); white-space: pre-wrap; word-break: break-all; overflow-x: auto; max-height: 180px;">${esc(_state.edgesText || 'No edges data available.')}</pre>
        </div>
      </div>
    `;
  }

  const launchBtnIcon = _state.launching
    ? '<span class="c-spinner" style="width:18px;height:18px;display:inline-block;"></span>'
    : ICONS.play.html;

  const data = {
    refreshIcon: ICONS.refresh.html,
    checkIcon: ICONS.check.html,
    errorIcon: ICONS.error.html,
    playIcon: ICONS.play.html,
    available: _state.available,
    hasGui: _state.hasGui,
    pointsPath: esc(_state.pointsPath),
    edgesPath: esc(_state.edgesPath),
    launching: _state.launching,
    launchBtnIcon,
    launchBtnText: _state.launching ? 'Launching&hellip;' : 'Launch Vsee',
    hasLaunchMessage: !!_state.launchMessage,
    launchOk: _state.launchOk,
    launchMessage: esc(_state.launchMessage || ''),
    modelPreviewContent,
  };

  container.innerHTML = await loadTemplate('vsee', data);
  mountHandlers(container);
}

/* ── Skeleton Render ────────────────────────────────────────────────────── */

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-6);">
        <div class="c-skeleton c-skeleton--heading" style="width: 120px; height: 28px; margin-bottom: 8px;"></div>
        <div class="c-skeleton c-skeleton--text" style="width: 220px; height: 16px;"></div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-5); margin-bottom: var(--space-5);">
        <div class="c-skeleton c-skeleton--card" style="height: 340px;"></div>
        <div class="c-skeleton c-skeleton--card" style="height: 340px;"></div>
      </div>
      <div class="c-skeleton c-skeleton--card" style="height: 80px;"></div>
    </div>
  `;
}

/* ── Error Render ───────────────────────────────────────────────────────── */

function renderError(container) {
  container.innerHTML = html`
    <div class="empty-state" style="margin-top: 10vh;">
      <div class="empty-state__icon" style="color: var(--danger);">
        ${ICONS.error}
      </div>
      <div class="empty-state__title">Connection Error</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to reach the Vsee backend. The server may be offline.')}
      </div>
      <button class="c-btn c-btn--primary" id="vsee-retry-page" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#vsee-retry-page')?.addEventListener('click', () => {
    loadData();
  });
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // Track file path inputs
  const pointsInput = container.querySelector('#vsee-points-path');
  const edgesInput = container.querySelector('#vsee-edges-path');

  pointsInput?.addEventListener('input', (e) => {
    _state.pointsPath = e.target.value;
  });
  edgesInput?.addEventListener('input', (e) => {
    _state.edgesPath = e.target.value;
  });

  // Launch button
  container.querySelector('#vsee-launch-btn')?.addEventListener('click', () => {
    launchVsee();
  });

  // Refresh model (card header button)
  container.querySelector('#vsee-refresh-model')?.addEventListener('click', () => {
    loadModelData();
  });

  // Retry model (error state button)
  container.querySelector('#vsee-retry-model')?.addEventListener('click', () => {
    loadModelData();
  });

  // Copy points
  container.querySelector('[data-action="copy-points"]')?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(_state.pointsText);
      showToast('success', 'Points text copied to clipboard.');
    } catch {
      showToast('error', 'Failed to copy points text.');
    }
  });

  // Copy edges
  container.querySelector('[data-action="copy-edges"]')?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(_state.edgesText);
      showToast('success', 'Edges text copied to clipboard.');
    } catch {
      showToast('error', 'Failed to copy edges text.');
    }
  });

  // Quick action: Open with default data
  container.querySelector('#vsee-open-default')?.addEventListener('click', () => {
    _state.pointsPath = '';
    _state.edgesPath = '';
    if (pointsInput) pointsInput.value = '';
    if (edgesInput) edgesInput.value = '';
    launchVsee();
  });

  // Quick action: Refresh model
  container.querySelector('#vsee-refresh-model-btn')?.addEventListener('click', () => {
    loadModelData();
  });
}

/* ── API: Launch Vsee ───────────────────────────────────────────────────── */

async function launchVsee() {
  const api = getApi();
  if (!api || _state.launching) return;

  _state.launching = true;
  _state.launchMessage = '';
  _state.launchOk = false;

  // Reflect the spinner immediately
  const launchBtn = _state.container?.querySelector('#vsee-launch-btn');
  if (launchBtn) {
    launchBtn.disabled = true;
    launchBtn.innerHTML = html`
      <span class="c-btn__icon"><span class="c-spinner" style="width:18px;height:18px;display:inline-block;"></span></span>
      Launching…
    `;
  }

  try {
    const body = {};
    if (_state.pointsPath.trim()) body.points_path = _state.pointsPath.trim();
    if (_state.edgesPath.trim()) body.edges_path = _state.edgesPath.trim();

    const res = await api.post(API_LAUNCH, body);
    const data = res?.data || res;

    _state.launchOk = data?.launched === true;
    _state.launchMessage = data?.message || (_state.launchOk ? 'Vsee launched successfully.' : 'Launch failed.');
  } catch (err) {
    _state.launchOk = false;
    _state.launchMessage = err.message || 'Failed to launch Vsee.';
  }

  _state.launching = false;

  if (!_state.destroyed && _state.container) {
    await renderPage(_state.container);
  }
}

/* ── API: Load Model Data ────────────────────────────────────────────────── */

async function loadModelData() {
  const api = getApi();
  if (!api) {
    _state.modelError = true;
    _state.modelErrorMessage = 'API client not available.';
    _state.modelLoading = false;
    if (!_state.destroyed && _state.container) await renderPage(_state.container);
    return;
  }

  _state.modelLoading = true;
  _state.modelError = false;
  _state.modelErrorMessage = '';

  if (!_state.destroyed && _state.container) await renderPage(_state.container);

  try {
    const res = await api.get(API_MODEL);
    const data = res?.data || res;

    _state.pointsText = data?.points_text || '';
    _state.edgesText = data?.edges_text || '';
    _state.modelError = false;
  } catch (err) {
    _state.modelError = true;
    _state.modelErrorMessage = err.message || 'Failed to fetch model data.';
    _state.pointsText = '';
    _state.edgesText = '';
  }

  _state.modelLoading = false;

  if (!_state.destroyed && _state.container) {
    await renderPage(_state.container);
  }
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
  if (!api) {
    _state.error = true;
    _state.errorMessage = 'API client not available.';
    _state.loading = false;
    if (_state.container) await renderPage(_state.container);
    return;
  }

  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';

  if (_state.container) renderSkeletons(_state.container);

  try {
    const res = await api.get(API_STATUS);
    const data = res?.data || res;

    _state.available = data?.available === true;
    _state.hasGui = data?.has_gui === true;
    _state.error = false;
    _state.loading = false;
  } catch (err) {
    console.error('[vsee] Failed to load status:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch Vsee status.';
    _state.loading = false;
    _state.available = false;
    _state.hasGui = false;
  }

  if (!_state.destroyed && _state.container) {
    await renderPage(_state.container);
  }

  // Load model data in parallel (don't block on it)
  loadModelData();
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;

  renderSkeletons(container);
  loadData();
}

export async function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && !_state.destroyed && _state.container) {
    await renderPage(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;
  _state.container = null;
  _state.pointsPath = '';
  _state.edgesPath = '';
  _state.launchMessage = '';
  _state.launching = false;
  _state.pointsText = '';
  _state.edgesText = '';

  // Reset status state
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.available = false;
  _state.hasGui = false;
  _state.modelLoading = false;
  _state.modelError = false;
  _state.modelErrorMessage = '';
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="vsee-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#vsee-root') || container;
      render(root);
    },
    destroy,
  };
}
