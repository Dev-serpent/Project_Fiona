/* ==========================================================================
   performance.js — Real-Time System Performance Metrics Dashboard
   ==========================================================================
   Displays CPU, memory, disk, and network metrics with live-updating
   metric cards, Canvas 2D time-series graphs, and a sortable process
   list.  Polls the backend on a configurable interval.
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
  skeletonTableRow,
  skeletonChart,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const MAX_HISTORY_POINTS = 60;
const PROCESS_PAGE_SIZE = 100;
const REFRESH_INTERVALS = [
  { value: 1000,  label: '1s' },
  { value: 5000,  label: '5s' },
  { value: 15000, label: '15s' },
  { value: 30000, label: '30s' },
  { value: 0,     label: 'Pause' },
];
const COLORS = {
  cpu:     '#00f0ff',
  cpuCore: ['#00f0ff', '#38bdf8', '#a855f7', '#22c55e', '#eab308', '#ef4444', '#f97316', '#8b5cf6'],
  memUsed: '#38bdf8',
  memCache: '#22c55e',
  memFree: '#64748b',
  netUp:   '#22c55e',
  netDown: '#38bdf8',
  disk:    '#a855f7',
};

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  // Polling
  refreshInterval: 5000,
  pollTimer: null,
  lastUpdated: null,
  paused: false,
  visibilityHidden: false,

  // Metrics data
  cpuPercent: 0,
  cpuPerCore: [],
  cpuCount: 0,
  memoryUsed: 0,
  memoryTotal: 0,
  memoryPercent: 0,
  memoryCached: 0,
  memorySwapTotal: 0,
  memorySwapUsed: 0,
  diskUsed: 0,
  diskTotal: 0,
  diskPercent: 0,
  mounts: [],
  networkUp: 0,
  networkDown: 0,

  // History arrays (for graphs)
  cpuHistory: [],         // array of { time, overall, cores[] }
  memoryHistory: [],      // array of { time, used, cached, free }
  networkHistory: [],     // array of { time, up, down }

  // Network delta tracking
  prevRxBytes: 0,
  prevTxBytes: 0,
  prevNetTime: 0,

  // Process list
  processes: [],
  processSort: 'cpu',
  processOrder: 'desc',
  processSearch: '',
  processPage: 1,
  processTotal: 0,
  processLoading: false,

  // Graph time range (seconds of history to show)
  graphTimeRange: 60,

  // Tooltip
  tooltipData: null,
  tooltipX: 0,
  tooltipY: 0,

  // Kill process dialog
  killTarget: null,

  // WebSocket unsubscribe
  wsUnsubscribe: null,

  // Canvas animation
  animFrame: null,
  hoveredChart: null,
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

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
}

function formatSpeed(bps) {
  if (bps === 0) return '0 Mbps';
  const mbps = (bps * 8) / (1024 * 1024);
  if (mbps < 0.01) return '<0.01 Mbps';
  return mbps.toFixed(2) + ' Mbps';
}

function formatTimestamp(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  const s = date.getSeconds().toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function timeAgo(timestamp) {
  const diff = Math.floor((Date.now() - timestamp) / 1000);
  if (diff < 5) return 'just now';
  return `${diff}s ago`;
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadMetrics() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) return;

  try {
    const result = await api.get('/api/v1/system/metrics');
    if (_state.destroyed) return;

    const metrics = result?.data || result;
    updateMetrics(metrics);
  } catch (err) {
    console.warn('[performance] Metrics poll failed:', err);
    if (!_state.error) {
      _state.error = true;
      _state.errorMessage = err.message || 'Failed to fetch metrics.';
      if (_state.container) renderPage(_state.container);
    }
  }
}

async function loadProcesses() {
  if (_state.destroyed || _state.processLoading) return;
  const api = getApi();
  if (!api) return;

  _state.processLoading = true;

  try {
    const result = await api.get('/api/v1/system/processes', {
      sort: _state.processSort,
      order: _state.processOrder,
      search: _state.processSearch || undefined,
      page: _state.processPage,
      per_page: PROCESS_PAGE_SIZE,
    });
    if (_state.destroyed) return;

    const data = result?.data || result;
    _state.processes = Array.isArray(data)
      ? data
      : Array.isArray(data?.processes)
        ? data.processes
        : data?.items || [];
    _state.processTotal = data?.total || _state.processes.length;
  } catch (err) {
    console.warn('[performance] Process list failed:', err);
    // Keep existing process data on failure
  } finally {
    _state.processLoading = false;
    if (!_state.destroyed && _state.container) {
      updateProcessTable();
    }
  }
}

function updateMetrics(metrics) {
  if (_state.destroyed) return;

  // Update CPU
  _state.cpuPercent = metrics.cpu_percent ?? 0;
  _state.cpuPerCore = metrics.cpu_per_core || [];
  _state.cpuCount = metrics.cpu_count || _state.cpuPerCore.length || 0;

  // Update Memory
  const mem = metrics.memory || {};
  _state.memoryUsed = mem.used_gb ?? 0;
  _state.memoryTotal = mem.total_gb ?? 0;
  _state.memoryPercent = mem.percent_used ?? 0;
  _state.memoryCached = mem.cached_gb ?? 0;
  _state.memorySwapTotal = mem.swap_total_gb ?? 0;
  _state.memorySwapUsed = mem.swap_used_gb ?? 0;

  // Update Disk
  const disk = metrics.disk || {};
  _state.diskUsed = disk.used_gb ?? 0;
  _state.diskTotal = disk.total_gb ?? 0;
  _state.diskPercent = disk.percent_used ?? 0;
  _state.mounts = disk.mounts || [];

  // Update Network
  const net = metrics.network || {};
  const now = Date.now();
  const rxBytes = net.rx_bytes ?? metrics.rx_bytes ?? 0;
  const txBytes = net.tx_bytes ?? metrics.tx_bytes ?? 0;

  if (_state.prevRxBytes > 0 && _state.prevNetTime > 0) {
    const dt = (now - _state.prevNetTime) / 1000;
    if (dt > 0) {
      _state.networkDown = ((rxBytes - _state.prevRxBytes) * 8) / dt;
      _state.networkUp = ((txBytes - _state.prevTxBytes) * 8) / dt;
    }
  }
  _state.prevRxBytes = rxBytes;
  _state.prevTxBytes = txBytes;
  _state.prevNetTime = now;

  // Append to history
  const ts = Date.now();
  _state.cpuHistory.push({
    time: ts,
    overall: _state.cpuPercent,
    cores: [..._state.cpuPerCore],
  });
  if (_state.cpuHistory.length > MAX_HISTORY_POINTS) _state.cpuHistory.shift();

  _state.memoryHistory.push({
    time: ts,
    used: _state.memoryUsed,
    cached: _state.memoryCached,
    free: (_state.memoryTotal - _state.memoryUsed - _state.memoryCached),
  });
  if (_state.memoryHistory.length > MAX_HISTORY_POINTS) _state.memoryHistory.shift();

  _state.networkHistory.push({
    time: ts,
    up: _state.networkUp,
    down: _state.networkDown,
  });
  if (_state.networkHistory.length > MAX_HISTORY_POINTS) _state.networkHistory.shift();

  _state.lastUpdated = new Date();
  _state.error = false;
  _state.loading = false;

  // Update UI
  if (_state.container) {
    updateMetricCards();
    updateTimestamp();
    drawCharts();
  }
}

/* ── HTML Rendering ─────────────────────────────────────────────────────── */

