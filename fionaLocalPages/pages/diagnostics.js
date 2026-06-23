/* ==========================================================================
   diagnostics.js — System Health & Diagnostics Dashboard
   ==========================================================================
   Runs health checks on all Fiona subsystems and displays results in a
   card grid.  Supports "Run All" with sequential progress, individual
   re-check, JSON export of the report, and log bundle download.
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
  skeletonButton,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const DIAGNOSTICS_KEY = 'fiona_last_diagnostics';

/** Check definitions — each knows its own endpoint and how to parse. */
const CHECKS = [
  {
    id: 'api-server',
    label: 'API Server',
    icon: 'activity',
    description: 'Ping the Fiona REST API health endpoint.',
    run: async (api) => {
      const t0 = performance.now();
      const res = await api.get('/api/v1/health');
      const ms = Math.round(performance.now() - t0);
      const data = res?.data || res || {};
      return {
        status: data.status === 'ok' || res?.status === 200 ? 'ok' : 'error',
        responseTime: ms,
        details: data,
        summary: `${ms}ms response`,
      };
    },
  },
  {
    id: 'websocket',
    label: 'WebSocket',
    icon: 'globe',
    description: 'Verify WebSocket connectivity and measure latency.',
    run: async (_api) => {
      const fiona = window.fiona;
      if (!fiona?.api?.wsLatency && !fiona?.socket) {
        // Fallback: measure via ephemeral connection
        const url = (fiona?.api?.baseUrl || '').replace(/^http/, 'ws') + '/ws';
        const t0 = performance.now();
        return new Promise((resolve) => {
          try {
            const ws = new WebSocket(url);
            ws.onopen = () => {
              const ms = Math.round(performance.now() - t0);
              ws.close();
              resolve({ status: 'ok', responseTime: ms, summary: `${ms}ms latency` });
            };
            ws.onerror = () => {
              resolve({ status: 'error', responseTime: null, summary: 'Connection refused', details: 'WebSocket endpoint unreachable' });
            };
            setTimeout(() => {
              ws.close();
              resolve({ status: 'warning', responseTime: null, summary: 'Timed out', details: 'WebSocket did not open within 5s' });
            }, 5000);
          } catch (e) {
            resolve({ status: 'error', responseTime: null, summary: e.message, details: e });
          }
        });
      }
      const t0 = performance.now();
      const latency = fiona.api.wsLatency ? await fiona.api.wsLatency() : 0;
      const ms = Math.round(performance.now() - t0);
      return { status: 'ok', responseTime: ms, summary: `${ms}ms latency` };
    },
  },
  {
    id: 'ollama-agent',
    label: 'Ollama Agent',
    icon: 'bot',
    description: 'Check the Ollama agent status and active model.',
    run: async (api) => {
      const t0 = performance.now();
      let res;
      try {
        res = await api.get('/api/v1/agent/status');
      } catch {
        // Try alternate path
        res = await api.get('/api/v1/agents/status');
      }
      const ms = Math.round(performance.now() - t0);
      const data = res?.data || res || {};
      const ok = data.status === 'ok' || data.status === 'running' || data.running === true;
      return {
        status: ok ? 'ok' : 'warning',
        responseTime: ms,
        details: data,
        summary: data.model
          ? `Model: ${data.model}`
          : data.default_model
            ? `Model: ${data.default_model}`
            : ok ? 'Running' : 'Not available',
      };
    },
  },
  {
    id: 'camcoms',
    label: 'CamComs',
    icon: 'eye',
    description: 'Check camera/communications subsystem status.',
    run: async (api) => {
      const t0 = performance.now();
      let res;
      try {
        res = await api.get('/api/v1/camcoms/status');
      } catch {
        // May not exist — treat gracefully
        return { status: 'warning', responseTime: null, summary: 'Endpoint not available', details: 'CamComs may not be configured.' };
      }
      const ms = Math.round(performance.now() - t0);
      const data = res?.data || res || {};
      const ok = data.status === 'ok' || data.connected === true;
      return {
        status: ok ? 'ok' : 'error',
        responseTime: ms,
        details: data,
        summary: data.fingerprint
          ? `Fingerprint: ${data.fingerprint}`
          : data.device
            ? `Device: ${data.device}`
            : ok ? 'Connected' : 'Disconnected',
      };
    },
  },
  {
    id: 'system-resources',
    label: 'System Resources',
    icon: 'info',
    description: 'CPU, memory, and disk usage thresholds.',
    run: async (api) => {
      const t0 = performance.now();
      const res = await api.get('/api/v1/system/status');
      const ms = Math.round(performance.now() - t0);
      const data = res?.data || res || {};
      const cpu = data.cpu?.percent ?? 0;
      const mem = data.memory?.percent_used ?? 0;
      const disk = data.disk?.percent_used ?? 0;
      // Determine overall status from worst metric
      const issues = [];
      if (cpu > 90) issues.push(`CPU at ${cpu.toFixed(0)}%`);
      if (mem > 90) issues.push(`Memory at ${mem.toFixed(0)}%`);
      if (disk > 90) issues.push(`Disk at ${disk.toFixed(0)}%`);
      const status = issues.length > 0 ? 'error' : (cpu > 70 || mem > 70) ? 'warning' : 'ok';
      return {
        status,
        responseTime: ms,
        details: { cpu: `${cpu.toFixed(1)}%`, memory: `${mem.toFixed(1)}%`, disk: `${disk.toFixed(1)}%` },
        summary: issues.length > 0 ? issues.join('; ') : `CPU ${cpu.toFixed(0)}% · Mem ${mem.toFixed(0)}% · Disk ${disk.toFixed(0)}%`,
      };
    },
  },
  {
    id: 'file-system',
    label: 'File System',
    icon: 'folder',
    description: 'Verify project root accessibility and config directories.',
    run: async (api) => {
      const t0 = performance.now();
      const res = await api.get('/api/v1/files/info');
      const ms = Math.round(performance.now() - t0);
      const data = res?.data || res || {};
      const errors = [];
      if (data.error) errors.push(data.error);
      const ok = !data.error && data.exists !== false;
      return {
        status: ok ? 'ok' : 'error',
        responseTime: ms,
        details: data,
        summary: ok
          ? `${data.file_count ?? '?'} files, ${data.dir_count ?? '?'} dirs`
          : errors.join('; ') || 'Inaccessible',
      };
    },
  },
  {
    id: 'network',
    label: 'Network',
    icon: 'globe',
    description: 'Check connectivity to essential endpoints.',
    run: async (api) => {
      const t0 = performance.now();
      const endpoints = [
        '/api/v1/health',
        '/api/v1/system/status',
      ];
      const results = [];
      let allOk = true;
      for (const ep of endpoints) {
        try {
          await api.get(ep);
          results.push(`${ep}: OK`);
        } catch {
          results.push(`${ep}: FAIL`);
          allOk = false;
        }
      }
      const ms = Math.round(performance.now() - t0);
      return {
        status: allOk ? 'ok' : 'warning',
        responseTime: ms,
        details: results,
        summary: allOk ? 'All endpoints reachable' : `${results.filter(r => r.includes('FAIL')).length} endpoint(s) failed`,
      };
    },
  },
  {
    id: 'browser-automation',
    label: 'Browser Automation',
    icon: 'globe',
    description: 'Check if the browser automation engine is available.',
    run: async (api) => {
      const t0 = performance.now();
      let res;
      try {
        res = await api.get('/api/v1/browser/status');
      } catch {
        return { status: 'warning', responseTime: null, summary: 'Endpoint not available', details: 'Browser automation may not be configured.' };
      }
      const ms = Math.round(performance.now() - t0);
      const data = res?.data || res || {};
      const ok = data.status === 'ok' || data.running === true || data.available === true;
      return {
        status: ok ? 'ok' : 'error',
        responseTime: ms,
        details: data,
        summary: ok
          ? `${data.browser || data.engine || 'Engine'} available`
          : data.error || 'Not available',
      };
    },
  },
];

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  results: {},        // checkId -> { status, responseTime, details, summary, running? }
  lastRun: null,      // Date
  running: false,
  currentCheckId: null,
  runningAll: false,
  expandedId: null,
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

