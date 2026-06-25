/* ==========================================================================
   notifications.js — Notifications Page
   ==========================================================================
   System event center showing notifications with urgency indicators,
   filter controls, dismiss actions, auto-refresh polling, and a
   collapsible "create notification" form for testing.

   Exports default: createPage(routeInfo) => { render, mount, destroy }
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';
import { toast } from '../js/components/Toast.js';
import {
  skeletonCard,
  skeletonHeading,
  skeletonText,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 5000;
const NOTIFICATION_LIMIT = 50;

/** @type {Object<string, string>} */
const URGENCY_LABELS = {
  critical: 'Critical',
  normal: 'Normal',
  low: 'Low',
};

/** @type {Object<string, string>} */
const URGENCY_BADGE = {
  critical: 'c-badge--danger',
  normal: 'c-badge--warning',
  low: 'c-badge--info',
};

/** @type {Object<string, string>} */
const URGENCY_COLORS = {
  critical: 'var(--danger)',
  normal: 'var(--warning)',
  low: 'var(--text-muted)',
};

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  // Notifications data
  items: [],
  total: 0,
  unread: 0,

  // Filters
  unreadOnly: false,
  autoRefresh: false,

  // Dismiss confirmation
  confirmingDismissAll: false,

  // Create notification form
  createOpen: false,
  creating: false,
  formTitle: '',
  formBody: '',
  formUrgency: 'normal',

  // Polling
  pollTimer: null,

  // Dismiss animation tracking
  dismissingIndices: new Set(),
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

  const unreadCount = _state.unread;
  const itemsCount = _state.items.length;

  // Build notification list content
  const notificationListContent = itemsCount === 0 ? String(renderEmptyState().html) : renderNotificationList().html;

  // Build create button content
  let createBtnContent;
  if (_state.creating) {
    createBtnContent = html`
      <span class="c-spinner c-spinner--sm" style="display: inline-flex; align-items: center;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <circle cx="12" cy="12" r="10" stroke-dasharray="31.4 31.4" stroke-linecap="round" />
        </svg>
      </span>
      Sending&hellip;
    `;
  } else {
    createBtnContent = html`
      <span class="c-btn__icon">${ICONS.plus}</span>
      Send
    `;
  }

  const data = {
    hasUnread: unreadCount > 0,
    unreadCount: String(unreadCount),
    unreadOnly: _state.unreadOnly,
    autoRefresh: _state.autoRefresh,
    confirmingDismissAll: _state.confirmingDismissAll,
    itemsCount: String(itemsCount),
    singularItems: itemsCount === 1,
    trashIcon: ICONS.trash.html,
    refreshIcon: ICONS.refresh.html,
    warningIcon: ICONS.warning.html,
    plusIcon: ICONS.plus.html,
    chevronDownIcon: ICONS.chevronDown.html,
    createOpen: _state.createOpen,
    formTitle: esc(_state.formTitle),
    formBody: esc(_state.formBody),
    isCritical: _state.formUrgency === 'critical',
    isNormal: _state.formUrgency === 'normal',
    isLow: _state.formUrgency === 'low',
    creating: _state.creating,
    createBtnContent,
    notificationListContent,
  };

  container.innerHTML = await loadTemplate('notifications', data);
  mountComponents(container);
}

/* ── Empty State ────────────────────────────────────────────────────────── */

function renderEmptyState() {
  return html`
    <div class="empty-state" style="margin-top: 8vh;">
      <div class="empty-state__icon" style="color: var(--text-muted); opacity: 0.4;">
        ${ICONS.bell}
      </div>
      <div class="empty-state__title">No notifications</div>
      <div class="empty-state__description">
        Notifications will appear here when system events occur.
      </div>
    </div>
  `;
}

/* ── Notification List ──────────────────────────────────────────────────── */

function renderNotificationList() {
  return html`
    <div style="display: flex; flex-direction: column; gap: var(--space-3);">
      ${html.raw(_state.items.map((notif, index) => renderNotificationCard(notif, index)).join(''))}
    </div>
  `;
}

function renderNotificationCard(notif, index) {
  const urgency = notif.urgency || 'normal';
  const urgencyColor = URGENCY_COLORS[urgency] || 'var(--text-muted)';
  const badgeClass = URGENCY_BADGE[urgency] || 'c-badge--default';
  const badgeLabel = URGENCY_LABELS[urgency] || urgency;
  const isDismissing = _state.dismissingIndices.has(index);

  return html`
    <div class="c-card notification-item"
         data-notif-index="${index}"
         style="transition: opacity 0.3s ease, transform 0.3s ease;
                ${isDismissing ? 'opacity: 0; transform: translateX(20px); pointer-events: none;' : ''}">
      <div class="c-card__body" style="padding: var(--space-4); display: flex; align-items: flex-start; gap: var(--space-3);">
        <!-- Urgency indicator bar -->
        <div style="width: 4px; align-self: stretch; flex-shrink: 0;
                    border-radius: var(--radius-sm); background: ${urgencyColor};"></div>

        <!-- Urgency dot -->
        <div style="flex-shrink: 0; width: 10px; height: 10px; border-radius: 50%;
                    background: ${urgencyColor}; margin-top: 5px;"></div>

        <!-- Content -->
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: 2px;">
            <span style="font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--text-primary);">
              ${esc(notif.title || 'Untitled')}
            </span>
            <span class="c-badge ${badgeClass}" style="font-size: 9px; padding: 0 6px; text-transform: capitalize;">
              ${badgeLabel}
            </span>
          </div>
          ${notif.body ? html`
            <div style="font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.5;
                        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
              ${esc(notif.body)}
            </div>
          ` : ''}
        </div>

        <!-- Dismiss button -->
        <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost notif-dismiss-btn"
                data-notif-index="${index}"
                title="Dismiss notification"
                style="flex-shrink: 0; color: var(--text-muted);"
                ${isDismissing ? 'disabled' : ''}>
          ${ICONS.close}
        </button>
      </div>
    </div>
  `;
}

