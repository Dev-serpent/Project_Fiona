/* ==========================================================================
   recall.js — RecallVault Page
   ==========================================================================
   Persistent key-value memory browser.  Lets users search stored memories
   (recall), add new ones (remember), and delete them (forget).
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,

  // Search
  searchQuery: '',
  searchResults: [],
  searchLoading: false,
  searchError: false,
  searchErrorMessage: '',

  // Add form
  addFormExpanded: false,
  addLoading: false,

  // Forget confirmation
  confirmingKey: null,

  // Notification
  notification: null, // { type: 'success'|'error', message: string }
  notificationTimer: null,
  debounceTimer: null,
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

function timeAgo(timestamp) {
  if (!timestamp) return '';
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;
  const sec = Math.floor(diff / 1000);
  if (sec < 0) return 'just now';
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

/* ── Result Renderers ───────────────────────────────────────────────────── */

function renderResultsSkeleton() {
  return html`
    <div class="c-skeleton-group" style="margin-top: var(--space-3);">
      <div class="c-skeleton c-skeleton--card" style="height: 80px;"></div>
      <div class="c-skeleton c-skeleton--card" style="height: 80px;"></div>
      <div class="c-skeleton c-skeleton--card" style="height: 80px;"></div>
    </div>
  `;
}

function renderEmptyState(type) {
  if (type === 'initial') {
    return html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-8) var(--space-4); color: var(--text-muted);">
        <span style="width: 32px; height: 32px; opacity: 0.4;">${ICONS.search}</span>
        <div style="font-size: var(--font-size-sm); text-align: center;">Search to find stored memories</div>
      </div>
    `;
  }
  return html`
    <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-8) var(--space-4); color: var(--text-muted);">
      <span style="width: 32px; height: 32px; opacity: 0.4;">${ICONS.info}</span>
      <div style="font-size: var(--font-size-sm); text-align: center;">No results found</div>
    </div>
  `;
}

function renderResultCard(item) {
  const isConfirming = _state.confirmingKey === item.key;
  const key = esc(item.key);
  const value = esc(String(item.value ?? ''));
  const category = esc(item.category || 'general');
  const ts = timeAgo(item.timestamp);

  return html`
    <div class="c-card" style="margin-bottom: var(--space-2);">
      <div class="c-card__body" style="padding: var(--space-3) var(--space-4);">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3);">
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
              <span style="font-weight: var(--font-weight-semibold); color: var(--text-primary); font-family: var(--font-mono); font-size: var(--font-size-sm);">${key}</span>
              <span class="c-badge c-badge--info" style="font-size: 9px;">${category}</span>
            </div>
            <div style="font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; font-family: var(--font-mono); white-space: pre-wrap; word-break: break-all; line-height: var(--line-height-relaxed);">${value}</div>
            <div style="display: flex; align-items: center; gap: 4px; margin-top: 6px;">
              <span style="display: flex; align-items: center; width: 12px; height: 12px; color: var(--text-muted);">${ICONS.clock}</span>
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">${ts}</span>
            </div>
          </div>
          <div style="flex-shrink: 0;">
            ${isConfirming
              ? html`
                <div style="display: flex; gap: var(--space-1); align-items: center;">
                  <button class="c-btn c-btn--sm c-btn--danger" data-forget-confirm="${key}" title="Confirm forget">
                    <span class="c-btn__icon">${ICONS.trash}</span>
                    Forget
                  </button>
                  <button class="c-btn c-btn--sm c-btn--ghost" data-forget-cancel="${key}" title="Cancel">Cancel</button>
                </div>
              `
              : html`
                <button class="c-btn c-btn--sm c-btn--icon c-btn--danger" data-forget="${key}" title="Forget this memory">
                  <span class="c-btn__icon">${ICONS.trash}</span>
                </button>
              `
            }
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderResults() {
  const resultsEl = _state.container?.querySelector('#recall-results');
  if (!resultsEl) return;

  const statusEl = _state.container?.querySelector('#recall-status-count');

  if (_state.searchLoading) {
    resultsEl.innerHTML = renderResultsSkeleton();
    if (statusEl) statusEl.textContent = '';
    return;
  }

  if (_state.searchError) {
    resultsEl.innerHTML = html`
      <div class="c-alert c-alert--danger" style="margin-top: var(--space-3);">
        <span class="c-alert__icon">${ICONS.error}</span>
        <div class="c-alert__content">
          <div class="c-alert__title">Search failed</div>
          <div>${esc(_state.searchErrorMessage || 'An unexpected error occurred.')}</div>
        </div>
        <button class="c-alert__dismiss" id="recall-search-retry" title="Retry search">
          ${ICONS.refresh}
        </button>
      </div>
    `;
    if (statusEl) statusEl.textContent = '';

    resultsEl.querySelector('#recall-search-retry')?.addEventListener('click', () => {
      performSearch(_state.searchQuery);
    });
    return;
  }

  const query = _state.searchQuery.trim();
  if (!query) {
    resultsEl.innerHTML = renderEmptyState('initial');
    if (statusEl) statusEl.textContent = '';
    return;
  }

  const items = _state.searchResults;
  if (!items || items.length === 0) {
    resultsEl.innerHTML = renderEmptyState('empty');
    if (statusEl) statusEl.textContent = '';
    return;
  }

  resultsEl.innerHTML = items.map(renderResultCard).join('');

  if (statusEl) {
    statusEl.textContent = `${items.length} result${items.length !== 1 ? 's' : ''} found`;
  }

  // Bind forget / confirm / cancel buttons
  resultsEl.querySelectorAll('[data-forget]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const key = btn.getAttribute('data-forget');
      _state.confirmingKey = key;
      renderResults();
    });
  });

  resultsEl.querySelectorAll('[data-forget-confirm]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const key = btn.getAttribute('data-forget-confirm');
      handleConfirmForget(key);
    });
  });

  resultsEl.querySelectorAll('[data-forget-cancel]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      _state.confirmingKey = null;
      renderResults();
    });
  });
}

