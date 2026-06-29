/* ==========================================================================
   notifications.js — Notifications Page
   ==========================================================================
   System event center showing notifications with urgency indicators,
   filter controls, dismiss actions, auto-refresh polling, real-time
   WebSocket updates via store subscription, browser notification API,
   read/unread tracking, category display, and a collapsible
   "create notification" form for testing.

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
const WS_CHECK_INTERVAL = 3000;

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

/** @type {Object<string, string>} */
const CATEGORY_COLORS = {
  System: 'var(--info)',
  Agent: 'var(--success)',
  Action: 'var(--warning)',
  Error: 'var(--danger)',
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
  severityFilter: '',      // '' | 'critical' | 'normal' | 'low'
  categoryFilter: '',      // '' | 'System' | 'Agent' | 'Action' | ...

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

  // Store subscription
  storeUnsubscribe: null,
  storeSubscribed: false,

  // WebSocket connection state tracking
  wsConnected: false,
  wsCheckTimer: null,

  // Browser notification permission
  browserNotifGranted: false,
  browserNotifDenied: false,
  browserNotifUnsub: null,
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api || window.__fiona?.api;
}

function getStore() {
  return window.fiona?.store || window.__fiona?.store;
}

function esc(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

/**
 * Check if the WebSocket connection appears to be active.
 * Looks at the store's system.status or checks for a connected WS connection.
 */
function isWsConnected() {
  const store = getStore();
  if (store) {
    const status = store.get('system.status');
    if (status === 'connected') return true;
  }
  // Also check via the API client
  const api = getApi();
  if (api && typeof api._getConnections === 'function') {
    // Best-effort: if there's at least one WS connection, assume it might be ok
    return true;
  }
  return false;
}

/**
 * Get a unique list of categories present in the current items.
 */
function getCategories(items) {
  const cats = new Set();
  for (const n of items) {
    if (n.category) cats.add(n.category);
  }
  return ['', ...Array.from(cats).sort()];
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

  // Apply filters
  const filteredItems = getFilteredItems();
  const unreadCount = _state.unread;
  const itemsCount = filteredItems.length;

  // Build notification list content
  const notificationListContent = itemsCount === 0 ? String(renderEmptyState().html) : renderNotificationList(filteredItems).html;

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

  // Determine browser notification button visibility
  const showBrowserNotifBtn = !('Notification' in window)
    ? false
    : Notification.permission === 'default';

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
    bellIcon: ICONS.bell ? ICONS.bell.html : '',
    checkIcon: ICONS.check ? ICONS.check.html : '',
    createOpen: _state.createOpen,
    formTitle: esc(_state.formTitle),
    formBody: esc(_state.formBody),
    isCritical: _state.formUrgency === 'critical',
    isNormal: _state.formUrgency === 'normal',
    isLow: _state.formUrgency === 'low',
    creating: _state.creating,
    createBtnContent,
    notificationListContent,
    showBrowserNotifBtn,
  };

  container.innerHTML = await loadTemplate('notifications', data);
  mountComponents(container);
}

/**
 * Get items filtered by current filter settings.
 */
