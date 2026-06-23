/* ==========================================================================
   logs.js — Log Viewer Page
   ==========================================================================
   Professional log viewer for Fiona system logs.  Provides real-time
   streaming via WebSocket, level filtering, search with debounce,
   date/time range presets, export, and a virtual-scrolled log list.

   Exports: { render(container?), mount(container), destroy() }
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonText,
  skeletonHeading,
  skeletonButton,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const MAX_CACHED_LOGS = 500;
const SEARCH_DEBOUNCE_MS = 300;
const LOG_PAGE_SIZE = 100;
const WS_EVENT_LOG = 'system:log';

const LOG_LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARN', 'ERROR'];

const LEVEL_COLORS = {
  DEBUG: 'var(--text-muted)',
  INFO:  'var(--info)',
  WARN:  'var(--warning)',
  ERROR: 'var(--danger)',
};

const LEVEL_BG = {
  DEBUG: 'rgba(100, 116, 139, 0.12)',
  INFO:  'rgba(56, 189, 248, 0.12)',
  WARN:  'rgba(234, 179, 8, 0.12)',
  ERROR: 'rgba(239, 68, 68, 0.12)',
};

const TIME_PRESETS = [
  { label: 'Last 5 min', value: 5 * 60 * 1000 },
  { label: 'Last 15 min', value: 15 * 60 * 1000 },
  { label: 'Last 1 hour', value: 60 * 60 * 1000 },
  { label: 'Today', value: 'today' },
  { label: 'All', value: 'all' },
];

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  // Filters
  level: 'ALL',
  search: '',
  since: null,
  until: null,
  service: 'all',

  // Data
  logs: [],               // ring buffer — newest last
  services: [],
  totalServerCount: 0,

  // Real-time
  realtime: false,
  userScrolledUp: false,
  wsUnsub: null,

  // Debounce
  searchTimer: null,

  // Expanded entries
  expandedIds: new Set(),

  // Virtual scroll
  visibleRange: { start: 0, end: 50 },

  // Refs
  listEl: null,
  statusBarEl: null,
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

function formatTimestamp(ts) {
  if (!ts) return '--';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '--';
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  const ms = String(d.getMilliseconds()).padStart(3, '0');
  return `${h}:${m}:${s}.${ms}`;
}

function formatDateFull(ts) {
  if (!ts) return '--';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '--';
  return d.toISOString().replace('T', ' ').slice(0, 23);
}

function logId(entry, index) {
  return entry.id || `log-${index}-${entry.timestamp || Date.now()}`;
}

function matchesLevel(entry, level) {
  if (level === 'ALL') return true;
  return (entry.level || '').toUpperCase() === level;
}

function matchesSearch(entry, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  const msg = (entry.message || '').toLowerCase();
  const svc = (entry.service || '').toLowerCase();
  const det = (entry.details || '');
  const detStr = typeof det === 'string' ? det.toLowerCase() : JSON.stringify(det).toLowerCase();
  return msg.includes(q) || svc.includes(q) || detStr.includes(q);
}

function matchesTimeRange(entry, since, until) {
  const ts = new Date(entry.timestamp || 0).getTime();
  if (since && ts < since) return false;
  if (until && ts > until) return false;
  return true;
}

function getFilteredLogs() {
  return _state.logs.filter((e) => {
    if (!matchesLevel(e, _state.level)) return false;
    if (!matchesSearch(e, _state.search)) return false;
    if (!matchesTimeRange(e, _state.since, _state.until)) return false;
    if (_state.service !== 'all' && e.service !== _state.service) return false;
    return true;
  });
}

/* ── HTML Renderers ─────────────────────────────────────────────────────── */