function renderPage(container) {
  if (_state.destroyed) return;
  _state.container = container;

  if (_state.loading) {
    renderSkeletons(container);
    return;
  }

  if (_state.error && !_state.lastUpdated) {
    renderError(container);
    return;
  }

  const intervalLabel = REFRESH_INTERVALS.find(i => i.value === _state.refreshInterval)?.label || '5s';
  const timeAgoText = _state.lastUpdated
    ? `Updated ${timeAgo(_state.lastUpdated)}`
    : 'Waiting for data…';

  container.innerHTML = html`
    <!-- Page Header -->
    <div style="margin-bottom: var(--space-5);" id="perf-header">
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3);">
        <div>
          <h1 style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); margin: 0;">
            Performance
          </h1>
          <p style="font-size: var(--font-size-sm); color: var(--text-muted); margin: 2px 0 0 0;">
            Real-time system resource monitoring
          </p>
        </div>
        <div style="display: flex; align-items: center; gap: var(--space-3);">
          <span style="font-size: var(--font-size-xs); color: var(--text-muted);" id="perf-timestamp">
            ${esc(timeAgoText)}
          </span>
          <span style="display: flex; align-items: center; gap: var(--space-1);">
            <span style="font-size: var(--font-size-xs); color: var(--text-muted);">Interval:</span>
            <select class="c-select c-select--sm" id="perf-interval"
                    style="width: auto; min-width: 80px; height: 30px; font-size: var(--font-size-xs); padding: 0 var(--space-3);">
              ${html.raw(REFRESH_INTERVALS.map((i) => html`
                <option value="${i.value}" ${_state.refreshInterval === i.value ? 'selected' : ''}>${esc(i.label)}</option>
              `).join(''))}
            </select>
          </span>
          <button class="c-btn c-btn--sm c-btn--ghost" id="perf-refresh-btn" title="Refresh now">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Top Row: 4 Metric Cards -->
    <div id="perf-metric-cards"
         style="display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); margin-bottom: var(--space-5);">
      ${renderCpuCard()}
      ${renderMemoryCard()}
      ${renderDiskCard()}
      ${renderNetworkCard()}
    </div>

    <!-- Middle: Time-Series Graphs -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-5);">
      <div class="c-card" id="chart-cpu-container">
        <div class="c-card__header">
          <span class="c-card__title">CPU Usage</span>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted);">last 60s</span>
        </div>
        <div class="c-card__body" style="position: relative;">
          <canvas id="chart-cpu" style="width: 100%; height: 180px;"></canvas>
          <div id="chart-cpu-tooltip" class="chart-tooltip" style="display: none; position: absolute; pointer-events: none;"></div>
        </div>
      </div>
      <div class="c-card" id="chart-memory-container">
        <div class="c-card__header">
          <span class="c-card__title">Memory</span>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted);">last 60s</span>
        </div>
        <div class="c-card__body" style="position: relative;">
          <canvas id="chart-memory" style="width: 100%; height: 180px;"></canvas>
          <div id="chart-memory-tooltip" class="chart-tooltip" style="display: none; position: absolute; pointer-events: none;"></div>
        </div>
      </div>
      <div class="c-card" id="chart-network-container">
        <div class="c-card__header">
          <span class="c-card__title">Network</span>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted);">last 60s</span>
        </div>
        <div class="c-card__body" style="position: relative;">
          <canvas id="chart-network" style="width: 100%; height: 180px;"></canvas>
          <div id="chart-network-tooltip" class="chart-tooltip" style="display: none; position: absolute; pointer-events: none;"></div>
        </div>
      </div>
      <div class="c-card" id="chart-combined-container">
        <div class="c-card__header">
          <span class="c-card__title">Combined Overview</span>
          <div style="display: flex; align-items: center; gap: var(--space-2);">
            ${html.raw([60, 300, 900, 3600].map((r) => html`
              <button class="c-btn c-btn--sm c-btn--ghost${_state.graphTimeRange === r ? ' c-btn--primary' : ''}"
                      data-action="time-range" data-range="${r}"
                      style="font-size: var(--font-size-xxs); padding: 2px 8px;">
                ${r >= 60 ? Math.floor(r / 60) + 'm' : r + 's'}
              </button>
            `).join(''))}
          </div>
        </div>
        <div class="c-card__body" style="position: relative;">
          <canvas id="chart-combined" style="width: 100%; height: 180px;"></canvas>
          <div id="chart-combined-tooltip" class="chart-tooltip" style="display: none; position: absolute; pointer-events: none;"></div>
        </div>
      </div>
    </div>

    <!-- Bottom: Process List -->
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">Processes</span>
        <div style="display: flex; align-items: center; gap: var(--space-3);">
          <div class="c-input-wrapper" style="width: 200px;">
            <span class="c-input-wrapper__icon c-input-wrapper__icon--left">${ICONS.search}</span>
            <input type="text" class="c-input c-input--sm" id="perf-process-search"
                   placeholder="Filter by name…"
                   value="${esc(_state.processSearch)}"
                   style="padding-left: 32px;">
          </div>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted);">
            ${_state.processTotal} processes
          </span>
        </div>
      </div>
      <div style="overflow-x: auto;">
        <table class="c-table" id="perf-process-table">
          <thead>
            <tr>
              ${html.raw(['PID', 'Name', 'CPU%', 'Memory%', 'Status', 'User', ''].map((col, i) => {
                const sortKey = ['pid', 'name', 'cpu', 'mem', 'status', 'user', ''][i];
                if (!sortKey) return html`<th style="width: 50px;">Actions</th>`;
                const isSorted = _state.processSort === sortKey;
                const arrow = isSorted
                  ? (_state.processOrder === 'asc' ? ' ▲' : ' ▼')
                  : '';
                return html`
                  <th class="c-table th--sortable${isSorted ? ' th--sorted' : ''}"
                      data-action="sort-process" data-sort="${sortKey}"
                      style="cursor: pointer; user-select: none;">
                    ${esc(col)}${arrow ? html`<span style="margin-left: 2px;">${arrow}</span>` : ''}
                  </th>
                `;
              }).join(''))}
            </tr>
          </thead>
          <tbody id="perf-process-tbody">
            ${html.raw(renderProcessRows())}
          </tbody>
        </table>
      </div>
      ${_state.processTotal > PROCESS_PAGE_SIZE ? html`
        <div class="c-card__footer" style="justify-content: center; gap: var(--space-2);">
          <button class="c-btn c-btn--sm c-btn--ghost" data-action="page-process" data-page="${_state.processPage - 1}"
                  ${_state.processPage <= 1 ? 'disabled' : ''}>
            Previous
          </button>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted);">
            Page ${_state.processPage} of ${Math.ceil(_state.processTotal / PROCESS_PAGE_SIZE)}
          </span>
          <button class="c-btn c-btn--sm c-btn--ghost" data-action="page-process" data-page="${_state.processPage + 1}"
                  ${_state.processPage * PROCESS_PAGE_SIZE >= _state.processTotal ? 'disabled' : ''}>
            Next
          </button>
        </div>
      ` : ''}
    </div>
  `;

  mountPageComponents(container);
}