/* ── Skeleton & Error States ────────────────────────────────────────────── */

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-5);">
        ${skeletonHeading({ width: '200px' })}
        ${skeletonText({ width: '140px' })}
      </div>
      <div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-4);">
        <div class="c-skeleton" style="width: 100px; height: 32px; border-radius: var(--radius-md);"></div>
        <div class="c-skeleton" style="width: 100px; height: 32px; border-radius: var(--radius-md);"></div>
        <div class="c-skeleton" style="width: 80px; height: 32px; border-radius: var(--radius-md);"></div>
      </div>
      <div style="display: flex; flex-direction: column; gap: var(--space-3);">
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
      <div class="empty-state__title">Failed to Load Notifications</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to fetch notifications from the backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="notif-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#notif-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Component Mounting / Event Binding ─────────────────────────────────── */

function mountComponents(container) {
  // Filter: All
  container.querySelector('#notif-filter-all')?.addEventListener('click', async () => {
    if (_state.unreadOnly) {
      _state.unreadOnly = false;
      await renderPage(container);
    }
  });

  // Filter: Unread only
  container.querySelector('#notif-filter-unread')?.addEventListener('click', async () => {
    if (!_state.unreadOnly) {
      _state.unreadOnly = true;
      await renderPage(container);
    }
  });

  // Refresh button
  container.querySelector('#notif-refresh-btn')?.addEventListener('click', () => {
    loadData();
  });

  // Auto-refresh toggle
  container.querySelector('#notif-auto-refresh-toggle')?.addEventListener('change', (e) => {
    _state.autoRefresh = e.target.checked;
    if (_state.autoRefresh) {
      startPolling();
    } else {
      stopPolling();
    }
  });

  // Dismiss All button
  container.querySelector('#notif-dismiss-all-btn')?.addEventListener('click', async () => {
    if (_state.items.length === 0) return;
    _state.confirmingDismissAll = true;
    await renderPage(container);
  });

  // Dismiss All: Cancel
  container.querySelector('#notif-dismiss-all-cancel')?.addEventListener('click', async () => {
    _state.confirmingDismissAll = false;
    await renderPage(container);
  });

  // Dismiss All: Confirm
  container.querySelector('#notif-dismiss-all-confirm')?.addEventListener('click', () => {
    _state.confirmingDismissAll = false;
    dismissAllNotifications();
  });

  // Create: Toggle collapse
  container.querySelector('#notif-create-header')?.addEventListener('click', async () => {
    _state.createOpen = !_state.createOpen;
    await renderPage(container);
  });

  // Create: Title input
  container.querySelector('#notif-create-title')?.addEventListener('input', (e) => {
    _state.formTitle = e.target.value;
  });

  // Create: Body textarea
  container.querySelector('#notif-create-body-input')?.addEventListener('input', (e) => {
    _state.formBody = e.target.value;
  });

  // Create: Urgency select
  container.querySelector('#notif-create-urgency')?.addEventListener('change', (e) => {
    _state.formUrgency = e.target.value;
  });

  // Create: Send button
  container.querySelector('#notif-create-send-btn')?.addEventListener('click', () => {
    createNotification();
  });

  // Delegate dismiss button clicks on notification items
  const notifList = container.querySelector('#notif-list');
  if (notifList) {
    notifList.addEventListener('click', (e) => {
      const btn = e.target.closest('.notif-dismiss-btn');
      if (!btn) return;
      const index = parseInt(btn.dataset.notifIndex, 10);
      if (!isNaN(index) && !_state.dismissingIndices.has(index)) {
        dismissNotification(index);
      }
    });
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
    const params = { limit: NOTIFICATION_LIMIT };
    if (_state.unreadOnly) {
      params.unread_only = true;
    }

    const result = await api.get('/api/v1/notifications', params);
    const data = result?.data || result;

    _state.items = Array.isArray(data?.items) ? data.items : [];
    _state.total = data?.total ?? _state.items.length;
    _state.unread = data?.unread ?? 0;
    _state.error = false;
    _state.loading = false;

    // Clear dismissing state when data reloads
    _state.dismissingIndices.clear();
    _state.confirmingDismissAll = false;

    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  } catch (err) {
    console.error('[notifications] Failed to load data:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch notifications.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  }
}

/* ── Dismiss Notifications ──────────────────────────────────────────────── */

function dismissNotification(index) {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  // Start dismiss animation
  _state.dismissingIndices.add(index);
  if (_state.container) renderPage(_state.container);  // synchronous for immediate animation feedback

  // Perform the API call after a brief moment so the animation starts
  setTimeout(async () => {
    try {
      const result = await api.post('/api/v1/notifications/dismiss', { index });
      if (result?.ok === false) {
        // Revert on failure
        _state.dismissingIndices.delete(index);
        if (_state.container) await renderPage(_state.container);
        toast.showToast('error', 'Error', 'Failed to dismiss notification.');
        return;
      }

      // Remove from items list after a brief delay for the animation
      setTimeout(async () => {
        if (_state.destroyed) return;
        _state.items.splice(index, 1);
        _state.dismissingIndices.delete(index);
        // Recalculate indices after removal
        const newDismissing = new Set();
        for (const idx of _state.dismissingIndices) {
          if (idx > index) {
            newDismissing.add(idx - 1);
          } else if (idx < index) {
            newDismissing.add(idx);
          }
        }
        _state.dismissingIndices = newDismissing;

        // Update unread count (we don't know if it was unread, best-effort)
        if (_state.unread > 0) _state.unread--;

        if (_state.container) await renderPage(_state.container);
      }, 350);
    } catch (err) {
      console.error('[notifications] Dismiss failed:', err);
      _state.dismissingIndices.delete(index);
      if (_state.container) await renderPage(_state.container);
      toast.showToast('error', 'Error', 'Failed to dismiss notification.');
    }
  }, 50);
}

async function dismissAllNotifications() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  try {
    const result = await api.post('/api/v1/notifications/dismiss', { all: true });
    if (result?.ok === false) {
      toast.showToast('error', 'Error', 'Failed to dismiss all notifications.');
      return;
    }

    toast.showToast('success', 'Dismissed', 'All notifications have been dismissed.');

    // Clear state
    _state.items = [];
    _state.unread = 0;
    _state.dismissingIndices.clear();
    _state.confirmingDismissAll = false;

    if (_state.container) await renderPage(_state.container);
  } catch (err) {
    console.error('[notifications] Dismiss all failed:', err);
    toast.showToast('error', 'Error', 'Failed to dismiss all notifications.');
  }
}

/* ── Create Notification ────────────────────────────────────────────────── */

async function createNotification() {
  if (_state.destroyed) return;

  const title = _state.formTitle.trim();
  const body = _state.formBody.trim();

  if (!title) {
    toast.showToast('warning', 'Validation', 'Notification title is required.');
    return;
  }

  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  _state.creating = true;
  if (_state.container) await renderPage(_state.container);

  try {
    const result = await api.post('/api/v1/notifications/create', {
      title,
      body,
      urgency: _state.formUrgency,
    });

    if (result?.ok === false) {
      toast.showToast('error', 'Error', 'Failed to create notification.');
      _state.creating = false;
      if (_state.container) await renderPage(_state.container);
      return;
    }

    toast.showToast('success', 'Created', `Notification "${title}" has been sent.`);

    // Clear form
    _state.formTitle = '';
    _state.formBody = '';
    _state.formUrgency = 'normal';
    _state.creating = false;

    // Refresh the list
    await loadData();

    // Keep create panel open if it was open
    if (_state.container) await renderPage(_state.container);
  } catch (err) {
    console.error('[notifications] Create failed:', err);
    toast.showToast('error', 'Error', err.message || 'Failed to create notification.');
    _state.creating = false;
    if (_state.container) await renderPage(_state.container);
  }
}

/* ── Polling ─────────────────────────────────────────────────────────────── */

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
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  try {
    const params = { limit: NOTIFICATION_LIMIT };
    if (_state.unreadOnly) {
      params.unread_only = true;
    }

    const result = await api.get('/api/v1/notifications', params);
    if (_state.destroyed) return;

    const data = result?.data || result;
    const items = Array.isArray(data?.items) ? data.items : [];
    const newUnread = data?.unread ?? 0;

    // Check if anything changed
    const changed = items.length !== _state.items.length ||
      newUnread !== _state.unread ||
      JSON.stringify(items) !== JSON.stringify(_state.items);

    if (changed) {
      _state.items = items;
      _state.total = data?.total ?? items.length;
      _state.unread = newUnread;
      _state.dismissingIndices.clear();

      if (!_state.destroyed && _state.container) {
        await renderPage(_state.container);
      }
    }
  } catch {
    // Silent fail during background polling
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

  renderSkeletons(container);
  loadData().then(() => {
    if (!_state.destroyed && _state.autoRefresh) {
      startPolling();
    }
  });
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();

  _state.container = null;
  _state.items = [];
  _state.dismissingIndices.clear();
  _state.total = 0;
  _state.unread = 0;
  _state.confirmingDismissAll = false;
  _state.creating = false;
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
      return '<div id="notifications-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#notifications-root') || container;
      render(root);
    },
    destroy,
  };
}