function formatDate(date) {
  const d = date.toISOString().slice(0, 10);
  return `${d} ${formatTimestamp(date)}`;
}

function statusIcon(status) {
  switch (status) {
    case 'ok': return ICONS['check-circle'];
    case 'warning': return ICONS.warning;
    case 'error': return ICONS.error;
    default: return ICONS.help;
  }
}

function statusColor(status) {
  switch (status) {
    case 'ok': return 'var(--success)';
    case 'warning': return 'var(--warning)';
    case 'error': return 'var(--danger)';
    default: return 'var(--text-muted)';
  }
}

/* ── Render ─────────────────────────────────────────────────────────────── */

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

  const checkCount = CHECKS.length;
  const doneCount = Object.keys(_state.results).length;
  const okCount = Object.values(_state.results).filter((r) => r.status === 'ok').length;
  const warnCount = Object.values(_state.results).filter((r) => r.status === 'warning').length;
  const errCount = Object.values(_state.results).filter((r) => r.status === 'error').length;

  container.innerHTML = html`
    <!-- Page Header -->
    <div style="margin-bottom: var(--space-5);">
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3);">
        <div>
          <h1 style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); margin: 0;">
            Diagnostics
          </h1>
          <p style="font-size: var(--font-size-sm); color: var(--text-muted); margin: 2px 0 0 0;">
            System health check and diagnostics dashboard
          </p>
        </div>
        <div style="display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap;">
          ${_state.lastRun ? html`
            <span style="font-size: var(--font-size-xs); color: var(--text-muted);" id="diag-last-run">
              Last run: ${formatDate(_state.lastRun)}
            </span>
          ` : ''}
          <button class="c-btn c-btn--primary c-btn--sm" id="diag-run-all"
                  ?disabled="${_state.running}"
                  style="${_state.running ? 'opacity: 0.6; cursor: not-allowed;' : ''}">
            <span class="c-btn__icon">
              ${_state.running ? ICONS.refresh : ICONS.play}
            </span>
            ${_state.running ? 'Running…' : 'Run All Checks'}
          </button>
          <button class="c-btn c-btn--sm c-btn--ghost" id="diag-export"
                  ?disabled="${doneCount === 0}"
                  title="Export diagnostics report (JSON)">
            <span class="c-btn__icon">${ICONS.download}</span>
            Export
          </button>
          <button class="c-btn c-btn--sm c-btn--ghost" id="diag-logs-bundle"
                  title="Download log bundle">
            <span class="c-btn__icon">${ICONS.fileText}</span>
            Log Bundle
          </button>
        </div>
      </div>
      <!-- Summary bar -->
      ${doneCount > 0 ? html`
        <div style="display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-3); padding: var(--space-2) var(--space-3); background: var(--surface); border-radius: var(--radius-md); font-size: var(--font-size-xs);">
          <span>${doneCount}/${checkCount} checks completed</span>
          <span style="display: flex; align-items: center; gap: 4px; color: var(--success);">
            <span style="width: 8px; height: 8px; border-radius: 50%; background: var(--success);"></span>
            ${okCount} passed
          </span>
          ${warnCount > 0 ? html`
            <span style="display: flex; align-items: center; gap: 4px; color: var(--warning);">
              <span style="width: 8px; height: 8px; border-radius: 50%; background: var(--warning);"></span>
              ${warnCount} warnings
            </span>
          ` : ''}
          ${errCount > 0 ? html`
            <span style="display: flex; align-items: center; gap: 4px; color: var(--danger);">
              <span style="width: 8px; height: 8px; border-radius: 50%; background: var(--danger);"></span>
              ${errCount} failures
            </span>
          ` : ''}
        </div>
      ` : ''}
      ${_state.running ? html`
        <div style="margin-top: var(--space-3);">
          <div class="c-progress" style="height: 4px;">
            <div class="c-progress__bar" style="width: ${(doneCount / checkCount) * 100}%; background: var(--accent); transition: width 0.3s;"></div>
          </div>
          <span style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 4px; display: block;">
            ${_state.currentCheckId
              ? `Running: ${CHECKS.find(c => c.id === _state.currentCheckId)?.label || _state.currentCheckId}…`
              : 'Starting…'}
          </span>
        </div>
      ` : ''}
    </div>

    <!-- Check Cards Grid -->
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: var(--space-4);">
      ${html.raw(CHECKS.map((check) => renderCheckCard(check)).join(''))}
    </div>
  `;

  mountHandlers(container);
}