function renderCpuCard() {
  const pct = _state.cpuPercent || 0;
  const cores = _state.cpuPerCore.length > 0 ? _state.cpuPerCore : [_state.cpuPercent];
  const count = _state.cpuCount || cores.length;

  return html`
    <div class="c-card" style="position: relative; overflow: hidden;">
      <div class="c-card__body">
        <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2);">
          <div style="width: 24px; height: 24px; border-radius: var(--radius-md); background: ${COLORS.cpu}20; display: flex; align-items: center; justify-content: center; color: ${COLORS.cpu};">
            ${ICONS.activity}
          </div>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">CPU</span>
        </div>
        <div style="display: flex; align-items: baseline; gap: 4px; margin-bottom: var(--space-2);">
          <span style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); font-variant-numeric: tabular-nums;" id="perf-cpu-val">
            ${pct.toFixed(1)}
          </span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted);">%</span>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted); margin-left: auto;">${count} cores</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 2px;" id="perf-cpu-cores">
          ${html.raw(cores.map((corePct, i) => html`
            <div style="display: flex; align-items: center; gap: var(--space-2);">
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted); width: 20px; text-align: right; font-variant-numeric: tabular-nums;">${i + 1}</span>
              <div class="c-progress c-progress--sm" style="flex: 1;">
                <div class="c-progress__bar" style="width: ${corePct}%; background: ${COLORS.cpuCore[i % COLORS.cpuCore.length]};"></div>
              </div>
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted); width: 32px; text-align: right; font-variant-numeric: tabular-nums;">${(corePct || 0).toFixed(0)}%</span>
            </div>
          `).join(''))}
        </div>
      </div>
    </div>
  `;
}