function renderPage(container) {
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

  const filtered = getFilteredLogs();
  const liveClass = _state.realtime ? 'logs-live--active' : '';

  container.innerHTML = html`
    <!-- Page Header -->
    <div class="logs-header">
      <div class="logs-header__top">
        <div>
          <h1 style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); margin: 0;">
            Logs
          </h1>
          <p style="font-size: var(--font-size-sm); color: var(--text-muted); margin: 2px 0 0 0;">
            System activity and diagnostics
          </p>
        </div>
        <div class="logs-header__controls">
          <select class="logs-service-select" id="logs-service-select"
                  title="Filter by service"
                  style="padding: 4px 8px; font-size: var(--font-size-xs); background: var(--surface); color: var(--text-primary); border: 1px solid var(--border); border-radius: var(--radius-md);">
            <option value="all">All Services</option>
            ${_state.services.map((s) => html`
              <option value="${esc(s)}" ${_state.service === s ? 'selected' : ''}>${esc(s)}</option>
            `)}
          </select>
          <button class="c-btn c-btn--sm c-btn--icon ${liveClass}" id="logs-realtime-btn"
                  title="Toggle real-time streaming"
                  style="${_state.realtime ? 'color: var(--success); border-color: var(--success);' : ''}">
            ${_state.realtime ? ICONS.pause : ICONS.play}
          </button>
        </div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="logs-toolbar">
      <div class="logs-toolbar__row">
        <!-- Level filter buttons -->
        <div class="logs-level-filters">
          ${LOG_LEVELS.map((lvl) => html`
            <button class="logs-level-btn ${_state.level === lvl ? 'logs-level-btn--active' : ''}"
                    data-level="${lvl}"
                    style="${_state.level === lvl ? `background: ${LEVEL_BG[lvl] || 'var(--accent-muted)'}; color: ${LEVEL_COLORS[lvl] || 'var(--accent)'}; border-color: ${LEVEL_COLORS[lvl] || 'var(--accent)'};` : ''}">
              ${lvl}
            </button>
          `)}
        </div>

        <!-- Search -->
        <div class="logs-search-wrap">
          <span class="logs-search-icon">${ICONS.search}</span>
          <input type="text" class="logs-search-input" id="logs-search-input"
                 placeholder="Search logs…" value="${esc(_state.search)}"
                 style="padding-left: 28px;" />
        </div>

        <!-- Time presets -->
        <select class="logs-time-preset" id="logs-time-preset"
                style="padding: 4px 8px; font-size: var(--font-size-xs); background: var(--surface); color: var(--text-primary); border: 1px solid var(--border); border-radius: var(--radius-md);">
          ${TIME_PRESETS.map((p) => {
            let val = p.value;
            if (typeof val === 'number') val = `ms-${val}`;
            const isSelected = (
              (p.value === 'all' && !_state.since && !_state.until) ||
              (p.value === 'today' && _state.since === _todayStart()) ||
              (typeof p.value === 'number' && _state.since === Date.now() - p.value)
            );
            return html`<option value="${val}" ${isSelected ? 'selected' : ''}>${p.label}</option>`;
          })}
        </select>

        <!-- Action buttons -->
        <button class="c-btn c-btn--sm c-btn--ghost" id="logs-clear-btn" title="Clear log view">
          <span class="c-btn__icon">${ICONS.trash}</span>
          Clear
        </button>
        <button class="c-btn c-btn--sm c-btn--ghost" id="logs-export-btn" title="Export as .txt">
          <span class="c-btn__icon">${ICONS.download}</span>
          Export
        </button>
      </div>
    </div>

    <!-- New logs banner (appears when user has scrolled up in real-time mode) -->
    <div class="logs-new-banner" id="logs-new-banner" style="display: none;">
      <button class="c-btn c-btn--sm c-btn--primary" id="logs-new-btn">
        <span class="c-btn__icon" style="animation: pulseSoft 2s ease-in-out infinite;">${ICONS.arrowDown}</span>
        New logs available
      </button>
    </div>

    <!-- Log List -->
    <div class="logs-list" id="logs-list">
      ${filtered.length === 0
        ? html`
            <div class="empty-state" style="margin-top: 10vh;">
              <div class="empty-state__icon" style="color: var(--text-muted);">${ICONS.info}</div>
              <div class="empty-state__title">No logs match your filters</div>
              <div class="empty-state__description">
                Try adjusting the level, search, or time range.
              </div>
            </div>
          `
        : filtered.map((entry, idx) => renderLogEntry(entry, idx))
      }
    </div>

    <!-- Status Bar -->
    <div class="logs-statusbar" id="logs-statusbar">
      <span id="logs-count-total">Total: ${_state.totalServerCount || _state.logs.length}</span>
      <span class="logs-statusbar__sep">·</span>
      <span id="logs-count-visible">Visible: ${filtered.length}</span>
      ${_state.realtime ? html`
        <span class="logs-statusbar__sep">·</span>
        <span class="logs-statusbar__live" id="logs-live-indicator">
          <span class="logs-statusbar__live-dot"></span>
          Live
        </span>
      ` : ''}
    </div>
  `;

  mountComponents(container);
}