/* ── Add Form Renderer ──────────────────────────────────────────────────── */

function renderAddForm() {
  const bodyEl = _state.container?.querySelector('#recall-add-body');
  const chevronEl = _state.container?.querySelector('#recall-add-chevron');
  if (!bodyEl) return;

  if (!_state.addFormExpanded) {
    bodyEl.classList.add('is-hidden');
    if (chevronEl) chevronEl.innerHTML = String(ICONS.chevronDown);
    return;
  }

  bodyEl.classList.remove('is-hidden');
  if (chevronEl) chevronEl.innerHTML = String(ICONS.chevronUp);

  bodyEl.innerHTML = html`
    <div class="c-card__body" style="border-top: 1px solid var(--border-subtle);">
      <form id="recall-add-form">
        <div class="c-form-group" style="margin-bottom: var(--space-3);">
          <label class="c-form-group__label" for="recall-add-key">Key <span style="color: var(--danger);">*</span></label>
          <input type="text" class="c-input" id="recall-add-key" placeholder="Enter a unique key..." required autocomplete="off">
        </div>
        <div class="c-form-group" style="margin-bottom: var(--space-3);">
          <label class="c-form-group__label" for="recall-add-value">Value <span style="color: var(--danger);">*</span></label>
          <textarea class="c-textarea" id="recall-add-value" placeholder="Enter the value to store..." rows="3" required></textarea>
        </div>
        <div class="c-form-group" style="margin-bottom: var(--space-4);">
          <label class="c-form-group__label" for="recall-add-category">Category</label>
          <input type="text" class="c-input" id="recall-add-category" placeholder="general" value="general" autocomplete="off">
        </div>
        <div style="display: flex; gap: var(--space-2); align-items: center;">
          <button class="c-btn c-btn--primary" type="submit" id="recall-add-submit" ${_state.addLoading ? 'disabled' : ''}>
            <span class="c-btn__icon">${_state.addLoading ? html`<span class="c-spinner c-spinner--sm">${ICONS.refresh}</span>` : ICONS.plus}</span>
            ${_state.addLoading ? 'Remembering...' : 'Remember'}
          </button>
        </div>
      </form>
    </div>
  `;

  // Bind form submit
  bodyEl.querySelector('#recall-add-form')?.addEventListener('submit', handleAdd);
}

/* ── Error Banner ────────────────────────────────────────────────────────── */

function showError(message) {
  const el = _state.container?.querySelector('#recall-error');
  if (!el) return;
  el.classList.remove('is-hidden');
  const textEl = el.querySelector('.c-alert__content');
  if (textEl) textEl.innerHTML = `<div>${esc(message)}</div>`;
}