function renderCheckCard(check) {
  const result = _state.results[check.id];
  const isRunning = _state.currentCheckId === check.id;
  const isExpanded = _state.expandedId === check.id;
  const hasResult = !!result;
  const status = result?.status || 'pending';

  return html`
    <div class="c-card" style="position: relative; ${isRunning ? 'border-color: var(--accent);' : ''}
         ${hasResult ? '' : 'opacity: 0.75;'}">
      <div class="c-card__body" style="padding: var(--space-4);">
        <!-- Card Header -->
        <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: var(--space-2);">
          <div style="display: flex; align-items: center; gap: var(--space-3);">
            <div style="width: 28px; height: 28px; border-radius: var(--radius-md);
                        background: ${status !== 'pending' ? statusColor(status) + '20' : 'var(--bg-tertiary)'};
                        display: flex; align-items: center; justify-content: center;
                        color: ${status !== 'pending' ? statusColor(status) : 'var(--text-muted)'};
                        flex-shrink: 0;">
              ${isRunning ? ICONS.refresh : (hasResult ? statusIcon(status) : ICONS.help)}
            </div>
            <div>
              <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary);">
                ${esc(check.label)}
              </div>
              <div style="font-size: var(--font-size-xxs); color: var(--text-muted);">
                ${esc(check.description)}
              </div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0;">
            ${result?.responseTime != null ? html`
              <span style="font-size: var(--font-size-xxs); color: var(--text-muted); font-variant-numeric: tabular-nums; white-space: nowrap;">
                ${result.responseTime}ms
              </span>
            ` : ''}
            <button class="c-btn c-btn--sm c-btn--ghost" data-check-id="${check.id}" data-action="run-check"
                    ?disabled="${_state.running}"
                    title="Run this check" style="padding: 2px 6px;">
              <span class="c-btn__icon" style="width: 14px; height: 14px;">${ICONS.refresh}</span>
            </button>
          </div>
        </div>

        <!-- Status / Summary -->
        ${hasResult ? html`
          <div style="display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3);
                      background: ${statusColor(status)}10; border-radius: var(--radius-sm);
                      font-size: var(--font-size-xs); color: var(--text-secondary);">
            <span style="width: 6px; height: 6px; border-radius: 50%; background: ${statusColor(status)}; flex-shrink: 0;"></span>
            <span style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              ${status === 'ok' ? '✓ ' : status === 'warning' ? '⚠ ' : '✗ '}
              ${esc(result.summary || (status === 'ok' ? 'Passed' : 'Failed'))}
            </span>
          </div>
        ` : isRunning ? html`
          <div style="padding: var(--space-2); text-align: center; font-size: var(--font-size-xs); color: var(--text-muted);">
            <span class="c-spinner c-spinner--sm"></span> Running…
          </div>
        ` : html`
          <div style="padding: var(--space-2); text-align: center; font-size: var(--font-size-xs); color: var(--text-muted);">
            Not yet checked
          </div>
        `}

        <!-- Expand / Details toggle -->
        ${hasResult && result.details ? html`
          <div style="margin-top: var(--space-2);">
            <button class="c-btn c-btn--sm c-btn--ghost" data-check-id="${check.id}" data-action="toggle-details"
                    style="font-size: var(--font-size-xxs); padding: 2px 6px; width: 100%; justify-content: center;">
              ${isExpanded ? 'Hide details' : 'Show details'}
            </button>
            ${isExpanded ? html`
              <pre style="margin-top: var(--space-2); padding: var(--space-2); background: var(--bg-tertiary);
                          border-radius: var(--radius-sm); font-size: var(--font-size-xxs);
                          overflow-x: auto; max-height: 200px; font-family: var(--font-mono);
                          color: var(--text-secondary); white-space: pre-wrap; word-break: break-all;">
${esc(JSON.stringify(result.details, null, 2))}
              </pre>
            ` : ''}
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      ${skeletonHeading({ width: '200px' })}
      ${skeletonText({ width: '260px' })}
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: var(--space-4); margin-top: var(--space-5);">
        ${Array.from({ length: 8 }, () => skeletonCard({ height: '140px' }))}
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
        ${esc(_state.errorMessage || 'Unable to reach the Fiona backend for diagnostics.')}
      </div>
      <button class="c-btn c-btn--primary" id="diag-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#diag-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // Run All
  container.querySelector('#diag-run-all')?.addEventListener('click', () => {
    if (!_state.running) runAllChecks();
  });

  // Export
  container.querySelector('#diag-export')?.addEventListener('click', exportReport);

  // Log bundle
  container.querySelector('#diag-logs-bundle')?.addEventListener('click', downloadLogBundle);

  // Individual check run
  container.querySelectorAll('[data-action="run-check"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.checkId;
      if (id && !_state.running) runSingleCheck(id);
    });
  });

  // Toggle details
  container.querySelectorAll('[data-action="toggle-details"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.checkId;
      _state.expandedId = _state.expandedId === id ? null : id;
      if (_state.container) renderPage(_state.container);
    });
  });
}

