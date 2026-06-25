/* ==========================================================================
   phiconnect.js — PhiConnect Secure Messaging Page
   ==========================================================================
   Full PhiConnect UI: service status & identity display, recent messages
   list with auto-refresh, and message compose/send form.  Polls for new
   messages every 10 seconds when auto-refresh is enabled.
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

const POLL_INTERVAL = 10000;
const MESSAGE_POLL_SECONDS = 180;
const STORAGE_KEY = 'fiona_phiconnect_auto_refresh';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  status: null,            // { ready, port, config_dir, identity_exists }
  identity: null,          // { device_id, public_bundle, fingerprint }
  messages: [],            // [{ sender, body, timestamp, ... }]
  autoRefresh: false,
  pollTimer: null,
  copyFeedback: false,
  sending: false,
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

function timeAgo(timestamp) {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

function persistAutoRefresh(value) {
  try {
    if (value) localStorage.setItem(STORAGE_KEY, '1');
    else localStorage.removeItem(STORAGE_KEY);
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

  const statusReady = _state.status?.ready === true;
  const port = _state.status?.port;
  const configDir = _state.status?.config_dir;
  const fingerprint = _state.identity?.fingerprint;
  const deviceId = _state.identity?.device_id;
  const messages = Array.isArray(_state.messages) ? _state.messages : [];

  // Build messages list content
  let messagesListContent = '';
  if (messages.length === 0) {
    messagesListContent = html`
      <div style="text-align: center; padding: var(--space-8) var(--space-4); color: var(--text-muted);">
        <div style="width: 40px; height: 40px; margin: 0 auto var(--space-3); display: flex; align-items: center; justify-content: center; color: var(--text-muted); opacity: 0.4;">
          ${ICONS.message}
        </div>
        <div style="font-size: var(--font-size-sm);">No recent messages</div>
        <div style="font-size: var(--font-size-xs); margin-top: var(--space-1);">
          Messages from the last ${MESSAGE_POLL_SECONDS / 60} minutes will appear here.
        </div>
      </div>
    `;
  } else {
    messagesListContent = messages.map((msg) => `
      <div class="phc-message" style="padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-1);">
          <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--accent); font-family: var(--font-mono);">
            ${esc(msg.sender || 'unknown')}
          </span>
          <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">
            ${timeAgo(msg.timestamp)}
          </span>
        </div>
        <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: pre-wrap; word-break: break-word; line-height: 1.5;">
          ${esc(msg.body || '')}
        </div>
      </div>
    `).join('');
  }

  const sendBtnContent = _state.sending
    ? '<span class="c-spinner c-spinner--sm" style="width: 16px; height: 16px;"></span> Sending&hellip;'
    : '<span style="width: 16px; height: 16px; display: flex; align-items: center; justify-content: center;">' + ICONS.chevronRight.html + '</span> Send';

  const data = {
    refreshIcon: ICONS.refresh.html,
    lockIcon: ICONS.lock.html,
    helpIcon: ICONS.help.html,
    messageIcon: ICONS.message.html,
    checkIcon: ICONS.check.html,
    copyIcon: ICONS.copy.html,
    arrowUpIcon: ICONS.arrowUp.html,
    autoRefresh: _state.autoRefresh,
    statusReady,
    hasPort: port != null,
    port: esc(String(port ?? '')),
    hasConfigDir: !!configDir,
    configDir: esc(configDir || ''),
    hasDeviceId: !!deviceId,
    deviceId: esc(deviceId || ''),
    hasFingerprint: !!fingerprint,
    fingerprint: esc(fingerprint || ''),
    copyFeedback: _state.copyFeedback,
    hasMessages: messages.length > 0,
    messagesCount: messages.length,
    messagesListContent,
    sending: _state.sending,
    sendBtnContent,
  };

  container.innerHTML = await loadTemplate('phiconnect', data);
  mountHandlers(container);
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-5);">
        ${skeletonHeading({ width: '180px' })}
        ${skeletonText({ width: '240px' })}
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: var(--space-4);">
        ${skeletonCard({ height: '320px' })}
        ${skeletonCard({ height: '320px' })}
      </div>
      <div style="margin-top: var(--space-4);">
        ${skeletonCard({ height: '180px' })}
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
        ${esc(_state.errorMessage || 'Unable to reach the PhiConnect backend. The service may not be running.')}
      </div>
      <button class="c-btn c-btn--primary" id="phc-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#phc-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // Refresh button — re-fetch everything (won't clear form, user-initiated)
  container.querySelector('#phc-refresh-btn')?.addEventListener('click', () => {
    loadData();
  });

  // Auto-refresh toggle
  const autoToggle = container.querySelector('#phc-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', () => {
      _state.autoRefresh = autoToggle.checked;
      persistAutoRefresh(_state.autoRefresh);
      if (_state.autoRefresh) startPolling();
      else stopPolling();
    });
  }

  // Copy fingerprint button
  container.querySelector('#phc-copy-btn')?.addEventListener('click', async () => {
    const fingerprint = _state.identity?.fingerprint;
    if (!fingerprint) return;

    try {
      await navigator.clipboard.writeText(fingerprint);
      _state.copyFeedback = true;
      const btn = container.querySelector('#phc-copy-btn');
      if (btn) {
        btn.querySelector('span:last-child').textContent = 'Copied!';
        const iconSpan = btn.querySelector('span:first-child');
        if (iconSpan) iconSpan.innerHTML = ICONS.check.html || ICONS.check;
      }
      setTimeout(() => {
        if (_state.destroyed) return;
        _state.copyFeedback = false;
        const btn2 = container.querySelector('#phc-copy-btn');
        if (btn2) {
          btn2.querySelector('span:last-child').textContent = 'Copy';
          const iconSpan2 = btn2.querySelector('span:first-child');
          if (iconSpan2) iconSpan2.innerHTML = ICONS.copy.html || ICONS.copy;
        }
      }, 2000);
    } catch (err) {
      console.warn('[phiconnect] Copy failed:', err);
    }
  });

  // Send message form
  const sendForm = container.querySelector('#phc-send-form');
  if (sendForm) {
    sendForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (_state.sending) return;

      const bodyEl = container.querySelector('#phc-msg-body');
      const hostEl = container.querySelector('#phc-msg-host');
      if (!bodyEl) return;

      const body = bodyEl.value.trim();
      if (!body) return;

      const host = hostEl ? hostEl.value.trim() : '';

      _state.sending = true;
      updateSendButtonSending(container);

      try {
        const api = getApi();
        if (!api) throw new Error('API not available');

        const payload = { body };
        if (host) {
          const parts = host.split(':');
          payload.host = parts[0];
          if (parts[1]) payload.port = parseInt(parts[1], 10);
        }

        const result = await api.post('/api/v1/phiconnect/send', payload);
        if (!result || !result.ok) {
          throw new Error(result?.data?.error || result?.data?.message || 'Send failed');
        }

        // Clear inputs
        bodyEl.value = '';
        if (hostEl) hostEl.value = '';

        // Show success toast
        toast.showToast('success', 'Message Sent', 'Your message was sent successfully.');

        // Refresh messages (silent, so no loading state flash)
        await refreshMessagesOnly();
      } catch (err) {
        console.error('[phiconnect] Send failed:', err);
        toast.showToast('error', 'Send Failed', err.message || 'Could not send message.');
      } finally {
        _state.sending = false;
        updateSendButtonIdle(container);
      }
    });
  }
}

function updateSendButtonSending(container) {
  const btn = container.querySelector('#phc-send-btn');
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = html`
    <span class="c-spinner c-spinner--sm" style="width: 16px; height: 16px;"></span>
    Sending\u2026
  `;
}

function updateSendButtonIdle(container) {
  const btn = container.querySelector('#phc-send-btn');
  if (!btn) return;
  btn.disabled = false;
  btn.innerHTML = html`
    <span style="width: 16px; height: 16px; display: flex; align-items: center; justify-content: center;">
      ${ICONS.chevronRight}
    </span>
    Send
  `;
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
  await refreshMessagesOnly();
}

/* ── Messages List Incremental Update ────────────────────────────────────── */