function renderLogEntry(entry, index) {
  const level = (entry.level || 'INFO').toUpperCase();
  const levelColor = LEVEL_COLORS[level] || 'var(--text-secondary)';
  const levelBg = LEVEL_BG[level] || 'transparent';
  const id = logId(entry, index);
  const isExpanded = _state.expandedIds.has(id);
  const hasDetails = entry.details != null && entry.details !== '';
  const detailsJson = hasDetails
    ? (typeof entry.details === 'object' ? JSON.stringify(entry.details, null, 2) : String(entry.details))
    : '';

  return html`
    <div class="logs-entry ${isExpanded ? 'logs-entry--expanded' : ''}"
         data-log-id="${id}"
         style="animation: fadeIn var(--transition-fast) ease forwards;">
      <div class="logs-entry__main" data-log-toggle>
        <span class="logs-entry__time" title="${esc(formatDateFull(entry.timestamp))}">
          ${esc(formatTimestamp(entry.timestamp))}
        </span>
        <span class="logs-entry__badge" style="color: ${levelColor}; background: ${levelBg}; border-color: ${levelColor};">
          ${level}
        </span>
        <span class="logs-entry__service" title="${esc(entry.service || '')}">
          ${esc(entry.service || '—')}
        </span>
        <span class="logs-entry__message">
          ${esc(entry.message || '')}
        </span>
        <span class="logs-entry__actions">
          ${hasDetails ? html`
            <button class="c-btn c-btn--icon c-btn--ghost logs-entry__expand-btn"
                    data-log-expand="${id}" title="Toggle details"
                    style="width: 22px; height: 22px; min-width: 22px;">
              ${isExpanded ? ICONS.chevronUp : ICONS.chevronDown}
            </button>
          ` : ''}
          <button class="c-btn c-btn--icon c-btn--ghost logs-entry__copy-btn"
                  data-log-copy="${id}" title="Copy entry"
                  style="width: 22px; height: 22px; min-width: 22px;">
            ${ICONS.copy}
          </button>
        </span>
      </div>
      ${isExpanded && hasDetails ? html`
        <div class="logs-entry__details">
          <pre style="margin: 0; font-size: var(--font-size-xs); line-height: 1.6; white-space: pre-wrap; word-break: break-all;">${esc(detailsJson)}</pre>
        </div>
      ` : ''}
    </div>
  `;
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-6);">
        ${skeletonHeading({ width: '160px' })}
        ${skeletonText({ width: '200px' })}
      </div>
      <div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-4);">
        ${Array.from({ length: 5 }, () => skeletonButton({ width: '56px' }))}
        ${skeletonButton({ width: '180px' })}
      </div>
      <div style="display: flex; flex-direction: column; gap: 2px;">
        ${Array.from({ length: 15 }, () => html`
          <div style="display: flex; gap: var(--space-3); padding: 8px 0; border-bottom: 1px solid var(--border-subtle); align-items: center;">
            <div class="c-skeleton" style="width: 80px; height: 14px; border-radius: var(--radius-sm); flex-shrink: 0;"></div>
            <div class="c-skeleton" style="width: 48px; height: 18px; border-radius: var(--radius-full); flex-shrink: 0;"></div>
            <div class="c-skeleton" style="width: 100px; height: 14px; border-radius: var(--radius-sm); flex-shrink: 0;"></div>
            <div class="c-skeleton" style="flex: 1; height: 14px; border-radius: var(--radius-sm);"></div>
          </div>
        `)}
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
      <div class="empty-state__title">Failed to Load Logs</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to fetch logs from the backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="logs-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#logs-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    loadInitialData();
  });
}