function getFilteredItems() {
  let items = _state.items;

  if (_state.unreadOnly) {
    items = items.filter((n) => !n.read);
  }

  if (_state.severityFilter) {
    items = items.filter((n) => n.urgency === _state.severityFilter);
  }

  if (_state.categoryFilter) {
    items = items.filter((n) => n.category === _state.categoryFilter);
  }

  return items;
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
        ${_state.unreadOnly || _state.severityFilter || _state.categoryFilter
          ? 'No notifications match the current filters.'
          : 'Notifications will appear here when system events occur.'}
      </div>
    </div>
  `;
}

/* ── Notification List ──────────────────────────────────────────────────── */

function renderNotificationList(items) {
  return html`
    <div style="display: flex; flex-direction: column; gap: var(--space-3);">
      ${html.raw(items.map((notif, index) => renderNotificationCard(notif, index)).join(''))}
    </div>
  `;
}

function renderNotificationCard(notif, index) {
  const urgency = notif.urgency || 'normal';
  const urgencyColor = URGENCY_COLORS[urgency] || 'var(--text-muted)';
  const badgeClass = URGENCY_BADGE[urgency] || 'c-badge--default';
  const badgeLabel = URGENCY_LABELS[urgency] || urgency;
  const isDismissing = _state.dismissingIndices.has(index);
  const isRead = notif.read === true;
  const category = notif.category || '';
  const categoryColor = CATEGORY_COLORS[category] || 'var(--text-muted)';
  const agentId = notif.agent_id || notif.agentId || '';

  return html`
    <div class="c-card notification-item ${isRead ? 'notification-item--read' : 'notification-item--unread'}"
         data-notif-id="${esc(notif.id || '')}"
         data-notif-index="${index}"
         style="transition: opacity 0.3s ease, transform 0.3s ease, box-shadow 0.2s ease;
                cursor: pointer;
                ${isRead ? 'opacity: 0.75;' : ''}
                ${isDismissing ? 'opacity: 0; transform: translateX(20px); pointer-events: none;' : ''}">
      <div class="c-card__body" style="padding: var(--space-4); display: flex; align-items: flex-start; gap: var(--space-3);">
        <!-- Urgency indicator bar -->
        <div style="width: 4px; align-self: stretch; flex-shrink: 0;
                    border-radius: var(--radius-sm); background: ${urgencyColor};"></div>

        <!-- Read/unread dot -->
        <div style="flex-shrink: 0; width: 10px; height: 10px; border-radius: 50%;
                    background: ${isRead ? 'var(--text-muted)' : urgencyColor};
                    margin-top: 5px; opacity: ${isRead ? 0.4 : 1};"></div>

        <!-- Content -->
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: 2px; flex-wrap: wrap;">
            <span style="font-size: var(--font-size-md); font-weight: var(--font-weight-semibold);
                        color: ${isRead ? 'var(--text-secondary)' : 'var(--text-primary)'};">
              ${esc(notif.title || 'Untitled')}
            </span>
            <span class="c-badge ${badgeClass}" style="font-size: 9px; padding: 0 6px; text-transform: capitalize;">
              ${badgeLabel}
            </span>
            ${category ? html`
              <span class="c-badge c-badge--default" style="font-size: 9px; padding: 0 6px; background: ${categoryColor}20; color: ${categoryColor}; border: 1px solid ${categoryColor}40;">
                ${esc(category)}
              </span>
            ` : ''}
            ${agentId ? html`
              <span style="font-size: 9px; color: var(--text-muted); display: flex; align-items: center; gap: 2px;">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="2" width="20" height="14" rx="2" ry="2"/>
                  <path d="M16 8h2"/>
                  <path d="M12 8h2"/>
                  <path d="M8 8h2"/>
                </svg>
                ${esc(agentId)}
              </span>
            ` : ''}
          </div>
          ${notif.body ? html`
            <div style="font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.5;
                        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
                        ${isRead ? 'opacity: 0.7;' : ''}">
              ${esc(notif.body)}
            </div>
          ` : ''}
          ${notif.timestamp ? html`
            <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
              ${formatTimestamp(notif.timestamp)}
            </div>
          ` : ''}
        </div>

        <!-- Dismiss button -->
        <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost notif-dismiss-btn"
                data-notif-id="${esc(notif.id || '')}"
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

/**
 * Format a unix timestamp for display.
 */
function formatTimestamp(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHrs = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHrs < 24) return `${diffHrs}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
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

  // Severity / Urgency filter
  container.querySelector('#notif-severity-filter')?.addEventListener('change', async (e) => {
    _state.severityFilter = e.target.value;
    await renderPage(container);
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

  // Dismiss All / Clear All button
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

  // Mark All Read
  container.querySelector('#notif-mark-all-read-btn')?.addEventListener('click', () => {
    markAllRead();
  });

  // Browser Notification Permission
  container.querySelector('#notif-browser-permission-btn')?.addEventListener('click', () => {
    requestBrowserNotificationPermission();
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

  // Delegate clicks on notification items (dismiss + mark read)
  const notifList = container.querySelector('#notif-list');
  if (notifList) {
    notifList.addEventListener('click', (e) => {
      // Dismiss button
      const dismissBtn = e.target.closest('.notif-dismiss-btn');
      if (dismissBtn) {
        const index = parseInt(dismissBtn.dataset.notifIndex, 10);
        if (!isNaN(index) && !_state.dismissingIndices.has(index)) {
          e.stopPropagation();
          dismissNotification(index);
        }
        return;
      }

      // Click on notification card (mark as read)
      const card = e.target.closest('.notification-item');
      if (card) {
        const notifId = card.dataset.notifId || '';
        const index = parseInt(card.dataset.notifIndex, 10);
        const notif = _state.items[index];
        if (notif && !notif.read) {
          markRead(notif, index);
        }
      }
    });

    // Hover effect for notification items
    notifList.addEventListener('mouseenter', (e) => {
      const card = e.target.closest('.notification-item');
      if (card && !card.classList.contains('notification-item--read')) {
        card.style.boxShadow = 'var(--shadow-md)';
      }
    }, true);

    notifList.addEventListener('mouseleave', (e) => {
      const card = e.target.closest('.notification-item');
      if (card) {
        card.style.boxShadow = '';
      }
    }, true);
  }

  // Update connection status indicator
  updateConnectionStatus();
}

function updateConnectionStatus() {
  const el = document.getElementById('notif-connection-status');
  if (!el) return;

  const connected = isWsConnected();
  if (connected) {
    el.textContent = '● Live';
    el.style.color = 'var(--success)';
  } else if (_state.autoRefresh) {
    el.textContent = '◌ Polling';
    el.style.color = 'var(--warning)';
  } else {
    el.textContent = '';
  }
}

/* ── Store Subscription ─────────────────────────────────────────────────── */

function subscribeToStore() {
  if (_state.storeSubscribed) return;

  const store = getStore();
  if (!store) {
    console.warn('[notifications] Store not available, will use polling only');
    return;
  }

  try {
    const unsub = store.subscribe('notifications.items', (newItems) => {
      if (_state.destroyed) return;
      // Sync items from store, preserving local state flags like read
      syncItemsFromStore(Array.isArray(newItems) ? newItems : []);
    });
    _state.storeUnsubscribe = unsub;
    _state.storeSubscribed = true;
    console.log('[notifications] Subscribed to store notifications.items');
  } catch (err) {
    console.warn('[notifications] Failed to subscribe to store:', err);
  }
}

function unsubscribeFromStore() {
  if (_state.storeUnsubscribe) {
    try {
      _state.storeUnsubscribe();
    } catch (e) {
      // ignore
    }
    _state.storeUnsubscribe = null;
  }
  _state.storeSubscribed = false;
}

/**
 * Sync items from the store into local state and re-render.
 * Merges new items, preserving local read state from backend updates.
 */
function syncItemsFromStore(newItems) {
  // Calculate unread count
  const unread = newItems.filter((n) => !n.read).length;

  // Update total
  const total = newItems.length;

  // Check if anything actually changed to avoid unnecessary re-renders
  const changed = total !== _state.items.length ||
    unread !== _state.unread ||
    JSON.stringify(newItems) !== JSON.stringify(_state.items);

  if (changed) {
    _state.items = newItems;
    _state.total = total;
    _state.unread = unread;
    _state.dismissingIndices.clear();
    _state.confirmingDismissAll = false;

    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
  }
}

/* ── WebSocket Connection Monitoring ────────────────────────────────────── */

function startWsMonitoring() {
  stopWsMonitoring();
  _state.wsCheckTimer = setInterval(() => {
    if (_state.destroyed) return;
    const wasConnected = _state.wsConnected;
    _state.wsConnected = isWsConnected();

    // Update connection status indicator if it changed
    if (wasConnected !== _state.wsConnected) {
      updateConnectionStatus();
    }

    // If WS disconnected and auto-refresh is on, polling handles it
    // If WS reconnected, polling is still active as supplement
  }, WS_CHECK_INTERVAL);
}

function stopWsMonitoring() {
  if (_state.wsCheckTimer) {
    clearInterval(_state.wsCheckTimer);
    _state.wsCheckTimer = null;
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

    const items = Array.isArray(data?.items) ? data.items : [];
    const total = data?.total ?? items.length;
    const unread = data?.unread ?? 0;

    _state.items = items;
    _state.total = total;
    _state.unread = unread;
    _state.error = false;
    _state.loading = false;

    // Also sync to store so other subscribers get the data
    const store = getStore();
    if (store) {
      store.set('notifications.items', items);
      store.set('notifications.unreadCount', unread);
    }

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

/* ── Mark Read ──────────────────────────────────────────────────────────── */

async function markRead(notif, index) {
  if (_state.destroyed) return;
  if (notif.read) return;

  // Optimistic update
  const updated = [..._state.items];
  updated[index] = { ...updated[index], read: true };
  _state.items = updated;
  _state.unread = Math.max(0, _state.unread - 1);

  if (_state.container) await renderPage(_state.container);

  // Also update the store
  const store = getStore();
  if (store && notif.id) {
    const storeItems = store.get('notifications.items');
    const storeIdx = storeItems.findIndex((n) => n.id === notif.id);
    if (storeIdx >= 0) {
      const newStoreItems = [...storeItems];
      newStoreItems[storeIdx] = { ...newStoreItems[storeIdx], read: true };
      store.set('notifications.items', newStoreItems);
      store.set('notifications.unreadCount', Math.max(0, store.get('notifications.unreadCount') - 1));
    }
  }

  // Backend call
  const api = getApi();
  if (!api || !notif.id) return;

  try {
    await api.post('/api/v1/notifications/mark-read', { id: notif.id });
  } catch (err) {
    console.error('[notifications] Mark read failed:', err);
    // Revert on failure
    const revertItems = [..._state.items];
    if (revertItems[index]) {
      revertItems[index] = { ...revertItems[index], read: false };
      _state.items = revertItems;
      _state.unread += 1;
      if (_state.container) await renderPage(_state.container);
    }
  }
}

async function markAllRead() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  // Optimistic update
  const updated = _state.items.map((n) => ({ ...n, read: true }));
  const prevUnread = _state.unread;
  _state.items = updated;
  _state.unread = 0;

  if (_state.container) await renderPage(_state.container);

  // Also update store
  const store = getStore();
  if (store) {
    store.set('notifications.items', updated);
    store.set('notifications.unreadCount', 0);
  }

  try {
    await api.post('/api/v1/notifications/mark-all-read', {});
    toast.showToast('success', 'Marked Read', 'All notifications marked as read.');
  } catch (err) {
    console.error('[notifications] Mark all read failed:', err);
    // Revert
    const revertItems = _state.items.map((n) => ({ ...n, read: false }));
    _state.items = revertItems;
    _state.unread = prevUnread;
    if (_state.container) await renderPage(_state.container);
    if (store) {
      store.set('notifications.items', revertItems);
      store.set('notifications.unreadCount', prevUnread);
    }
    toast.showToast('error', 'Error', 'Failed to mark all as read.');
  }
}

/* ── Dismiss Notifications ──────────────────────────────────────────────── */

function dismissNotification(index) {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  const notif = _state.items[index];
  const notifId = notif?.id;

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
        const removedItem = _state.items[index];
        _state.items.splice(index, 1);
        _state.dismissingIndices.delete(index);

        // Remove from store too
        if (removedItem && removedItem.id) {
          const store = getStore();
          if (store) {
            const storeItems = store.get('notifications.items');
            const storeIdx = storeItems.findIndex((n) => n.id === removedItem.id);
            if (storeIdx >= 0) {
              const newItems = [...storeItems];
              newItems.splice(storeIdx, 1);
              store.set('notifications.items', newItems);
            }
          }
        }

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

        // Update unread count
        if (!notif?.read && _state.unread > 0) _state.unread--;

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
      toast.showToast('error', 'Error', 'Failed to clear all notifications.');
      return;
    }

    toast.showToast('success', 'Cleared', 'All notifications have been cleared.');

    // Clear state
    _state.items = [];
    _state.unread = 0;
    _state.dismissingIndices.clear();
    _state.confirmingDismissAll = false;

    // Also clear store
    const store = getStore();
    if (store) {
      store.set('notifications.items', []);
      store.set('notifications.unreadCount', 0);
    }

    if (_state.container) await renderPage(_state.container);
  } catch (err) {
    console.error('[notifications] Dismiss all failed:', err);
    toast.showToast('error', 'Error', 'Failed to clear all notifications.');
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

/* ── Browser Notification API ───────────────────────────────────────────── */

function requestBrowserNotificationPermission() {
  if (!('Notification' in window)) {
    toast.showToast('info', 'Not Supported', 'Browser notifications are not supported in this browser.');
    return;
  }

  if (Notification.permission === 'granted') {
    _state.browserNotifGranted = true;
    toast.showToast('success', 'Granted', 'Browser notifications are already enabled.');
    return;
  }

  if (Notification.permission === 'denied') {
    _state.browserNotifDenied = true;
    toast.showToast('warning', 'Denied', 'Browser notifications were previously denied. Update your browser settings to enable them.');
    return;
  }

  Notification.requestPermission().then((permission) => {
    if (permission === 'granted') {
      _state.browserNotifGranted = true;
      toast.showToast('success', 'Enabled', 'Browser notifications are now enabled.');
      if (_state.container) renderPage(_state.container);
    } else {
      _state.browserNotifDenied = true;
      toast.showToast('info', 'Not Granted', 'Browser notification permission was not granted.');
    }
  }).catch((err) => {
    console.error('[notifications] Browser notification permission error:', err);
    toast.showToast('error', 'Error', 'Failed to request notification permission.');
  });
}

function showBrowserNotification(notif) {
  if (!('Notification' in window)) return;
  if (Notification.permission !== 'granted') return;
  if (!document.hidden) return;  // Only show when page is not visible

  try {
    const n = new Notification(notif.title || 'Notification', {
      body: notif.body || '',
      tag: notif.id || `notif-${Date.now()}`,
      icon: '/favicon.ico',
      silent: notif.urgency !== 'critical',
    });

    n.onclick = () => {
      window.focus();
      if (window.fiona?.router) {
        window.fiona.router.navigate('/notifications');
      }
      n.close();
    };

    // Auto-close after 10 seconds
    setTimeout(() => n.close(), 10000);
  } catch (err) {
    console.warn('[notifications] Failed to show browser notification:', err);
  }
}

function setupBrowserNotificationListener() {
  // Listen for store changes to show browser notifications for new items
  const store = getStore();
  if (!store) return;

  try {
    // Subscribe to notifications.items to detect new items
    const unsub = store.subscribe('notifications.items', (items) => {
      if (_state.destroyed) return;
      if (!Array.isArray(items) || items.length === 0) return;

      // Check if there's a new item at index 0 that wasn't there before
      // We track the last known first item id
      if (_state._lastFirstId && items[0] && items[0].id !== _state._lastFirstId) {
        // New notification arrived
        showBrowserNotification(items[0]);
      }
      _state._lastFirstId = items[0]?.id || null;
    });

    _state.browserNotifUnsub = unsub;
  } catch (err) {
    console.warn('[notifications] Failed to setup browser notification listener:', err);
  }
}

/* ── Polling ─────────────────────────────────────────────────────────────── */

function startPolling() {
  stopPolling();
  _state.pollTimer = setInterval(silentPoll, POLL_INTERVAL);
  updateConnectionStatus();
}

function stopPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
  updateConnectionStatus();
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

      // Sync to store
      const store = getStore();
      if (store) {
        store.set('notifications.items', items);
        store.set('notifications.unreadCount', newUnread);
      }

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

  // Subscribe to store for real-time updates
  subscribeToStore();

  // Set up browser notification listener
  setupBrowserNotificationListener();

  // Load initial data from REST API
  loadData().then(() => {
    if (!_state.destroyed) {
      // Start WebSocket connection monitoring
      startWsMonitoring();

      if (_state.autoRefresh) {
        startPolling();
      }

      // Check browser notification permission state
      if ('Notification' in window) {
        if (Notification.permission === 'granted') {
          _state.browserNotifGranted = true;
        }
      }
    }
  });
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();
  stopWsMonitoring();
  unsubscribeFromStore();

  if (_state.browserNotifUnsub) {
    try { _state.browserNotifUnsub(); } catch (e) { /* ignore */ }
    _state.browserNotifUnsub = null;
  }

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