function renderMemoryCard() {
  const total = _state.memoryTotal || 0;
  const used = _state.memoryUsed || 0;
  const pct = _state.memoryPercent || 0;
  const swapUsed = _state.memorySwapUsed || 0;
  const swapTotal = _state.memorySwapTotal || 0;
  const cached = _state.memoryCached || 0;

  return html`
    <div class="c-card">
      <div class="c-card__body">
        <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2);">
          <div style="width: 24px; height: 24px; border-radius: var(--radius-md); background: ${COLORS.memUsed}20; display: flex; align-items: center; justify-content: center; color: ${COLORS.memUsed};">
            ${ICONS.info}
          </div>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Memory</span>
        </div>
        <div style="display: flex; align-items: baseline; gap: 4px; margin-bottom: var(--space-2);">
          <span style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); font-variant-numeric: tabular-nums;" id="perf-mem-val">
            ${used.toFixed(1)}
          </span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted);">GB / ${total.toFixed(1)} GB</span>
        </div>
        <div class="c-progress" style="margin-bottom: var(--space-2); height: 8px;">
          <div class="c-progress__bar" style="width: ${pct}%; background: ${COLORS.memUsed};"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: var(--font-size-xxs); color: var(--text-muted);">
          <span>${pct.toFixed(1)}% used</span>
          <span>${cached.toFixed(1)} GB cached</span>
        </div>
        ${swapTotal > 0 ? html`
          <div style="margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-subtle); display: flex; justify-content: space-between; font-size: var(--font-size-xs); color: var(--text-muted);">
            <span>Swap: ${swapUsed.toFixed(1)} GB / ${swapTotal.toFixed(1)} GB</span>
            <span>${swapTotal > 0 ? ((swapUsed / swapTotal) * 100).toFixed(1) : 0}%</span>
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function renderDiskCard() {
  const total = _state.diskTotal || 0;
  const used = _state.diskUsed || 0;
  const pct = _state.diskPercent || 0;
  const mounts = _state.mounts || [];

  return html`
    <div class="c-card">
      <div class="c-card__body">
        <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2);">
          <div style="width: 24px; height: 24px; border-radius: var(--radius-md); background: ${COLORS.disk}20; display: flex; align-items: center; justify-content: center; color: ${COLORS.disk};">
            ${ICONS.folder}
          </div>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Disk</span>
        </div>
        <div style="display: flex; align-items: baseline; gap: 4px; margin-bottom: var(--space-2);">
          <span style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); font-variant-numeric: tabular-nums;" id="perf-disk-val">
            ${used.toFixed(1)}
          </span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted);">GB / ${total.toFixed(1)} GB</span>
        </div>
        <div class="c-progress" style="margin-bottom: var(--space-1);">
          <div class="c-progress__bar" style="width: ${pct}%; background: ${COLORS.disk};"></div>
        </div>
        <div style="font-size: var(--font-size-xxs); color: var(--text-muted);">
          ${pct.toFixed(1)}% used
        </div>
        ${mounts.length > 0 ? html`
          <div style="margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-subtle);">
            ${html.raw(mounts.slice(0, 3).map((m) => html`
              <div style="display: flex; justify-content: space-between; font-size: var(--font-size-xxs); color: var(--text-muted); padding: 1px 0;">
                <span>${esc(m.mount || m.mount_point || '')}</span>
                <span>${(m.percent_used || 0).toFixed(0)}%</span>
              </div>
            `).join(''))}
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function renderNetworkCard() {
  const up = _state.networkUp || 0;
  const down = _state.networkDown || 0;

  return html`
    <div class="c-card">
      <div class="c-card__body">
        <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2);">
          <div style="width: 24px; height: 24px; border-radius: var(--radius-md); background: ${COLORS.netDown}20; display: flex; align-items: center; justify-content: center; color: ${COLORS.netDown};">
            ${ICONS.globe}
          </div>
          <span style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Network</span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3);">
          <div>
            <div style="display: flex; align-items: center; gap: var(--space-1); margin-bottom: 2px;">
              <span style="width: 8px; height: 8px; border-radius: 50%; background: ${COLORS.netDown}; flex-shrink: 0;"></span>
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted); text-transform: uppercase;">Down</span>
            </div>
            <span style="font-size: var(--font-size-lg); font-weight: var(--font-weight-bold); color: var(--text-primary); font-variant-numeric: tabular-nums;" id="perf-net-down">
              ${formatSpeed(down)}
            </span>
          </div>
          <div>
            <div style="display: flex; align-items: center; gap: var(--space-1); margin-bottom: 2px;">
              <span style="width: 8px; height: 8px; border-radius: 50%; background: ${COLORS.netUp}; flex-shrink: 0;"></span>
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted); text-transform: uppercase;">Up</span>
            </div>
            <span style="font-size: var(--font-size-lg); font-weight: var(--font-weight-bold); color: var(--text-primary); font-variant-numeric: tabular-nums;" id="perf-net-up">
              ${formatSpeed(up)}
            </span>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderProcessRows() {
  const rows = _state.processes || [];
  if (rows.length === 0) {
    return html`
      <tr>
        <td colspan="7" style="text-align: center; padding: var(--space-6); color: var(--text-muted);">
          ${_state.processLoading ? 'Loading…' : 'No processes found.'}
        </td>
      </tr>
    `;
  }

  return html.raw(rows.map((proc) => html`
    <tr style="cursor: pointer;" data-action="show-process" data-pid="${proc.pid || ''}">
      <td style="font-family: var(--font-mono); font-size: var(--font-size-xs);">${proc.pid ?? '—'}</td>
      <td><span style="max-width: 200px; display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${esc(proc.name || proc.command || '—')}</span></td>
      <td style="font-variant-numeric: tabular-nums;">${proc.cpu != null ? proc.cpu + '%' : proc.cpu_percent != null ? proc.cpu_percent + '%' : '—'}</td>
      <td style="font-variant-numeric: tabular-nums;">${proc.mem != null ? proc.mem + '%' : proc.memory_percent != null ? proc.memory_percent + '%' : '—'}</td>
      <td>${esc(proc.status || proc.state || 'running')}</td>
      <td style="font-size: var(--font-size-xs);">${esc(proc.user || proc.username || '—')}</td>
      <td>
        <button class="c-btn c-btn--sm c-btn--ghost c-btn--danger" data-action="kill-process" data-pid="${proc.pid || ''}"
                title="Kill process ${proc.pid || ''}" style="padding: 2px 6px;">
          <span class="c-btn__icon">${ICONS.trash}</span>
        </button>
      </td>
    </tr>
  `).join(''));
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      ${skeletonHeading({ width: '200px' })}
      ${skeletonText({ width: '160px' })}
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); margin: var(--space-5) 0;">
        ${Array.from({ length: 4 }, () => skeletonCard({ height: '160px' }))}
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-5);">
        ${Array.from({ length: 2 }, () => skeletonChart({ height: '200px' }))}
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-5);">
        ${Array.from({ length: 2 }, () => skeletonChart({ height: '200px' }))}
      </div>
      ${skeletonTableRow({ columns: 6, rows: 5 })}
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
        ${esc(_state.errorMessage || 'Unable to reach the Fiona backend for metrics data.')}
      </div>
      <button class="c-btn c-btn--primary" id="perf-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry Connection
      </button>
    </div>
  `;

  container.querySelector('#perf-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadMetrics().then(() => {
      if (!_state.destroyed && _state.loading === false) {
        loadProcesses();
      }
    });
  });
}

