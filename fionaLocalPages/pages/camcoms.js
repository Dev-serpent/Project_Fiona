/* ==========================================================================
   camcoms.js — CamComs Status Page
   ==========================================================================
   Displays the Camera/Communications subsystem status and identity
   fingerprint.  Two-card layout: Service Status (ready/error, config
   existence) and Identity (fingerprint, copy-to-clipboard).
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
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

const POLL_INTERVAL = 10000;
const STORAGE_KEY = 'fiona_camcoms_auto_refresh';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  status: null,       // { ready, error, config_exists, ... }
  identity: null,     // { fingerprint, error }
  autoRefresh: false,
  pollTimer: null,
  copyFeedback: false,
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

function persistAutoRefresh(value) {
  try {
    if (value) {
      localStorage.setItem(STORAGE_KEY, '1');
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch { /* ignore */ }
}

function loadAutoRefreshPreference() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
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

  const data = {
    autoRefresh: _state.autoRefresh,
    refreshIcon: ICONS.refresh.html,
    eyeIcon: ICONS.eye.html,
    lockIcon: ICONS.lock.html,
    checkCircleIcon: ICONS['check-circle'].html,
    errorIcon: ICONS.error.html,
    copyIcon: ICONS.copy.html,
    checkIcon: ICONS.check.html,
    warningIcon: ICONS.warning.html,
    helpIcon: ICONS.help.html,
    statusReady: _state.status?.ready === true,
    hasStatusError: !!_state.status?.error,
    statusErrorText: esc(_state.status?.error || ''),
    configExists: _state.status?.config_exists === true,
    hasConfigPath: !!_state.status?.config_path,
    configPath: esc(_state.status?.config_path || ''),
    hasDevice: !!_state.status?.device,
    device: esc(_state.status?.device || ''),
    hasFingerprint: !!_state.identity?.fingerprint,
    fingerprint: esc(_state.identity?.fingerprint || ''),
    hasIdentityError: !!_state.identity?.error,
    identityError: esc(_state.identity?.error || ''),
    copyFeedback: _state.copyFeedback,
  };

  container.innerHTML = await loadTemplate('camcoms', data);
  mountHandlers(container);
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-5);">
        ${skeletonHeading({ width: '180px' })}
        ${skeletonText({ width: '240px' })}
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: var(--space-4);">
        ${skeletonCard({ height: '280px' })}
        ${skeletonCard({ height: '280px' })}
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
      <div class="empty-state__title">Connection Error</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to reach the CamComs backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="camcoms-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#camcoms-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // Refresh button
  container.querySelector('#camcoms-refresh-btn')?.addEventListener('click', () => {
    loadData();
  });

  // Auto-refresh toggle
  const autoToggle = container.querySelector('#camcoms-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', () => {
      _state.autoRefresh = autoToggle.checked;
      persistAutoRefresh(_state.autoRefresh);
      if (_state.autoRefresh) {
        startPolling();
      } else {
        stopPolling();
      }
    });
  }

  // Copy button
  container.querySelector('#camcoms-copy-btn')?.addEventListener('click', async () => {
    const fingerprint = _state.identity?.fingerprint;
    if (!fingerprint) return;

    try {
      await navigator.clipboard.writeText(fingerprint);
      _state.copyFeedback = true;
      const btn = container.querySelector('#camcoms-copy-btn');
      if (btn) {
        btn.querySelector('span:last-child').textContent = 'Copied!';
        const iconSpan = btn.querySelector('span:first-child');
        if (iconSpan) iconSpan.innerHTML = ICONS.check.html || ICONS.check;
      }
      // Reset feedback after 2 seconds
      setTimeout(() => {
        if (_state.destroyed) return;
        _state.copyFeedback = false;
        const btn2 = container.querySelector('#camcoms-copy-btn');
        if (btn2) {
          btn2.querySelector('span:last-child').textContent = 'Copy';
          const iconSpan2 = btn2.querySelector('span:first-child');
          if (iconSpan2) iconSpan2.innerHTML = ICONS.copy.html || ICONS.copy;
        }
      }, 2000);
    } catch (err) {
      console.warn('[camcoms] Copy failed:', err);
    }
  });
}

/* ── Polling ────────────────────────────────────────────────────────────── */

function startPolling() {
  stopPolling();
  _state.pollTimer = setInterval(silentPoll, POLL_INTERVAL);
}

function stopPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
}

async function silentPoll() {
  if (_state.destroyed || !_state.autoRefresh) return;
  await fetchData(true);
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function fetchData(silent) {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    if (!silent) {
      _state.error = true;
      _state.errorMessage = 'API client not available.';
      _state.loading = false;
      if (_state.container) await renderPage(_state.container);
    }
    return;
  }

  try {
    const [statusRes, identityRes] = await Promise.allSettled([
      api.get('/api/v1/camcoms/status'),
      api.get('/api/v1/camcoms/identity'),
    ]);

    if (_state.destroyed) return;

    let changed = false;

    if (statusRes.status === 'fulfilled') {
      const data = statusRes.value?.data || {};
      _state.status = data;
      changed = true;
    } else {
      // Only surface error on non-silent loads
      if (!silent) {
        _state.error = true;
        _state.errorMessage = statusRes.reason?.message || 'Failed to fetch CamComs status.';
        _state.loading = false;
        if (_state.container) await renderPage(_state.container);
        return;
      }
    }

    if (identityRes.status === 'fulfilled') {
      const data = identityRes.value?.data || {};
      _state.identity = data;
      changed = true;
    } else {
      if (!silent) {
        _state.error = true;
        _state.errorMessage = identityRes.reason?.message || 'Failed to fetch CamComs identity.';
        _state.loading = false;
        if (_state.container) await renderPage(_state.container);
        return;
      }
    }

    if (changed) {
      _state.error = false;
      _state.loading = false;
      if (!_state.destroyed && _state.container) {
        await renderPage(_state.container);
      }
    }
  } catch (err) {
    if (!silent) {
      console.error('[camcoms] Failed to load data:', err);
      _state.error = true;
      _state.errorMessage = err.message || 'Unexpected error fetching CamComs data.';
      _state.loading = false;
      if (!_state.destroyed && _state.container) {
        await renderPage(_state.container);
      }
    }
  }
}

async function loadData() {
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';

  if (_state.container) renderSkeletons(_state.container);

  await fetchData(false);

  // Start polling if auto-refresh was previously enabled
  if (_state.autoRefresh && !_state.destroyed) {
    startPolling();
  }
}

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;
  _state.copyFeedback = false;
  _state.autoRefresh = loadAutoRefreshPreference();

  renderSkeletons(container);
  loadData();
}

export async function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && _state.container) {
    await renderPage(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;
  stopPolling();
  _state.container = null;
  _state.status = null;
  _state.identity = null;
  _state.copyFeedback = false;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="camcoms-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#camcoms-root') || container;
      render(root);
    },
    destroy,
  };
}
