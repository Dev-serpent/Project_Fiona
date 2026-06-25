/* ==========================================================================
   dashboard.js — System Dashboard Page
   ==========================================================================
   Overview page showing Fiona's system status at a glance.  Displays
   metric cards, active agents, recent activity timeline, and system
   info.  Polls the backend every 5 seconds for live updates.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { MetricsCard } from '../js/components/MetricsCard.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 5000;
const SPARKLINE_POINTS = 20;
const MAX_ACTIVITY_ITEMS = 10;

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  pollTimer: null,
  loading: true,
  error: false,
  errorMessage: '',
  systemStatus: null,
  activityHistory: [],
  cpuHistory: [],
  memoryHistory: [],
  diskHistory: [],
  uptimeHistory: [],
  cpuCard: null,
  memoryCard: null,
  diskCard: null,
  uptimeCard: null,
  lastUpdated: null,
  destroyed: false,
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

function getStore() {
  return window.fiona?.store;
}

function formatTimestamp(date) {
  const h = date.getHours().toString().padStart(2, '0');
  const m = date.getMinutes().toString().padStart(2, '0');
  const s = date.getSeconds().toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
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

function actionLabel(type) {
  const map = {
    macro: 'Macro',
    command: 'Command',
    chat: 'Chat',
    terminal: 'Terminal',
    file: 'File',
    browser: 'Browser',
    system: 'System',
    agent: 'Agent',
    recall: 'Recall',
  };
  return map[type] || type || 'Action';
}

function actionIconKey(type) {
  const map = {
    macro: 'play',
    command: 'bolt',
    chat: 'message',
    terminal: 'terminal',
    file: 'file',
    browser: 'globe',
    system: 'gear',
    agent: 'bot',
    recall: 'search',
  };
  return map[type] || 'activity';
}

function parseUptimeHours(str) {
  if (!str) return 0;
  let total = 0;
  const h = str.match(/(\d+)\s*h/);
  const m = str.match(/(\d+)\s*m/);
  if (h) total += parseInt(h[1], 10);
  if (m) total += parseInt(m[1], 10) / 60;
  return total;
}

/* ── HTML Renderers ─────────────────────────────────────────────────────── */