/* ── UI Update Methods ──────────────────────────────────────────────────── */

function updateMetricCards() {
  const container = _state.container;
  if (!container) return;

  // We re-render the metric cards section in-place for simplicity
  const cardsEl = container.querySelector('#perf-metric-cards');
  if (!cardsEl) return;

  // Replace the inner HTML efficiently
  cardsEl.innerHTML = renderCpuCard() + renderMemoryCard() + renderDiskCard() + renderNetworkCard();

  // Update process table too
  updateProcessTable();
}

function updateProcessTable() {
  const tbody = _state.container?.querySelector('#perf-process-tbody');
  if (!tbody) return;
  tbody.innerHTML = renderProcessRows();

  // Re-bind process row events
  bindProcessEvents(_state.container);
}

function updateTimestamp() {
  const el = _state.container?.querySelector('#perf-timestamp');
  if (el && _state.lastUpdated) {
    el.textContent = `Updated ${timeAgo(_state.lastUpdated)}`;
  }
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountPageComponents(container) {
  // ── Refresh button ──
  container.querySelector('#perf-refresh-btn')?.addEventListener('click', () => {
    loadMetrics();
    loadProcesses();
  });

  // ── Interval selector ──
  container.querySelector('#perf-interval')?.addEventListener('change', (e) => {
    const val = parseInt(e.target.value, 10);
    _state.refreshInterval = val;
    _state.paused = val === 0;
    restartPolling();
  });

  // ── Process search ──
  const searchInput = container.querySelector('#perf-process-search');
  if (searchInput) {
    let searchTimer;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        _state.processSearch = e.target.value;
        _state.processPage = 1;
        loadProcesses();
      }, 300);
    });
  }

  // ── Process sort ──
  container.querySelectorAll('[data-action="sort-process"]').forEach((th) => {
    th.addEventListener('click', () => {
      const sort = th.dataset.sort;
      if (_state.processSort === sort) {
        _state.processOrder = _state.processOrder === 'asc' ? 'desc' : 'asc';
      } else {
        _state.processSort = sort;
        _state.processOrder = 'desc';
      }
      loadProcesses();
    });
  });

  // ── Process pagination ──
  container.querySelectorAll('[data-action="page-process"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const page = parseInt(btn.dataset.page, 10);
      if (page > 0) {
        _state.processPage = page;
        loadProcesses();
      }
    });
  });

  // ── Process row click → details ──
  bindProcessEvents(container);

  // ── Time range buttons ──
  container.querySelectorAll('[data-action="time-range"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      _state.graphTimeRange = parseInt(btn.dataset.range, 10);
      // Re-render chart area header buttons
      const parent = btn.closest('.c-card__header');
      if (parent) {
        parent.querySelectorAll('[data-action="time-range"]').forEach((b) => {
          b.classList.toggle('c-btn--primary', parseInt(b.dataset.range, 10) === _state.graphTimeRange);
        });
      }
      drawCharts();
    });
  });

  // ── Canvas chart drawing ──
  drawCharts();
  bindCanvasEvents(container);
}

function bindProcessEvents(container) {
  // Kill buttons
  container.querySelectorAll('[data-action="kill-process"]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const pid = btn.dataset.pid;
      if (pid) showKillDialog(pid);
    });
  });

  // Row click → details
  container.querySelectorAll('[data-action="show-process"]').forEach((row) => {
    row.addEventListener('click', () => {
      const pid = row.dataset.pid;
      if (pid) showProcessDetails(pid);
    });
  });
}

/* ── Kill Process Dialog ────────────────────────────────────────────────── */

function showKillDialog(pid) {
  _state.killTarget = pid;
  const modalContainer = document.getElementById('modal-container');
  if (!modalContainer) return;

  modalContainer.innerHTML = `
    <div class="c-modal-backdrop" id="kill-backdrop">
      <div class="c-modal c-modal--sm">
        <div class="c-modal__header">
          <h3 class="c-modal__title">Kill Process</h3>
          <button class="c-modal__close" data-action="close-modal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="c-modal__body">
          <p style="color: var(--text-secondary); font-size: var(--font-size-sm);">
            Are you sure you want to terminate process <strong>PID ${esc(pid)}</strong>?
          </p>
          <p style="color: var(--warning); font-size: var(--font-size-xs); margin-top: var(--space-2);">
            This will forcibly stop the process. Unsaved data may be lost.
          </p>
        </div>
        <div class="c-modal__footer">
          <button class="c-btn" data-action="cancel-kill">Cancel</button>
          <button class="c-btn c-btn--danger-solid" data-action="confirm-kill" data-pid="${esc(pid)}">
            Kill Process
          </button>
        </div>
      </div>
    </div>
  `;

  modalContainer.style.display = 'flex';

  const close = () => {
    modalContainer.innerHTML = '';
    modalContainer.style.display = 'none';
    _state.killTarget = null;
  };

  modalContainer.querySelector('[data-action="close-modal"]')?.addEventListener('click', close);
  modalContainer.querySelector('[data-action="cancel-kill"]')?.addEventListener('click', close);
  modalContainer.querySelector('#kill-backdrop')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) close();
  });
  modalContainer.querySelector('[data-action="confirm-kill"]')?.addEventListener('click', async (e) => {
    const targetPid = e.target.dataset.pid;
    close();
    await executeKill(targetPid);
  });
}

async function executeKill(pid) {
  const api = getApi();
  if (!api) return;

  try {
    await api.post(`/api/v1/system/kill/${pid}`);
    showBriefToast('success', `Process ${pid} terminated.`);
    loadProcesses();
  } catch (err) {
    showBriefToast('error', `Failed to kill process ${pid}: ${err.message}`);
  }
}