/* ── Component Mounting / Event Binding ─────────────────────────────────── */

function mountComponents(container) {
  _state.listEl = container.querySelector('#logs-list');
  _state.statusBarEl = container.querySelector('#logs-statusbar');

  // Service selector
  container.querySelector('#logs-service-select')?.addEventListener('change', (e) => {
    _state.service = e.target.value;
    reapplyFilters();
  });

  // Real-time toggle
  container.querySelector('#logs-realtime-btn')?.addEventListener('click', () => {
    _state.realtime = !_state.realtime;
    if (_state.realtime) {
      _state.userScrolledUp = false;
      scrollToBottom();
    }
    reapplyFilters();
  });

  // Level filter buttons
  container.querySelectorAll('.logs-level-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      _state.level = btn.dataset.level;
      reapplyFilters();
    });
  });

  // Search input — debounced
  const searchInput = container.querySelector('#logs-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      if (_state.searchTimer) clearTimeout(_state.searchTimer);
      _state.searchTimer = setTimeout(() => {
        _state.search = searchInput.value;
        reapplyFilters();
      }, SEARCH_DEBOUNCE_MS);
    });
  }

  // Time preset selector
  container.querySelector('#logs-time-preset')?.addEventListener('change', (e) => {
    const val = e.target.value;
    if (val === 'all') {
      _state.since = null;
      _state.until = null;
    } else if (val === 'today') {
      _state.since = _todayStart();
      _state.until = null;
    } else if (val.startsWith('ms-')) {
      const ms = parseInt(val.slice(3), 10);
      _state.since = Date.now() - ms;
      _state.until = null;
    }
    loadLogs();
  });

  // Clear button
  container.querySelector('#logs-clear-btn')?.addEventListener('click', () => {
    _state.logs = [];
    _state.totalServerCount = 0;
    reapplyFilters();
  });

  // Export button
  container.querySelector('#logs-export-btn')?.addEventListener('click', exportLogs);

  // New logs banner
  container.querySelector('#logs-new-btn')?.addEventListener('click', () => {
    _state.userScrolledUp = false;
    scrollToBottom();
    container.querySelector('#logs-new-banner').style.display = 'none';
  });

  // Log entry events (delegated)
  const listEl = _state.listEl;
  if (listEl) {
    // Toggle expand
    listEl.addEventListener('click', (e) => {
      const expandBtn = e.target.closest('[data-log-expand]');
      const copyBtn = e.target.closest('[data-log-copy]');
      const toggleEl = e.target.closest('[data-log-toggle]');

      if (expandBtn) {
        const id = expandBtn.dataset.logExpand;
        if (_state.expandedIds.has(id)) {
          _state.expandedIds.delete(id);
        } else {
          _state.expandedIds.add(id);
        }
        reapplyFilters();
        return;
      }

      if (copyBtn) {
        const id = copyBtn.dataset.logCopy;
        copyLogEntry(id);
        return;
      }

      if (toggleEl) {
        const entry = toggleEl.closest('.logs-entry');
        if (entry) {
          const id = entry.dataset.logId;
          if (id) {
            if (_state.expandedIds.has(id)) {
              _state.expandedIds.delete(id);
            } else {
              _state.expandedIds.add(id);
            }
            reapplyFilters();
          }
        }
      }
    });
  }

  // Scroll detection for auto-scroll pause
  if (listEl) {
    listEl.addEventListener('scroll', handleScroll);
  }
}

/* ── Scroll Handling ────────────────────────────────────────────────────── */