async function renderContent(container) {
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

  const now = _state.lastUpdated || new Date();
  const connStatus = getStore()?.get('system.status') || 'disconnected';
  const connColor = connStatus === 'connected'
    ? 'var(--success)'
    : connStatus === 'connecting'
      ? 'var(--warning)'
      : 'var(--danger)';

  const data = {
    connStatus: connStatus.charAt(0).toUpperCase() + connStatus.slice(1),
    connColor: connColor,
    timestamp: formatTimestamp(now),
    refreshIcon: ICONS.refresh.html,
    messageIcon: ICONS.message.html,
    playIcon: ICONS.play.html,
    terminalIcon: ICONS.terminal.html,
    botIcon: ICONS.bot.html,
  };

  container.innerHTML = await loadTemplate('dashboard', data);

  mountComponents(container);
  if (_state.systemStatus) {
    updateMetricCards(_state.systemStatus);
    updateSystemInfo(_state.systemStatus);
    updateAgentsList(_state.systemStatus);
  }
  if (_state.activityHistory.length > 0) {
    updateActivityList();
  }
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-6);">
        ${skeletonHeading({ width: '200px' })}
        ${skeletonText({ width: '140px' })}
      </div>
      <div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-5);">
        ${html.raw(Array.from({ length: 4 }, () => `
          <div class="c-skeleton" style="width: 100px; height: 32px; border-radius: var(--radius-md);"></div>
        `).join(''))}
      </div>
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); margin-bottom: var(--space-5);">
        ${Array.from({ length: 4 }, () => skeletonCard({ height: '130px' }))}
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-5); margin-bottom: var(--space-5);">
        ${skeletonCard({ height: '300px' })}
        ${skeletonCard({ height: '300px' })}
      </div>
      ${skeletonCard({ height: '100px' })}
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
        ${esc(_state.errorMessage || 'Unable to reach the Fiona backend. The server may be offline.')}
      </div>
      <button class="c-btn c-btn--primary" id="dash-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry Connection
      </button>
    </div>
  `;

  container.querySelector('#dash-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountComponents(container) {
  // Refresh button
  container.querySelector('#dash-refresh-btn')?.addEventListener('click', () => loadData());

  // Quick actions
  container.querySelector('[data-action="quick-chat"]')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/chat');
  });
  container.querySelector('[data-action="quick-macro"]')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/macros');
  });
  container.querySelector('[data-action="quick-terminal"]')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/terminal');
  });
  container.querySelector('[data-action="quick-screenshot"]')?.addEventListener('click', async () => {
    try {
      const api = getApi();
      if (api) await api.post('/api/v1/desktop/screenshot');
    } catch (err) {
      console.warn('[dashboard] Screenshot failed:', err);
    }
  });

  mountMetricCards(container);

  if (_state.systemStatus) {
    updateMetricCards(_state.systemStatus);
    updateSystemInfo(_state.systemStatus);
    updateAgentsList(_state.systemStatus);
  }
  if (_state.activityHistory.length > 0) {
    updateActivityList();
  }
}

function mountMetricCards(container) {
  const cpuEl = container.querySelector('#metric-cpu');
  const memEl = container.querySelector('#metric-memory');
  const diskEl = container.querySelector('#metric-disk');
  const uptimeEl = container.querySelector('#metric-uptime');

  if (cpuEl && !_state.cpuCard) {
    _state.cpuCard = new MetricsCard({
      container: cpuEl,
      props: {
        title: 'CPU Usage',
        value: 0,
        unit: '%',
        icon: 'activity',
        color: 'var(--accent)',
        variant: 'default',
        sparklineData: _state.cpuHistory.length > 0 ? [..._state.cpuHistory] : [0],
      },
    });
    _state.cpuCard.attach();
  }

  if (memEl && !_state.memoryCard) {
    _state.memoryCard = new MetricsCard({
      container: memEl,
      props: {
        title: 'Memory',
        value: 0,
        unit: '%',
        icon: 'info',
        color: 'var(--info)',
        variant: 'default',
        sparklineData: _state.memoryHistory.length > 0 ? [..._state.memoryHistory] : [0],
      },
    });
    _state.memoryCard.attach();
  }

  if (diskEl && !_state.diskCard) {
    _state.diskCard = new MetricsCard({
      container: diskEl,
      props: {
        title: 'Disk',
        value: 0,
        unit: '%',
        icon: 'folder',
        color: 'var(--success)',
        variant: 'default',
        sparklineData: _state.diskHistory.length > 0 ? [..._state.diskHistory] : [0],
      },
    });
    _state.diskCard.attach();
  }

  if (uptimeEl && !_state.uptimeCard) {
    _state.uptimeCard = new MetricsCard({
      container: uptimeEl,
      props: {
        title: 'Uptime',
        value: 0,
        unit: 'h',
        icon: 'clock',
        color: 'var(--warning)',
        variant: 'default',
        sparklineData: _state.uptimeHistory.length > 0 ? [..._state.uptimeHistory] : [0],
      },
    });
    _state.uptimeCard.attach();
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
    if (_state.container) await renderContent(_state.container);
    return;
  }

  try {
    const [statusResult, historyResult] = await Promise.all([
      api.get('/api/v1/system/status'),
      api.get('/api/v1/actions/history'),
    ]);

    const status = statusResult?.data || statusResult;
    const history = Array.isArray(historyResult?.data)
      ? historyResult.data
      : Array.isArray(historyResult)
        ? historyResult
        : [];

    _state.systemStatus = status;
    _state.activityHistory = history.slice(0, MAX_ACTIVITY_ITEMS);
    _state.lastUpdated = new Date();
    _state.error = false;
    _state.loading = false;

    appendSparklineData(status);

    if (!_state.destroyed && _state.container) {
      await renderContent(_state.container);
    }
  } catch (err) {
    console.error('[dashboard] Failed to load data:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch data from backend.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      await renderContent(_state.container);
    }
  }
}

function appendSparklineData(status) {
  const cpu = status?.cpu?.percent ?? null;
  const mem = status?.memory?.percent_used ?? null;
  const disk = status?.disk?.percent_used ?? null;
  const uptime = status?.uptime ? parseUptimeHours(status.uptime) : null;

  if (cpu !== null) {
    _state.cpuHistory.push(cpu);
    if (_state.cpuHistory.length > SPARKLINE_POINTS) _state.cpuHistory.shift();
  }
  if (mem !== null) {
    _state.memoryHistory.push(mem);
    if (_state.memoryHistory.length > SPARKLINE_POINTS) _state.memoryHistory.shift();
  }
  if (disk !== null) {
    _state.diskHistory.push(disk);
    if (_state.diskHistory.length > SPARKLINE_POINTS) _state.diskHistory.shift();
  }
  if (uptime !== null) {
    _state.uptimeHistory.push(uptime);
    if (_state.uptimeHistory.length > SPARKLINE_POINTS) _state.uptimeHistory.shift();
  }
}

/* ── Data Update Methods ────────────────────────────────────────────────── */

function updateMetricCards(status) {
  const cpu = status?.cpu?.percent ?? 0;
  const mem = status?.memory?.percent_used ?? 0;
  const disk = status?.disk?.percent_used ?? 0;
  const uptime = status?.uptime || '0h 0m';

  const cpuDelta = _state.cpuHistory.length >= 2
    ? (_state.cpuHistory[_state.cpuHistory.length - 1] - _state.cpuHistory[_state.cpuHistory.length - 2]).toFixed(1)
    : '0';
  const memDelta = _state.memoryHistory.length >= 2
    ? (_state.memoryHistory[_state.memoryHistory.length - 1] - _state.memoryHistory[_state.memoryHistory.length - 2]).toFixed(1)
    : '0';

  if (_state.cpuCard) {
    // Update non-animated props only; updateValue() handles the animated value
    _state.cpuCard.update({
      sparklineData: [..._state.cpuHistory],
      delta: `${cpuDelta >= 0 ? '+' : ''}${cpuDelta}%`,
      trend: cpuDelta > 0 ? 'up' : cpuDelta < 0 ? 'down' : 'neutral',
    });
    _state.cpuCard.updateValue(cpu);
  }

  if (_state.memoryCard) {
    _state.memoryCard.update({
      sparklineData: [..._state.memoryHistory],
      delta: `${memDelta >= 0 ? '+' : ''}${memDelta}%`,
      trend: memDelta > 0 ? 'up' : memDelta < 0 ? 'down' : 'neutral',
    });
    _state.memoryCard.updateValue(mem);
  }

  if (_state.diskCard) {
    _state.diskCard.update({
      sparklineData: [..._state.diskHistory],
    });
    _state.diskCard.updateValue(disk);
  }

  if (_state.uptimeCard) {
    const uptimeHours = parseUptimeHours(uptime);
    _state.uptimeCard.update({
      sparklineData: [..._state.uptimeHistory],
      unit: 'h',
    });
    _state.uptimeCard.updateValue(uptimeHours);
  }
}

function updateSystemInfo(status) {
  const qs = (id) => _state.container?.querySelector(id);
  const setText = (id, text) => { const el = qs(id); if (el) el.textContent = text || '—'; };

  setText('#sys-os', status?.platform ? `${status.platform} ${status.release || ''}` : '—');
  setText('#sys-hostname', status?.hostname || '—');
  setText('#sys-python', status?.python_version ? status.python_version.split(' ')[0] : '—');
}

function updateAgentsList(status) {
  const agentsEl = _state.container?.querySelector('#agents-list');
  const badgeEl = _state.container?.querySelector('#agent-count-badge');
  if (!agentsEl) return;

  const agents = getStore()?.get('agents.list') || status?.agents || [];
  const count = agents.length;
  if (badgeEl) badgeEl.textContent = String(count);

  if (count === 0) {
    agentsEl.innerHTML = `
      <div style="text-align: center; padding: var(--space-6); color: var(--text-muted); font-size: var(--font-size-sm);">
        No agents connected.
      </div>
    `;
    return;
  }

  agentsEl.innerHTML = agents.map((agent) => `
    <div style="display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-2); border-radius: var(--radius-md); cursor: pointer; transition: background var(--transition-fast);"
         data-agent-id="${esc(agent.id || '')}">
      <div style="position: relative; flex-shrink: 0;">
        <div class="c-avatar c-avatar--sm c-avatar--accent">${esc((agent.name || 'A')[0])}</div>
        <span style="position: absolute; bottom: -1px; right: -1px; width: 8px; height: 8px;
                     border-radius: 50%; background: ${agent.active !== false ? 'var(--success)' : 'var(--text-muted)'};
                     border: 2px solid var(--surface);"></span>
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(agent.name || 'Unknown')}
        </div>
        <div style="font-size: var(--font-size-xs); color: var(--text-muted);">
          ${agent.model ? esc(agent.model) : agent.active !== false ? 'Active' : 'Idle'}
        </div>
      </div>
      <span style="font-size: 8px; color: ${agent.active !== false ? 'var(--success)' : 'var(--text-muted)'};">●</span>
    </div>
  `).join('');
}

function updateActivityList() {
  const listEl = _state.container?.querySelector('#activity-list');
  if (!listEl) return;

  const items = _state.activityHistory;
  if (!items || items.length === 0) {
    listEl.innerHTML = `
      <div style="text-align: center; padding: var(--space-6); color: var(--text-muted); font-size: var(--font-size-sm);">
        No recent activity.
      </div>
    `;
    return;
  }

  listEl.innerHTML = items.map((act) => {
    const type = act.type || act.action_type || 'action';
    const label = actionLabel(type);
    const iconKey = actionIconKey(type);
    const ts = act.timestamp || act.created_at || Date.now();
    const iconSvg = ICONS[iconKey] || ICONS.activity;

    return `
      <div style="display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-2) var(--space-2); border-radius: var(--radius-md); transition: background var(--transition-fast);">
        <div style="width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: var(--text-muted);">
          ${iconSvg}
        </div>
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: var(--space-2);">
            <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${esc(act.name || act.action_name || label)}
            </span>
            <span class="c-badge c-badge--default" style="font-size: 9px; padding: 0 6px; flex-shrink: 0;">${esc(label)}</span>
          </div>
          ${act.description ? `<div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 1px;">${esc(act.description)}</div>` : ''}
          <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 2px;">${timeAgo(ts)}</div>
        </div>
      </div>
    `;
  }).join('');
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

  const [statusResult, historyResult] = await Promise.allSettled([
    api.get('/api/v1/system/status'),
    api.get('/api/v1/actions/history'),
  ]);

  if (_state.destroyed) return;

  let changed = false;

  if (statusResult.status === 'fulfilled') {
    const status = statusResult.value?.data || statusResult.value;
    _state.systemStatus = status;
    _state.lastUpdated = new Date();
    appendSparklineData(status);
    if (_state.container) {
      updateMetricCards(status);
      updateSystemInfo(status);
      updateAgentsList(status);
    }
    changed = true;
  }

  if (historyResult.status === 'fulfilled') {
    const history = Array.isArray(historyResult.value?.data)
      ? historyResult.value.data
      : Array.isArray(historyResult.value)
        ? historyResult.value
        : [];
    _state.activityHistory = history.slice(0, MAX_ACTIVITY_ITEMS);
    if (_state.container) updateActivityList();
    changed = true;
  }

  if (changed) {
    const tsEl = _state.container?.querySelector('#dash-timestamp');
    if (tsEl && _state.lastUpdated) {
      tsEl.textContent = `Updated ${formatTimestamp(_state.lastUpdated)}`;
    }
  }

  if (statusResult.status === 'fulfilled') {
    _state.error = false;

    // Update status indicator previously set during full render
    const connStatus = getStore()?.get('system.status') || 'disconnected';
    const connLabel = _state.container?.querySelector('#dash-conn-label');
    const connDot = _state.container?.querySelector('#dash-status-dot');
    if (connLabel) {
      connLabel.textContent = connStatus.charAt(0).toUpperCase() + connStatus.slice(1);
    }
    if (connDot) {
      connDot.style.background = connStatus === 'connected'
        ? 'var(--success)'
        : connStatus === 'connecting'
          ? 'var(--warning)'
          : 'var(--danger)';
    }
  }
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Render — returns a mount point for the SPA router.
 * @returns {string} HTML placeholder
 */
export function render() {
  return '<div id="dash-root"></div>';
}

/**
 * Mount the dashboard page — initializes state, loads template, fetches data.
 * Called by the router after render().
 * @param {Element} container
 */
export async function mount(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;

  renderSkeletons(container);

  await loadData();

  if (!_state.destroyed) startPolling();
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();

  if (_state.cpuCard) { _state.cpuCard.destroy(); _state.cpuCard = null; }
  if (_state.memoryCard) { _state.memoryCard.destroy(); _state.memoryCard = null; }
  if (_state.diskCard) { _state.diskCard.destroy(); _state.diskCard = null; }
  if (_state.uptimeCard) { _state.uptimeCard.destroy(); _state.uptimeCard = null; }

  _state.container = null;
  _state.systemStatus = null;
  _state.activityHistory = [];
  _state.cpuHistory = [];
  _state.memoryHistory = [];
  _state.diskHistory = [];
  _state.uptimeHistory = [];
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
    render,
    async mount(container) {
      const root = container.querySelector('#dash-root') || container;
      _state.destroyed = false;
      _state.loading = true;
      _state.error = false;
      _state.errorMessage = '';
      _state.container = root;

      renderSkeletons(root);

      await loadData();

      if (!_state.destroyed) startPolling();
    },
    destroy,
  };
}