function showProcessDetails(pid) {
  // Lightweight detail view via toast
  const proc = (_state.processes || []).find((p) => String(p.pid) === String(pid));
  if (proc) {
    const detail = [
      `PID: ${proc.pid}`,
      `Name: ${proc.name || proc.command || '—'}`,
      `CPU: ${proc.cpu || proc.cpu_percent || '—'}%`,
      `Memory: ${proc.mem || proc.memory_percent || '—'}%`,
      `Status: ${proc.status || proc.state || 'running'}`,
      `User: ${proc.user || proc.username || '—'}`,
    ].join('\n');
    showBriefToast('info', detail, 5000);
  }
}

function showBriefToast(type, message, duration = 3000) {
  const toast = document.createElement('div');
  toast.className = `c-toast c-toast--${type || 'info'} animate-slide-right`;
  toast.style.cssText = 'position: fixed; bottom: 60px; right: 20px; z-index: 9999; max-width: 360px;';
  toast.innerHTML = `
    <div class="c-toast__icon">${ICONS[type === 'success' ? 'check' : type === 'error' ? 'error' : 'info']}</div>
    <div class="c-toast__content"><div class="c-toast__message" style="white-space: pre-line;">${esc(message)}</div></div>
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
  }, duration);
}

/* ── Canvas Chart Engine ────────────────────────────────────────────────── */

function drawCharts() {
  if (_state.destroyed) return;
  drawCpuChart();
  drawMemoryChart();
  drawNetworkChart();
  drawCombinedChart();
}

function getHistoryInRange(history) {
  // Filter history to within the selected time range
  if (_state.graphTimeRange >= 60) {
    // For 60s default, return all points
    return history;
  }
  const cutoff = Date.now() - (_state.graphTimeRange * 1000);
  return history.filter((h) => h.time >= cutoff);
}

function setupCanvas(canvas) {
  if (!canvas) return null;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  return { ctx, w: rect.width, h: rect.height };
}

function drawGrid(ctx, w, h, numLines) {
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth = 1;
  for (let i = 0; i < numLines; i++) {
    const y = (h / numLines) * (i + 1);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
}

function drawAxisLabels(ctx, w, h, minVal, maxVal) {
  const numLabels = 4;
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.font = '9px sans-serif';
  ctx.textAlign = 'right';
  for (let i = 0; i <= numLabels; i++) {
    const val = minVal + ((maxVal - minVal) / numLabels) * i;
    const y = h - ((val - minVal) / (maxVal - minVal || 1)) * h;
    ctx.fillText(val.toFixed(1), w - 4, y - 2);
  }
}

function drawLine(ctx, data, getY, color, w, h) {
  if (data.length < 2) return;

  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  for (let i = 0; i < data.length; i++) {
    const x = (i / (data.length - 1)) * w;
    const y = getY(data[i], i);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function drawFilledLine(ctx, data, getY, color, w, h) {
  if (data.length < 2) return;

  ctx.beginPath();
  for (let i = 0; i < data.length; i++) {
    const x = (i / (data.length - 1)) * w;
    const y = getY(data[i], i);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();

  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, color.replace(')', ', 0.2)').replace(/[a-f0-9]{6}|[a-f0-9]{3}\)/i, '0.2)'));
  gradient.addColorStop(1, 'transparent');
  ctx.fillStyle = gradient;
  ctx.fill();
}

function findClosestPoint(data, canvasX, w) {
  if (data.length === 0) return null;
  const idx = Math.round((canvasX / w) * (data.length - 1));
  return {
    index: Math.max(0, Math.min(data.length - 1, idx)),
    point: data[Math.max(0, Math.min(data.length - 1, idx))],
  };
}

/* ── CPU Chart ──────────────────────────────────────────────────────────── */

function drawCpuChart() {
  const canvas = _state.container?.querySelector('#chart-cpu');
  if (!canvas) return;
  const setup = setupCanvas(canvas);
  if (!setup) return;
  const { ctx, w, h } = setup;
  ctx.clearRect(0, 0, w, h);

  const data = _state.cpuHistory;
  if (data.length < 2) return;

  const pad = { top: 8, right: 8, bottom: 16, left: 8 };
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;

  ctx.translate(pad.left, pad.top);
  drawGrid(ctx, cw, ch, 4);

  // Find max value across all cores
  let maxVal = 100;
  for (const d of data) {
    if (d.overall > maxVal) maxVal = d.overall;
    if (d.cores) {
      for (const c of d.cores) {
        if (c > maxVal) maxVal = c;
      }
    }
  }
  maxVal = Math.ceil(maxVal / 10) * 10 || 100;

  drawAxisLabels(ctx, cw, ch, 0, maxVal);

  // Draw per-core lines
  if (data[0]?.cores && data[0].cores.length > 1) {
    const coreCount = data[0].cores.length;
    for (let coreIdx = 0; coreIdx < coreCount; coreIdx++) {
      const coreData = data.map((d) => d.cores[coreIdx] ?? 0);
      const color = COLORS.cpuCore[coreIdx % COLORS.cpuCore.length];
      drawLine(ctx, coreData, (v) => ch - (v / maxVal) * ch, color, cw, ch);
    }
  }

  // Draw overall CPU line (thicker, on top)
  drawLine(ctx, data, (d) => ch - (d.overall / maxVal) * ch, COLORS.cpu, cw, ch);

  // Legend
  const legendY = 0;
  const legendX = cw - 100;
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.font = '9px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('Overall', legendX, legendY + 8);
  ctx.fillStyle = COLORS.cpu;
  ctx.fillRect(legendX - 14, legendY + 2, 10, 2);
}

/* ── Memory Chart ───────────────────────────────────────────────────────── */

function drawMemoryChart() {
  const canvas = _state.container?.querySelector('#chart-memory');
  if (!canvas) return;
  const setup = setupCanvas(canvas);
  if (!setup) return;
  const { ctx, w, h } = setup;
  ctx.clearRect(0, 0, w, h);

  const data = _state.memoryHistory;
  if (data.length < 2) return;

  const pad = { top: 8, right: 8, bottom: 16, left: 8 };
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;

  ctx.translate(pad.left, pad.top);
  drawGrid(ctx, cw, ch, 4);

  const maxTotal = _state.memoryTotal || 16;
  drawAxisLabels(ctx, cw, ch, 0, maxTotal);

  // Stacked area: used + cached + free
  const layers = [
    { key: 'free',  color: COLORS.memFree },
    { key: 'cached', color: COLORS.memCache },
    { key: 'used',  color: COLORS.memUsed },
  ];

  // Draw top-down: used on top
  const stackKeys = ['used', 'cached', 'free'];
  for (const layerKey of stackKeys) {
    const layer = layers.find((l) => l.key === layerKey);
    if (!layer) continue;

    ctx.beginPath();
    const points = [];
    for (let i = 0; i < data.length; i++) {
      const x = (i / (data.length - 1)) * cw;
      let y = ch;
      // Sum all values above this layer
      let stacked = 0;
      for (const sk of stackKeys) {
        stacked += data[i][sk] || 0;
        if (sk === layerKey) break;
      }
      y = ch - (stacked / maxTotal) * ch;
      points.push({ x, y });
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    // Close the shape down
    ctx.lineTo(cw, ch);
    ctx.lineTo(0, ch);
    ctx.closePath();
    ctx.fillStyle = layer.color + '40';
    ctx.fill();

    // Draw top line
    ctx.beginPath();
    ctx.strokeStyle = layer.color;
    ctx.lineWidth = 1;
    for (let i = 0; i < points.length; i++) {
      if (i === 0) ctx.moveTo(points[i].x, points[i].y);
      else ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.stroke();
  }

  // Legend
  let lx = cw - 100;
  for (const layer of layers) {
    ctx.fillStyle = layer.color;
    ctx.fillRect(lx - 14, 0, 10, 2);
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(layer.key.charAt(0).toUpperCase() + layer.key.slice(1), lx, 8);
    lx += 40;
  }
}

/* ── Network Chart ──────────────────────────────────────────────────────── */

function drawNetworkChart() {
  const canvas = _state.container?.querySelector('#chart-network');
  if (!canvas) return;
  const setup = setupCanvas(canvas);
  if (!setup) return;
  const { ctx, w, h } = setup;
  ctx.clearRect(0, 0, w, h);

  const data = _state.networkHistory;
  if (data.length < 2) return;

  const pad = { top: 8, right: 8, bottom: 16, left: 8 };
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;

  ctx.translate(pad.left, pad.top);
  drawGrid(ctx, cw, ch, 4);

  // Auto-scale
  let maxVal = 1;
  for (const d of data) {
    if (d.down > maxVal) maxVal = d.down;
    if (d.up > maxVal) maxVal = d.up;
  }
  maxVal = Math.ceil(maxVal * 1.1);

  drawAxisLabels(ctx, cw, ch, 0, maxVal);

  // Draw down (download) — filled area
  drawFilledLine(ctx, data, (d) => ch - ((d.down || 0) / maxVal) * ch, COLORS.netDown, cw, ch);
  drawLine(ctx, data, (d) => ch - ((d.down || 0) / maxVal) * ch, COLORS.netDown, cw, ch);

  // Draw up (upload) — filled area
  drawFilledLine(ctx, data, (d) => ch - ((d.up || 0) / maxVal) * ch, COLORS.netUp, cw, ch);
  drawLine(ctx, data, (d) => ch - ((d.up || 0) / maxVal) * ch, COLORS.netUp, cw, ch);

  // Labels on right
  ctx.fillStyle = COLORS.netDown;
  ctx.font = '9px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillRect(cw - 64 - 14, 0, 10, 2);
  ctx.fillText('Down', cw - 64, 8);

  ctx.fillStyle = COLORS.netUp;
  ctx.fillRect(cw - 64 - 14, 14, 10, 2);
  ctx.fillText('Up', cw - 64, 22);
}

/* ── Combined Chart ─────────────────────────────────────────────────────── */

function drawCombinedChart() {
  const canvas = _state.container?.querySelector('#chart-combined');
  if (!canvas) return;
  const setup = setupCanvas(canvas);
  if (!setup) return;
  const { ctx, w, h } = setup;
  ctx.clearRect(0, 0, w, h);

  // Normalize all metrics to 0-100% scale
  const cpuData = _state.cpuHistory;
  const memData = _state.memoryHistory;
  const netData = _state.networkHistory;
  if (cpuData.length < 2 && memData.length < 2) return;

  const pad = { top: 8, right: 8, bottom: 16, left: 8 };
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;

  ctx.translate(pad.left, pad.top);
  drawGrid(ctx, cw, ch, 4);
  drawAxisLabels(ctx, cw, ch, 0, 100);

  // CPU line
  if (cpuData.length >= 2) {
    drawLine(ctx, cpuData, (d) => ch - (Math.min(d.overall, 100) / 100) * ch, COLORS.cpu, cw, ch);
  }

  // Memory %
  if (memData.length >= 2) {
    const memPctData = memData.map((d) => ({
      pct: _state.memoryTotal > 0 ? ((d.used) / _state.memoryTotal) * 100 : 0,
    }));
    drawLine(ctx, memPctData, (d) => ch - (Math.min(d.pct, 100) / 100) * ch, COLORS.memUsed, cw, ch);
  }

  // Network % (normalized to max observed)
  if (netData.length >= 2) {
    let maxNet = 1;
    for (const d of netData) { if (d.down > maxNet) maxNet = d.down; }
    const netPctData = netData.map((d) => ({
      pct: maxNet > 0 ? ((d.down || 0) / maxNet) * 50 : 0,
    }));
    drawLine(ctx, netPctData, (d) => ch - (Math.min(d.pct, 100) / 100) * ch, COLORS.netDown, cw, ch);
  }

  // Legend
  const legend = [
    { color: COLORS.cpu,     label: 'CPU' },
    { color: COLORS.memUsed, label: 'Memory' },
    { color: COLORS.netDown, label: 'Network' },
  ];
  let lx = cw - 120;
  for (const item of legend) {
    ctx.fillStyle = item.color;
    ctx.fillRect(lx - 14, 0, 10, 2);
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(item.label, lx, 8);
    lx += 50;
  }
}

/* ── Canvas Hover / Tooltip ─────────────────────────────────────────────── */

function bindCanvasEvents(container) {
  const charts = ['chart-cpu', 'chart-memory', 'chart-network', 'chart-combined'];
  for (const id of charts) {
    const canvas = container.querySelector(`#${id}`);
    const tooltip = container.querySelector(`#${id}-tooltip`);
    if (!canvas || !tooltip) continue;

    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      showChartTooltip(id, x, y, canvas, tooltip);
    });

    canvas.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
    });
  }
}