function updateMessagesList(container) {
  const listEl = container.querySelector('#phc-messages-list');
  const badgeEl = container.querySelector('#phc-msg-count');
  const messages = Array.isArray(_state.messages) ? _state.messages : [];

  if (!listEl) return;

  if (messages.length === 0) {
    listEl.innerHTML = html`
      <div style="text-align: center; padding: var(--space-8) var(--space-4); color: var(--text-muted);">
        <div style="width: 40px; height: 40px; margin: 0 auto var(--space-3); display: flex; align-items: center; justify-content: center; color: var(--text-muted); opacity: 0.4;">
          ${ICONS.message}
        </div>
        <div style="font-size: var(--font-size-sm);">No recent messages</div>
        <div style="font-size: var(--font-size-xs); margin-top: var(--space-1);">
          Messages from the last ${MESSAGE_POLL_SECONDS / 60} minutes will appear here.
        </div>
      </div>
    `;
    if (badgeEl) badgeEl.textContent = '0';
    return;
  }

  listEl.innerHTML = messages.map((msg) => `
    <div class="phc-message" style="padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-1);">
        <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--accent); font-family: var(--font-mono);">
          ${esc(msg.sender || 'unknown')}
        </span>
        <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">
          ${timeAgo(msg.timestamp)}
        </span>
      </div>
      <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: pre-wrap; word-break: break-word; line-height: 1.5;">
        ${esc(msg.body || '')}
      </div>
    </div>
  `).join('');

  if (badgeEl) badgeEl.textContent = String(messages.length);
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

/**
 * Refresh only the messages list — used by silent polling so the rest of
 * the page (especially the send form) is not disturbed.
 */
async function refreshMessagesOnly() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  try {
    const res = await api.get(`/api/v1/phiconnect/messages?seconds=${MESSAGE_POLL_SECONDS}`);
    if (_state.destroyed) return;

    if (res && res.ok) {
      _state.messages = Array.isArray(res.data) ? res.data : [];
      if (!_state.destroyed && _state.container && !_state.loading) {
        updateMessagesList(_state.container);
      }
    }
  } catch (err) {
    // Silently fail during poll — next poll or manual refresh will retry
  }
}