/* ── Check Execution ────────────────────────────────────────────────────── */

async function runSingleCheck(checkId) {
  const api = getApi();
  if (!api || _state.destroyed) return;

  const check = CHECKS.find((c) => c.id === checkId);
  if (!check) return;

  _state.currentCheckId = checkId;
  _state.results[checkId] = { ...(_state.results[checkId] || {}), running: true };
  if (_state.container) renderPage(_state.container);

  try {
    const result = await check.run(api);
    _state.results[checkId] = { ...result, running: false };
    _state.lastRun = new Date();
    persistLastRun();
  } catch (err) {
    _state.results[checkId] = {
      status: 'error',
      responseTime: null,
      summary: err.message || 'Check threw an exception',
      details: { error: err.message, stack: err.stack },
      running: false,
    };
  }

  _state.currentCheckId = null;
  if (!_state.destroyed && _state.container) {
    renderPage(_state.container);
  }
}

async function runAllChecks() {
  const api = getApi();
  if (!api || _state.destroyed || _state.running) return;

  _state.running = true;
  _state.runningAll = true;
  _state.results = {};

  // Render immediately to show progress
  if (_state.container) renderPage(_state.container);

  for (const check of CHECKS) {
    if (_state.destroyed) break;
    await runSingleCheck(check.id);
  }

  _state.running = false;
  _state.runningAll = false;
  _state.currentCheckId = null;
  _state.lastRun = new Date();
  persistLastRun();

  if (!_state.destroyed && _state.container) {
    renderPage(_state.container);
  }
}