function hideError() {
  const el = _state.container?.querySelector('#recall-error');
  if (!el) return;
  el.classList.add('is-hidden');
}

/* ── Notification ────────────────────────────────────────────────────────── */

function showNotification(type, message) {
  if (_state.notificationTimer) {
    clearTimeout(_state.notificationTimer);
    _state.notificationTimer = null;
  }

  _state.notification = { type, message };

  const el = _state.container?.querySelector('#recall-notification');
  if (!el) return;

  el.className = `c-alert c-alert--${type === 'success' ? 'success' : 'danger'}`;
  el.style.marginBottom = 'var(--space-4)';
  el.innerHTML = html`
    <span class="c-alert__icon">${type === 'success' ? ICONS['check-circle'] : ICONS.error}</span>
    <div class="c-alert__content">${esc(message)}</div>
    <button class="c-alert__dismiss" id="recall-notification-dismiss">${ICONS.close}</button>
  `;

  el.classList.remove('is-hidden');

  el.querySelector('#recall-notification-dismiss')?.addEventListener('click', hideNotification);

  _state.notificationTimer = setTimeout(hideNotification, 4000);
}

function hideNotification() {
  if (_state.notificationTimer) {
    clearTimeout(_state.notificationTimer);
    _state.notificationTimer = null;
  }
  _state.notification = null;
  const el = _state.container?.querySelector('#recall-notification');
  if (el) el.classList.add('is-hidden');
}

/* ── API Calls ───────────────────────────────────────────────────────────── */

async function performSearch(query) {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.searchError = true;
    _state.searchErrorMessage = 'API client not available.';
    _state.searchLoading = false;
    renderResults();
    return;
  }

  _state.searchLoading = true;
  _state.searchError = false;
  _state.searchErrorMessage = '';
  _state.confirmingKey = null;

  renderResults();

  try {
    const encoded = encodeURIComponent(query);
    const result = await api.get(`/api/v1/recall/search?q=${encoded}`);
    if (_state.destroyed) return;

    const data = result?.data;
    _state.searchResults = Array.isArray(data) ? data : [];
    _state.searchLoading = false;
    _state.searchError = false;
  } catch (err) {
    if (_state.destroyed) return;
    _state.searchLoading = false;
    _state.searchError = true;
    _state.searchErrorMessage = err.message || 'Search request failed.';
  }

  renderResults();
}

async function handleConfirmForget(key) {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    showNotification('error', 'API client not available.');
    return;
  }

  try {
    const encoded = encodeURIComponent(key);
    const result = await api.delete?.(`/api/v1/recall/forget/${encoded}`)
      || await _legacyDelete(api, key);

    if (_state.destroyed) return;

    if (result?.ok) {
      // Remove from results
      _state.searchResults = _state.searchResults.filter((item) => item.key !== key);
      _state.confirmingKey = null;
      renderResults();
      showNotification('success', `Forgot "${key}"`);
    } else {
      showNotification('error', `Failed to forget "${key}"`);
      _state.confirmingKey = null;
      renderResults();
    }
  } catch (err) {
    if (_state.destroyed) return;
    showNotification('error', err.message || `Failed to forget "${key}"`);
    _state.confirmingKey = null;
    renderResults();
  }
}

/**
 * Fallback DELETE helper if api.delete() is not available.
 * Some Fiona API wrappers expose delete via a POST with _method or
 * via a direct fetch call.
 */
async function _legacyDelete(api, key) {
  const encoded = encodeURIComponent(key);
  // Try fetch-based DELETE through the api's base URL
  if (typeof api.getBaseUrl === 'function') {
    const base = api.getBaseUrl();
    const res = await fetch(`${base}/api/v1/recall/forget/${encoded}`, { method: 'DELETE' });
    return res.json();
  }
  // Fallback: use api.post with a query param workaround
  return api.post(`/api/v1/recall/forget/${encoded}`, { _method: 'DELETE' });
}