function showChartTooltip(chartId, mouseX, mouseY, canvas, tooltip) {
  const pad = 8;
  const w = canvas.width / (window.devicePixelRatio || 1) - pad * 2;
  const dataX = mouseX - pad;

  let history;
  let valueFn;
  let label;

  switch (chartId) {
    case 'chart-cpu':
      history = _state.cpuHistory;
      valueFn = (d) => `CPU: ${d?.overall?.toFixed(1) ?? '—'}%`;
      label = 'CPU';
      break;
    case 'chart-memory':
      history = _state.memoryHistory;
      valueFn = (d) => d ? `Used: ${d.used?.toFixed(1)}G | Cache: ${d.cached?.toFixed(1)}G | Free: ${d.free?.toFixed(1)}G` : '—';
      label = 'Memory';
      break;
    case 'chart-network':
      history = _state.networkHistory;
      valueFn = (d) => d ? `Down: ${formatSpeed(d.down)} | Up: ${formatSpeed(d.up)}` : '—';
      label = 'Network';
      break;
    case 'chart-combined':
      history = _state.cpuHistory;
      valueFn = (d) => `CPU: ${d?.overall?.toFixed(1) ?? '—'}%`;
      label = 'Combined';
      break;
    default:
      return;
  }

  if (!history || history.length < 2) {
    tooltip.style.display = 'none';
    return;
  }

  const closest = findClosestPoint(history, dataX, w);
  if (!closest) {
    tooltip.style.display = 'none';
    return;
  }

  const timeStr = closest.point.time
    ? formatTimestamp(new Date(closest.point.time))
    : '';

  tooltip.style.display = 'block';
  tooltip.style.left = Math.min(mouseX + 12, canvas.offsetWidth - 180) + 'px';
  tooltip.style.top = Math.max(mouseY - 30, 4) + 'px';
  tooltip.style.background = 'var(--glass-bg-strong)';
  tooltip.style.backdropFilter = 'blur(8px)';
  tooltip.style.border = '1px solid var(--glass-border-strong)';
  tooltip.style.borderRadius = 'var(--radius-md)';
  tooltip.style.padding = '6px 10px';
  tooltip.style.fontSize = '11px';
  tooltip.style.color = 'var(--text-primary)';
  tooltip.style.zIndex = '100';
  tooltip.style.boxShadow = 'var(--shadow-md)';
  tooltip.style.whiteSpace = 'nowrap';
  tooltip.innerHTML = `
    <div style="font-weight: var(--font-weight-semibold);">${esc(label)}</div>
    <div style="color: var(--text-muted); font-size: 10px;">${timeStr}</div>
    <div style="margin-top: 2px;">${valueFn(closest.point)}</div>
  `;
}

