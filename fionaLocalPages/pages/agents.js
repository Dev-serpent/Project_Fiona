/* ==========================================================================
   agents.js — Active Agents Page
   ==========================================================================
   Shows all running agent instances with their status, progress, and
   controls.  Polls REST on mount and subscribes to WebSocket for live
   status updates.

   Exports: { render(container?), mount(container), destroy() }
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

const POLL_INTERVAL = 5000;
const WS_TOPIC_AGENTS = 'agents:status';
const MAX_VISIBLE_AGENTS = 50;

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  agents: [],
  availableModels: [],
  modelStatusHtml: '',
  pollTimer: null,
  wsUnsub: null,
  _boundListeners: [],
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api;
}

function getStore() {
  return window.fiona?.store;
}

function esc(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

function timeAgo(timestamp) {
  if (!timestamp) return '';
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

function formatDuration(ms) {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

function statusColor(status) {
  const map = {
    idle: 'var(--success)',
    working: 'var(--info)',
    error: 'var(--danger)',
    offline: 'var(--text-muted)',
    paused: 'var(--warning)',
  };
  return map[status] || 'var(--text-muted)';
}

function statusLabel(status) {
  const map = {
    idle: 'Idle',
    working: 'Working',
    error: 'Error',
    offline: 'Offline',
    paused: 'Paused',
  };
  return map[status] || status || 'Unknown';
}

/* ── HTML Renderers ─────────────────────────────────────────────────────── */

function renderModelStatus() {
  const models = _state.availableModels || [];
  const qwenAvailable = models.some(m => m.includes('qwen3:8b'));
  const otherModels = models.filter(m => !m.includes('qwen3:8b')).slice(0, 3);

  let html = `<div class="model-status" style="display:flex;align-items:center;gap:var(--space-3);font-size:var(--font-size-xs);color:var(--text-muted);flex-wrap:wrap;">`;

  // qwen3:8b indicator
  if (qwenAvailable) {
    html += `<span style="display:flex;align-items:center;gap:4px;">
      <span style="width:6px;height:6px;border-radius:50%;background:var(--success);"></span>
      <strong>qwen3:8b</strong> <span style="color:var(--text-muted)">online</span>
    </span>`;
  } else {
    html += `<span style="display:flex;align-items:center;gap:4px;">
      <span style="width:6px;height:6px;border-radius:50%;background:var(--danger);"></span>
      <strong>qwen3:8b</strong> <span style="color:var(--text-muted)">offline</span>
    </span>`;
  }

  // Other models
  if (otherModels.length > 0) {
    html += `<span style="color:var(--border-subtle)">|</span>`;
    html += otherModels.map(m =>
      `<span style="color:var(--text-muted);font-size:10px;">${esc(m)}</span>`
    ).join('');
  }

  if (models.length > 3) {
    html += `<span style="color:var(--text-muted);font-size:10px;">+${models.length - 3} more</span>`;
  }

  html += `</div>`;
  return html;
}

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

  const count = _state.agents.length;
  const hasAgents = count > 0;
  const agentCardsHtml = hasAgents ? _state.agents.map((a) => renderAgentCard(a)).join('') : '';

  const data = {
    agentCount: count,
    hasAgents,
    agentCardsHtml,
    plusIcon: ICONS.plus.html,
    botIcon: ICONS.bot.html,
    modelStatusHtml: _state.modelStatusHtml || '',
  };

  container.innerHTML = await loadTemplate('agents', data);

  mountComponents(container);
}