async function handleAdd(e) {
  e.preventDefault();
  if (_state.destroyed || _state.addLoading) return;

  const container = _state.container;
  if (!container) return;

  const keyEl = container.querySelector('#recall-add-key');
  const valueEl = container.querySelector('#recall-add-value');
  const catEl = container.querySelector('#recall-add-category');

  if (!keyEl || !valueEl) return;

  const key = keyEl.value.trim();
  const value = valueEl.value.trim();
  const category = (catEl?.value || 'general').trim() || 'general';

  if (!key) {
    showNotification('error', 'Key is required.');
    keyEl.focus();
    return;
  }
  if (!value) {
    showNotification('error', 'Value is required.');
    valueEl.focus();
    return;
  }

  const api = getApi();
  if (!api) {
    showNotification('error', 'API client not available.');
    return;
  }

  _state.addLoading = true;
  renderAddForm();

  try {
    const body = { key, value, category };
    const result = await api.post('/api/v1/recall/remember', body);
    if (_state.destroyed) return;

    if (result?.ok) {
      showNotification('success', `Remembered "${key}"`);

      // Clear form fields
      keyEl.value = '';
      valueEl.value = '';
      if (catEl) catEl.value = 'general';

      // If the user has an active search, refresh results
      if (_state.searchQuery.trim()) {
        performSearch(_state.searchQuery.trim());
      }
    } else {
      const msg = result?.data?.error || result?.error || 'Failed to remember.';
      showNotification('error', msg);
    }
  } catch (err) {
    if (_state.destroyed) return;
    showNotification('error', err.message || 'Failed to remember.');
  }

  _state.addLoading = false;
  renderAddForm();
}

function toggleAddForm() {
  _state.addFormExpanded = !_state.addFormExpanded;
  renderAddForm();
}

/* ── Event Binding ───────────────────────────────────────────────────────── */

function bindEvents() {
  const container = _state.container;
  if (!container) return;

  // Search input — debounced
  const searchInput = container.querySelector('#recall-search-input');
  if (searchInput) {
    searchInput.value = _state.searchQuery;
    searchInput.addEventListener('input', (e) => {
      _state.searchQuery = e.target.value;
      clearTimeout(_state.debounceTimer);
      _state.debounceTimer = setTimeout(() => {
        if (_state.destroyed) return;
        performSearch(_state.searchQuery);
      }, 300);
    });
  }

  // Toggle add form
  const toggleBtn = container.querySelector('#recall-toggle-add');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleAddForm);
  }

  // Error banner retry
  const retryBtn = container.querySelector('#recall-error-retry');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      hideError();
      if (_state.searchQuery.trim()) {
        performSearch(_state.searchQuery.trim());
      }
    });
  }
}

/* ── Full Page Render ────────────────────────────────────────────────────── */

async function renderPage(container) {
  if (_state.destroyed) return;

  // Build the results content (skeleton, empty, or result cards)
  let resultsContent = '';
  if (_state.searchLoading) {
    resultsContent = renderResultsSkeleton();
  } else if (_state.searchQuery.trim()) {
    if (_state.searchResults.length > 0) {
      resultsContent = _state.searchResults.map(renderResultCard).join('');
    } else {
      resultsContent = renderEmptyState('empty');
    }
  } else {
    resultsContent = renderEmptyState('initial');
  }

  const data = {
    searchIcon: ICONS.search.html,
    errorIcon: ICONS.error.html,
    refreshIcon: ICONS.refresh.html,
    plusIcon: ICONS.plus.html,
    chevronUpIcon: ICONS.chevronUp.html,
    chevronDownIcon: ICONS.chevronDown.html,
    searchQuery: esc(_state.searchQuery),
    addFormExpanded: _state.addFormExpanded,
    resultsContent,
  };

  container.innerHTML = await loadTemplate('recall', data);

  // Populate the add form body
  renderAddForm();

  // Render the appropriate results state
  renderResults();
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Full render — called from mount() and on retry.
 * @param {Element} container
 */
export async function render(container) {
  _state.destroyed = false;
  _state.container = container;

  await renderPage(container);
  bindEvents();
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;

  if (_state.debounceTimer) {
    clearTimeout(_state.debounceTimer);
    _state.debounceTimer = null;
  }
  if (_state.notificationTimer) {
    clearTimeout(_state.notificationTimer);
    _state.notificationTimer = null;
  }

  _state.container = null;
  _state.searchResults = [];
  _state.searchQuery = '';
  _state.searchLoading = false;
  _state.searchError = false;
  _state.searchErrorMessage = '';
  _state.confirmingKey = null;
  _state.notification = null;
  _state.addFormExpanded = false;
  _state.addLoading = false;
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
      return '<div id="recall-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#recall-root') || container;
      await render(root);
    },
    destroy,
  };
}