/* ── Polling ────────────────────────────────────────────────────────────── */

function startPolling() {
  stopPolling();
  if (_state.paused || _state.refreshInterval === 0) return;
  _state.pollTimer = setInterval(doPoll, _state.refreshInterval);
}

function stopPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
}

function restartPolling() {
  startPolling();
}

async function doPoll() {
  if (_state.destroyed || _state.paused) return;
  if (_state.visibilityHidden) return; // Skip when tab hidden

  await loadMetrics();
  // Load processes less frequently (every ~3 polls)
  if (_state.processes.length === 0 || Math.random() < 0.3) {
    loadProcesses();
  }
}

/* ── Visibility Handling ────────────────────────────────────────────────── */

function initVisibilityHandling() {
  document.addEventListener('visibilitychange', () => {
    _state.visibilityHidden = document.hidden;
    if (!document.hidden && !_state.destroyed) {
      // Tab became visible again — refresh immediately
      doPoll();
    }
  });
}

/* ── WebSocket Support ──────────────────────────────────────────────────── */

function initWebSocket() {
  const fiona = window.fiona;
  if (!fiona?.api?.on) return;

  _state.wsUnsubscribe = fiona.api.on('system:metrics', (params) => {
    if (_state.destroyed) return;
    if (params && typeof params === 'object') {
      updateMetrics(params);
    }
  });
}

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;

  renderSkeletons(container);

  initVisibilityHandling();
  initWebSocket();

  // Initial data load
  loadMetrics().then(() => {
    if (!_state.destroyed) {
      loadProcesses();
      startPolling();
    }
  });
}

export function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && _state.container && _state.container.querySelector('#perf-metric-cards')) {
    mountPageComponents(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;
  stopPolling();

  if (_state.wsUnsubscribe) {
    _state.wsUnsubscribe();
    _state.wsUnsubscribe = null;
  }

  if (_state.animFrame) {
    cancelAnimationFrame(_state.animFrame);
    _state.animFrame = null;
  }

  _state.container = null;
  _state.cpuHistory = [];
  _state.memoryHistory = [];
  _state.networkHistory = [];
  _state.processes = [];
  _state.cpuPerCore = [];
  _state.mounts = [];
  _state.killTarget = null;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="perf-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#perf-root') || container;
      render(root);
    },
    destroy,
  };
}