function handleScroll() {
  if (!_state.listEl || _state.destroyed) return;

  const { scrollTop, scrollHeight, clientHeight } = _state.listEl;
  const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

  if (_state.realtime) {
    if (!isAtBottom && !_state.userScrolledUp) {
      _state.userScrolledUp = true;
      showNewBanner();
    } else if (isAtBottom && _state.userScrolledUp) {
      _state.userScrolledUp = false;
      hideNewBanner();
    }
  }
}

function scrollToBottom() {
  if (!_state.listEl) return;
  requestAnimationFrame(() => {
    _state.listEl.scrollTop = _state.listEl.scrollHeight;
  });
}

function showNewBanner() {
  const banner = _state.container?.querySelector('#logs-new-banner');
  if (banner) banner.style.display = 'flex';
}

function hideNewBanner() {
  const banner = _state.container?.querySelector('#logs-new-banner');
  if (banner) banner.style.display = 'none';
}

/* ── Export ─────────────────────────────────────────────────────────────── */

function exportLogs() {
  const filtered = getFilteredLogs();
  if (filtered.length === 0) return;

  const lines = filtered.map((entry) => {
    const ts = formatDateFull(entry.timestamp);
    const lvl = (entry.level || 'INFO').toUpperCase();
    const svc = entry.service || '—';
    const msg = entry.message || '';
    let text = `[${ts}] [${lvl}] [${svc}] ${msg}`;
    if (entry.details) {
      const det = typeof entry.details === 'object'
        ? JSON.stringify(entry.details, null, 2)
        : String(entry.details);
      text += `\n${det}`;
    }
    return text;
  }).join('\n');

  const blob = new Blob([lines], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `fiona-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/* ── Copy Entry ─────────────────────────────────────────────────────────── */

function copyLogEntry(id) {
  const entry = _state.logs.find((e, i) => logId(e, i) === id);
  if (!entry) return;

  const ts = formatDateFull(entry.timestamp);
  const lvl = (entry.level || 'INFO').toUpperCase();
  const svc = entry.service || '—';
  const msg = entry.message || '';
  let text = `[${ts}] [${lvl}] [${svc}] ${msg}`;
  if (entry.details) {
    const det = typeof entry.details === 'object'
      ? JSON.stringify(entry.details, null, 2)
      : String(entry.details);
    text += `\n${det}`;
  }

  navigator.clipboard.writeText(text).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  });
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadInitialData() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.error = true;
    _state.errorMessage = 'API client not available.';
    _state.loading = false;
    if (_state.container) renderPage(_state.container);
    return;
  }

  try {
    const [logsResult, servicesResult] = await Promise.all([
      api.get('/api/v1/logs', { limit: LOG_PAGE_SIZE, offset: 0 }),
      api.get('/api/v1/logs/services'),
    ]);

    const logs = Array.isArray(logsResult?.data) ? logsResult.data
      : Array.isArray(logsResult) ? logsResult
      : [];
    const services = Array.isArray(servicesResult?.data) ? servicesResult.data
      : Array.isArray(servicesResult) ? servicesResult
      : [];

    appendLogs(logs);
    _state.services = services;
    _state.totalServerCount = logsResult?.meta?.total || logs.length;
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }

    // Subscribe to WebSocket for real-time
    subscribeToLogs();
  } catch (err) {
    console.error('[logs] Failed to load data:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch logs.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
  }
}

async function loadLogs() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  try {
    const params = { limit: LOG_PAGE_SIZE, offset: 0 };
    if (_state.level !== 'ALL') params.level = _state.level.toLowerCase();
    if (_state.search) params.search = _state.search;
    if (_state.since) params.since = new Date(_state.since).toISOString();
    if (_state.until) params.until = new Date(_state.until).toISOString();

    const result = await api.get('/api/v1/logs', params);
    const logs = Array.isArray(result?.data) ? result.data
      : Array.isArray(result) ? result
      : [];

    _state.logs = [];
    appendLogs(logs);
    _state.totalServerCount = result?.meta?.total || logs.length;

    if (!_state.destroyed && _state.container) {
      reapplyFilters();
    }
  } catch (err) {
    console.error('[logs] Failed to load logs:', err);
  }
}

function appendLogs(newLogs) {
  if (!Array.isArray(newLogs) || newLogs.length === 0) return;

  for (const entry of newLogs) {
    _state.logs.push(entry);
    if (_state.logs.length > MAX_CACHED_LOGS) {
      _state.logs.shift();
    }
  }
}

function reapplyFilters() {
  if (_state.destroyed || !_state.container) return;
  renderPage(_state.container);
}

/* ── WebSocket ──────────────────────────────────────────────────────────── */

function subscribeToLogs() {
  const api = getApi();
  if (!api) return;

  _state.wsUnsub = api.on(WS_EVENT_LOG, (params) => {
    if (_state.destroyed) return;

    // Ingest the incoming log entry
    const entry = params?.data || params;
    if (!entry) return;

    // Add to ring buffer
    _state.logs.push(entry);
    if (_state.logs.length > MAX_CACHED_LOGS) {
      _state.logs.shift();
    }

    // Update total count
    _state.totalServerCount++;

    // If real-time is on and user hasn't scrolled up, auto-append
    if (_state.realtime && !_state.userScrolledUp && _state.listEl) {
      // Check if level filter matches
      if (!matchesLevel(entry, _state.level)) return;
      if (!matchesSearch(entry, _state.search)) return;
      if (!matchesTimeRange(entry, _state.since, _state.until)) return;
      if (_state.service !== 'all' && entry.service !== _state.service) return;

      // Append the entry to the DOM directly
      const entryHtml = renderLogEntry(entry, _state.logs.length - 1);
      _state.listEl.insertAdjacentHTML('beforeend', entryHtml);

      // Update status bar
      updateStatusBar();

      // Auto-scroll
      scrollToBottom();
    } else if (_state.realtime && _state.userScrolledUp) {
      // Show "new logs" banner
      showNewBanner();
      // Also update status bar
      updateStatusBar();
    }
  });
}

function unsubscribeFromLogs() {
  if (_state.wsUnsub) {
    _state.wsUnsub();
    _state.wsUnsub = null;
  }
}

/* ── Status Bar Updates ─────────────────────────────────────────────────── */

function updateStatusBar() {
  if (_state.destroyed || !_state.container) return;
  const totalEl = _state.container.querySelector('#logs-count-total');
  const visibleEl = _state.container.querySelector('#logs-count-visible');
  const filtered = getFilteredLogs();
  if (totalEl) totalEl.textContent = `Total: ${_state.totalServerCount || _state.logs.length}`;
  if (visibleEl) visibleEl.textContent = `Visible: ${filtered.length}`;
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function _todayStart() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/* ── Polling for services (fallback if no initial load) ─────────────────── */

async function loadServices() {
  const api = getApi();
  if (!api) return;
  try {
    const result = await api.get('/api/v1/logs/services');
    const services = Array.isArray(result?.data) ? result.data
      : Array.isArray(result) ? result
      : [];
    _state.services = services;
    if (!_state.destroyed && _state.container) {
      const select = _state.container.querySelector('#logs-service-select');
      if (select) {
        const currentVal = select.value;
        select.innerHTML = `
          <option value="all">All Services</option>
          ${html.raw(services.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join(''))}
        `;
        select.value = currentVal;
      }
    }
  } catch { /* ignore */ }
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
  loadInitialData();
}

/**
 * Mount — called by router after render() inserts HTML.
 * @param {Element} container
 */
export function mount(container) {
  // mount() is called by the router after render().
  // Our event binding is done inside renderPage -> mountComponents.
  // We just ensure the container is set.
  _state.container = container;
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  unsubscribeFromLogs();

  if (_state.searchTimer) {
    clearTimeout(_state.searchTimer);
    _state.searchTimer = null;
  }

  _state.container = null;
  _state.logs = [];
  _state.services = [];
  _state.expandedIds = new Set();
  _state.listEl = null;
  _state.statusBarEl = null;
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
      return '<div id="logs-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#logs-root') || container;
      render(root);
    },
    destroy,
  };
}