/**
 * Full data fetch — status, identity, and messages.
 * @param {boolean} [silent=false] - If true, errors are not surfaced to the user.
 */
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
    const [statusRes, identityRes, messagesRes] = await Promise.allSettled([
      api.get('/api/v1/phiconnect/status'),
      api.get('/api/v1/phiconnect/identity'),
      api.get(`/api/v1/phiconnect/messages?seconds=${MESSAGE_POLL_SECONDS}`),
    ]);

    if (_state.destroyed) return;

    let changed = false;

    if (statusRes.status === 'fulfilled') {
      const data = statusRes.value?.data || {};
      _state.status = data;
      changed = true;
    } else {
      if (!silent) {
        _state.error = true;
        _state.errorMessage = statusRes.reason?.message || 'Failed to fetch PhiConnect status.';
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
        _state.errorMessage = identityRes.reason?.message || 'Failed to fetch PhiConnect identity.';
        _state.loading = false;
        if (_state.container) await renderPage(_state.container);
        return;
      }
    }

    if (messagesRes.status === 'fulfilled') {
      const data = messagesRes.value?.data;
      _state.messages = Array.isArray(data) ? data : [];
      changed = true;
    } else {
      if (!silent) {
        _state.error = true;
        _state.errorMessage = messagesRes.reason?.message || 'Failed to fetch messages.';
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
      console.error('[phiconnect] Failed to load data:', err);
      _state.error = true;
      _state.errorMessage = err.message || 'Unexpected error fetching PhiConnect data.';
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
  _state.messages = [];
  _state.copyFeedback = false;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="phiconnect-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#phiconnect-root') || container;
      render(root);
    },
    destroy,
  };
}