/* ── Export / Download ──────────────────────────────────────────────────── */

function exportReport() {
  const report = {
    generatedAt: new Date().toISOString(),
    lastRun: _state.lastRun?.toISOString() || null,
    summary: {
      total: CHECKS.length,
      completed: Object.keys(_state.results).length,
      passed: Object.values(_state.results).filter((r) => r.status === 'ok').length,
      warnings: Object.values(_state.results).filter((r) => r.status === 'warning').length,
      errors: Object.values(_state.results).filter((r) => r.status === 'error').length,
    },
    checks: CHECKS.map((check) => ({
      id: check.id,
      label: check.label,
      result: _state.results[check.id] || { status: 'pending', summary: 'Not checked' },
    })),
  };

  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `fiona-diagnostics-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadLogBundle() {
  const api = getApi();
  if (!api) {
    showToast('error', 'API client not available.');
    return;
  }

  try {
    const res = await api.get('/api/v1/logs/bundle');
    const data = res?.data || res;
    if (data?.url) {
      // Backend returned a URL
      const a = document.createElement('a');
      a.href = data.url;
      a.download = data.filename || `fiona-logs-${new Date().toISOString().slice(0, 10)}.tar.gz`;
      a.click();
    } else if (data?.content || data?.logs) {
      // Fallback: create a blob from returned content
      const content = data.content || data.logs;
      const blob = new Blob([typeof content === 'string' ? content : JSON.stringify(content, null, 2)],
        { type: 'application/gzip' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fiona-logs-${new Date().toISOString().slice(0, 10)}.tar.gz`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      showToast('info', 'No log bundle available from the backend.');
    }
  } catch (err) {
    // If the endpoint doesn't exist, offer a client-side log bundle as fallback
    try {
      const clientLogs = [];
      // Collect recent console logs if available
      if (window._fionaLogs && Array.isArray(window._fionaLogs)) {
        clientLogs.push(...window._fionaLogs.slice(-200));
      }
      const fallbackContent = JSON.stringify({
        generatedAt: new Date().toISOString(),
        source: 'client-side fallback',
        logs: clientLogs,
      }, null, 2);
      const blob = new Blob([fallbackContent], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fiona-logs-fallback-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('info', 'Backend bundle unavailable; downloaded client-side snapshot.');
    } catch (e2) {
      showToast('error', `Failed to download logs: ${err.message}`);
    }
  }
}

/* ── Persistence ────────────────────────────────────────────────────────── */

function persistLastRun() {
  try {
    const data = {
      lastRun: _state.lastRun?.toISOString() || null,
      results: _state.results,
    };
    localStorage.setItem(DIAGNOSTICS_KEY, JSON.stringify(data));
  } catch { /* ignore */ }
}

function loadPersistedData() {
  try {
    const raw = localStorage.getItem(DIAGNOSTICS_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      if (data.lastRun) _state.lastRun = new Date(data.lastRun);
      if (data.results) _state.results = data.results;
    }
  } catch { /* ignore */ }
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

  _state.loading = false;

  // Restore previous results from localStorage for a snappy initial view
  loadPersistedData();

  if (_state.container) renderPage(_state.container);

  // Auto-run checks that have never been run
  if (Object.keys(_state.results).length === 0) {
    runAllChecks();
  }
}

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;
  _state.expandedId = null;

  renderSkeletons(container);
  loadData();
}

export function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && _state.container) {
    renderPage(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;
  _state.running = false;
  _state.runningAll = false;
  _state.currentCheckId = null;
  _state.container = null;
  _state.results = {};
  _state.expandedId = null;
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="diag-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#diag-root') || container;
      render(root);
    },
    destroy,
  };
}