function renderAgentCard(agent) {
  const status = agent.status || 'offline';
  const color = statusColor(status);
  const label = statusLabel(status);
  const progress = agent.progress != null ? Math.min(Math.max(agent.progress, 0), 100) : null;
  const tokensUsed = agent.tokens_used || agent.tokensUsed || 0;
  const elapsed = agent.elapsed_ms || agent.elapsedMs || 0;
  const model = agent.model || '—';

  return html`
    <div class="c-card c-card--interactive agent-card" data-agent-id="${esc(agent.id || '')}" style="position: relative;">
      <div class="c-card__header" style="padding-bottom: var(--space-3);">
        <div style="display: flex; align-items: center; gap: var(--space-3); min-width: 0;">
          <div class="c-avatar c-avatar--sm c-avatar--accent" style="flex-shrink: 0;">
            ${esc((agent.name || 'A')[0])}
          </div>
          <div style="min-width: 0;">
            <div class="c-card__title" style="font-size: var(--font-size-sm); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${esc(agent.name || agent.id || 'Unknown')}
            </div>
            <div style="font-size: var(--font-size-xxs); color: var(--text-muted);">
              ${esc(model)} · ${esc(agent.id ? agent.id.slice(0, 8) : '')}
            </div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0;">
          <span style="display: flex; align-items: center; gap: 4px; font-size: var(--font-size-xxs); color: ${color};">
            <span style="width: 8px; height: 8px; border-radius: 50%; background: ${color};
                 ${status === 'working' ? 'animation: pulse 1.5s ease-in-out infinite;' : ''}"></span>
            ${esc(label)}
          </span>
        </div>
      </div>

      <div class="c-card__body" style="padding-top: 0; padding-bottom: var(--space-3);">
        <!-- Current Action -->
        <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-bottom: var(--space-2);
                    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
          ${agent.current_action || agent.currentAction || agent.task || 'No active task'}
        </div>

        <!-- Progress Bar -->
        ${progress !== null ? html`
          <div style="margin-bottom: var(--space-2);">
            <div style="display: flex; justify-content: space-between; font-size: var(--font-size-xxs); color: var(--text-muted); margin-bottom: 2px;">
              <span>Progress</span>
              <span>${progress}%</span>
            </div>
            <div class="c-progress c-progress--sm">
              <div class="c-progress__bar" style="width: ${progress}%; ${progress >= 100 ? 'background: var(--success);' : ''}"></div>
            </div>
          </div>
        ` : ''}

        <!-- Metrics Row -->
        <div style="display: flex; gap: var(--space-4); font-size: var(--font-size-xxs); color: var(--text-muted);">
          <span style="display: flex; align-items: center; gap: 3px;">
            ${ICONS.activity}
            ${tokensUsed > 0 ? `${tokensUsed} tokens` : '0 tokens'}
          </span>
          <span style="display: flex; align-items: center; gap: 3px;">
            ${ICONS.clock}
            ${formatDuration(elapsed)}
          </span>
        </div>
      </div>

      <!-- Controls Footer -->
      <div class="c-card__footer c-card__footer--actions" style="border-top: 1px solid var(--border-subtle);">
        <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost agent-pause-btn" title="${status === 'paused' ? 'Resume' : 'Pause'}" data-agent-id="${esc(agent.id || '')}">
          ${status === 'paused' ? ICONS.play : ICONS.pause}
        </button>
        <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost agent-stop-btn" title="Stop" data-agent-id="${esc(agent.id || '')}" style="color: var(--danger);">
          ${ICONS.close}
        </button>
        <button class="c-btn c-btn--icon c-btn--sm c-btn--ghost agent-restart-btn" title="Restart" data-agent-id="${esc(agent.id || '')}">
          ${ICONS.refresh}
        </button>
      </div>
    </div>
  `;
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-5);">
        ${skeletonHeading({ width: '200px' })}
        ${skeletonText({ width: '140px' })}
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: var(--space-4);">
        ${Array.from({ length: 4 }, () => skeletonCard({ height: '180px' }))}
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
        ${esc(_state.errorMessage || 'Unable to fetch agents from backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="agents-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  const retryBtn = container.querySelector('#agents-retry-btn');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      _state.error = false;
      _state.loading = true;
      renderSkeletons(container);
      loadData();
    });
  }
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountComponents(container) {
  // Keep track of listeners so destroy() can remove them
  const listeners = [];

  // New Agent button
  const btnNew = container.querySelector('#btn-new-agent');
  if (btnNew) {
    const handler = () => handleNewAgent();
    btnNew.addEventListener('click', handler);
    listeners.push(() => btnNew.removeEventListener('click', handler));
  }

  // Click card → navigate to agent status detail
  const cards = container.querySelectorAll('.agent-card');
  cards.forEach((card) => {
    const handler = () => {
      const agentId = card.dataset.agentId;
      if (agentId) navigateToAgent(agentId);
    };
    card.addEventListener('click', handler);
    listeners.push(() => card.removeEventListener('click', handler));
  });

  // Pause/Resume buttons
  container.querySelectorAll('.agent-pause-btn').forEach((btn) => {
    const handler = (e) => {
      e.stopPropagation();
      const agentId = btn.dataset.agentId;
      if (agentId) togglePauseAgent(agentId);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  // Stop buttons
  container.querySelectorAll('.agent-stop-btn').forEach((btn) => {
    const handler = (e) => {
      e.stopPropagation();
      const agentId = btn.dataset.agentId;
      if (agentId) stopAgent(agentId);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  // Restart buttons
  container.querySelectorAll('.agent-restart-btn').forEach((btn) => {
    const handler = (e) => {
      e.stopPropagation();
      const agentId = btn.dataset.agentId;
      if (agentId) restartAgent(agentId);
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  _state._boundListeners = listeners;
}

/* ── Actions ────────────────────────────────────────────────────────────── */

function navigateToAgent(agentId) {
  const router = window.fiona?.router;
  if (router) {
    router.navigate(`/agents/${encodeURIComponent(agentId)}`);
  }
}

async function handleNewAgent() {
  const { modal } = await import('../js/components/Modal.js');
  const result = await modal.showModal({
    title: 'New Agent',
    content: html`
      <div class="c-form-group" style="margin-bottom: var(--space-4);">
        <label class="c-form-group__label">Agent Name</label>
        <input type="text" class="c-input" id="new-agent-name" placeholder="e.g. Code Assistant" />
      </div>
      <div class="c-form-group" style="margin-bottom: var(--space-4);">
        <label class="c-form-group__label">Model</label>
        <input type="text" class="c-input" id="new-agent-model" placeholder="e.g. llama3.2" value="llama3.2" />
      </div>
      <div class="c-form-group">
        <label class="c-form-group__label">System Prompt</label>
        <textarea class="c-textarea" id="new-agent-prompt" placeholder="Optional system prompt…" rows="3"></textarea>
      </div>
    `,
    size: 'md',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Create Agent', value: 'create', variant: 'primary' },
    ],
  });

  if (result !== 'create') return;

  const nameEl = document.getElementById('new-agent-name');
  const modelEl = document.getElementById('new-agent-model');
  const promptEl = document.getElementById('new-agent-prompt');

  const name = nameEl?.value?.trim() || 'New Agent';
  const model = modelEl?.value?.trim() || 'llama3.2';
  const systemPrompt = promptEl?.value?.trim() || '';

  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  try {
    const result = await api.post('/api/v1/agents', { name, model, system_prompt: systemPrompt });
    toast.showToast('success', 'Agent Created', `Agent "${name}" has been started.`);
    loadData();
  } catch (err) {
    toast.showToast('error', 'Failed', err.message || 'Could not create agent.');
  }
}

async function togglePauseAgent(agentId) {
  const api = getApi();
  if (!api) return;
  const agent = _state.agents.find((a) => a.id === agentId);
  if (!agent) return;
  const isPaused = agent.status === 'paused';
  try {
    if (isPaused) {
      await api.post(`/api/v1/agents/${encodeURIComponent(agentId)}/resume`);
      toast.showToast('success', 'Resumed', 'Agent has been resumed.');
    } else {
      await api.post(`/api/v1/agents/${encodeURIComponent(agentId)}/pause`);
      toast.showToast('info', 'Paused', 'Agent has been paused.');
    }
    loadData();
  } catch (err) {
    toast.showToast('error', 'Failed', err.message || 'Could not toggle agent state.');
  }
}

async function stopAgent(agentId) {
  const api = getApi();
  if (!api) return;
  try {
    await api.post(`/api/v1/agents/${encodeURIComponent(agentId)}/stop`);
    toast.showToast('info', 'Stopped', 'Agent has been stopped.');
    loadData();
  } catch (err) {
    toast.showToast('error', 'Failed', err.message || 'Could not stop agent.');
  }
}

async function restartAgent(agentId) {
  const api = getApi();
  if (!api) return;
  try {
    await api.post(`/api/v1/agents/${encodeURIComponent(agentId)}/restart`);
    toast.showToast('success', 'Restarted', 'Agent is restarting…');
    loadData();
  } catch (err) {
    toast.showToast('error', 'Failed', err.message || 'Could not restart agent.');
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
    const result = await api.get('/api/v1/agents');
    const agents = Array.isArray(result?.data) ? result.data : Array.isArray(result) ? result : [];

    // Fetch available models from meta
    _state.availableModels = [];
    if (result?.meta?.available_models) {
      _state.availableModels = result.meta.available_models;
    }
    _state.modelStatusHtml = renderModelStatus();

    // Update store if available
    const store = getStore();
    if (store) {
      store.set('agents.list', agents);
    }

    _state.agents = agents.slice(0, MAX_VISIBLE_AGENTS);
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  } catch (err) {
    console.error('[agents] Failed to load agents:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch agents.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  }
}

async function handleWebSocketUpdate(data) {
  if (_state.destroyed || !data) return;

  // data could be a single agent update or an array
  const updates = Array.isArray(data) ? data : [data];

  for (const update of updates) {
    if (!update.id) continue;
    const idx = _state.agents.findIndex((a) => a.id === update.id);
    if (idx >= 0) {
      // Merge update into existing agent
      _state.agents[idx] = { ..._state.agents[idx], ...update };
    } else {
      // New agent appeared
      _state.agents.unshift(update);
      if (_state.agents.length > MAX_VISIBLE_AGENTS) {
        _state.agents = _state.agents.slice(0, MAX_VISIBLE_AGENTS);
      }
    }
  }

  if (_state.container && !_state.loading) {
    await renderPage(_state.container);
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
    // Also fetch available models during poll
    try {
      const modelsRes = await api.get('/api/v1/agent/models');
      if (modelsRes?.data?.models) {
        _state.availableModels = modelsRes.data.models;
        _state.modelStatusHtml = renderModelStatus();
      }
    } catch { /* best effort */ }

    const result = await api.get('/api/v1/agents');
    const agents = Array.isArray(result?.data) ? result.data : Array.isArray(result) ? result : [];
    _state.agents = agents.slice(0, MAX_VISIBLE_AGENTS);
    if (_state.container && !_state.loading) {
      await renderPage(_state.container);
    }
  } catch {
    // Silent fail during poll
  }
}

/* ── WebSocket Subscription ─────────────────────────────────────────────── */

function subscribeWebSocket() {
  const api = getApi();
  if (!api) return;

  try {
    const ws = api.connect?.();
    if (ws && typeof ws.on === 'function') {
      const unsub = ws.on('message', (msg) => {
        if (msg && (msg.event === WS_TOPIC_AGENTS || msg.topic === WS_TOPIC_AGENTS)) {
          handleWebSocketUpdate(msg.data || msg.params);
        }
      });
      _state.wsUnsub = unsub;
    }
  } catch (err) {
    // WebSocket subscription is best-effort
    console.warn('[agents] WS subscription failed:', err);
  }
}

function unsubscribeWebSocket() {
  if (_state.wsUnsub) {
    _state.wsUnsub();
    _state.wsUnsub = null;
  }
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Full render — called from outside the router or from mount().
 * @param {Element} container
 */
export function render() {
  return '<div id="agents-root"></div>';
}

export async function mount(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;

  renderSkeletons(container);
  subscribeWebSocket();
  await loadData();
  if (!_state.destroyed) startPolling();
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();
  unsubscribeWebSocket();

  // Remove bound listeners
  for (const fn of _state._boundListeners) {
    try { fn(); } catch (e) { /* ignore */ }
  }
  _state._boundListeners = [];

  _state.container = null;
  _state.agents = [];
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
      const root = container.querySelector('#agents-root') || container;
      _state.destroyed = false;
      _state.loading = true;
      _state.error = false;
      _state.errorMessage = '';
      _state.container = root;

      renderSkeletons(root);
      subscribeWebSocket();
      await loadData();
      if (!_state.destroyed) startPolling();
    },
    destroy,
  };
}
