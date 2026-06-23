/* ==========================================================================
   agent-status.js — Agent Status Detail Page
   ==========================================================================
   Detailed view of a single agent's operation with tabbed content:
   Thought Stream (real-time), Conversation, Tool Calls, Performance.
   Subscribes to WebSocket for streaming thought updates.

   Exports: { render(routeInfo), mount(container), destroy() }
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';
import { toast } from '../js/components/Toast.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 5000;
const WS_EVENT_THOUGHT = 'agent:thought';
const WS_EVENT_STATUS = 'agent:status';
const MAX_THOUGHTS = 500;
const MAX_CONVERSATION = 200;

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  agentId: null,
  agent: null,
  activeTab: 'thoughts',
  thoughts: [],
  conversation: [],
  toolCalls: [],
  performance: null,
  pollTimer: null,
  wsUnsub: null,
  autoScroll: true,
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

function formatTime(date) {
  if (!date) return '';
  const d = date instanceof Date ? date : new Date(date);
  const h = d.getHours().toString().padStart(2, '0');
  const m = d.getMinutes().toString().padStart(2, '0');
  const s = d.getSeconds().toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
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

  const agent = _state.agent;
  if (!agent) {
    renderEmpty(container);
    return;
  }

  const status = agent.status || 'offline';
  const color = statusColor(status);
  const label = statusLabel(status);
  const uptime = agent.uptime || agent.uptime_seconds || agent.elapsed_ms || 0;
  const model = agent.model || '—';

  container.innerHTML = html`
    <!-- Back Button -->
    <div style="margin-bottom: var(--space-3);">
      <button class="c-btn c-btn--sm c-btn--ghost" id="agent-back-btn" style="padding-left: 4px;">
        <span class="c-btn__icon">${ICONS.chevronLeft}</span>
        Back to Agents
      </button>
    </div>

    <!-- Agent Header -->
    <div class="c-card" style="margin-bottom: var(--space-5);">
      <div class="c-card__body" style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3);">
        <div style="display: flex; align-items: center; gap: var(--space-4);">
          <div class="c-avatar c-avatar--lg c-avatar--accent">
            ${esc((agent.name || 'A')[0])}
          </div>
          <div>
            <div style="display: flex; align-items: center; gap: var(--space-3);">
              <h2 style="font-size: var(--font-size-lg); font-weight: var(--font-weight-bold); color: var(--text-primary); margin: 0;">
                ${esc(agent.name || agent.id || 'Unknown Agent')}
              </h2>
              <span style="display: flex; align-items: center; gap: 4px; font-size: var(--font-size-xs); color: ${color};">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: ${color};
                     ${status === 'working' ? 'animation: pulse 1.5s ease-in-out infinite;' : ''}"></span>
                ${esc(label)}
              </span>
            </div>
            <div style="display: flex; gap: var(--space-4); margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-muted);">
              <span>Model: ${esc(model)}</span>
              <span>ID: ${esc(agent.id ? agent.id.slice(0, 12) : '—')}</span>
              <span>Uptime: ${typeof uptime === 'number' ? formatDuration(uptime) : esc(uptime || '—')}</span>
            </div>
          </div>
        </div>

        <!-- Controls -->
        <div style="display: flex; gap: var(--space-2);">
          <button class="c-btn c-btn--sm c-btn--ghost agent-ctrl-btn" data-action="toggle-pause" title="${status === 'paused' ? 'Resume' : 'Pause'}">
            <span class="c-btn__icon">${status === 'paused' ? ICONS.play : ICONS.pause}</span>
            ${status === 'paused' ? 'Resume' : 'Pause'}
          </button>
          <button class="c-btn c-btn--sm c-btn--ghost agent-ctrl-btn" data-action="stop" title="Stop" style="color: var(--danger);">
            <span class="c-btn__icon">${ICONS.close}</span>
            Stop
          </button>
          <button class="c-btn c-btn--sm c-btn--ghost agent-ctrl-btn" data-action="restart" title="Restart">
            <span class="c-btn__icon">${ICONS.refresh}</span>
            Restart
          </button>
        </div>
      </div>
    </div>

    <!-- Tab Bar -->
    <div class="c-tabs" style="margin-bottom: var(--space-4);">
      <button class="c-tab ${_state.activeTab === 'thoughts' ? 'c-tab--active' : ''}" data-tab="thoughts">
        <span class="c-tab__icon">${ICONS.activity}</span>
        Thought Stream
        <span class="c-tab__count">${_state.thoughts.length}</span>
      </button>
      <button class="c-tab ${_state.activeTab === 'conversation' ? 'c-tab--active' : ''}" data-tab="conversation">
        <span class="c-tab__icon">${ICONS.message}</span>
        Conversation
        <span class="c-tab__count">${_state.conversation.length}</span>
      </button>
      <button class="c-tab ${_state.activeTab === 'tools' ? 'c-tab--active' : ''}" data-tab="tools">
        <span class="c-tab__icon">${ICONS.bolt}</span>
        Tool Calls
        <span class="c-tab__count">${_state.toolCalls.length}</span>
      </button>
      <button class="c-tab ${_state.activeTab === 'performance' ? 'c-tab--active' : ''}" data-tab="performance">
        <span class="c-tab__icon">${ICONS.clock}</span>
        Performance
      </button>
    </div>

    <!-- Tab Content -->
    <div id="agent-tab-content">
      ${_state.activeTab === 'thoughts' ? renderThoughtStream() : ''}
      ${_state.activeTab === 'conversation' ? renderConversation() : ''}
      ${_state.activeTab === 'tools' ? renderToolCalls() : ''}
      ${_state.activeTab === 'performance' ? renderPerformance() : ''}
    </div>
  `;

  mountComponents(container);
}

/* ── Tab Renderers ──────────────────────────────────────────────────────── */

function renderThoughtStream() {
  const thoughts = _state.thoughts;

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">Real-time Thought Stream</span>
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <label style="display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xxs); color: var(--text-muted); cursor: pointer;">
            <input type="checkbox" id="thought-auto-scroll" checked style="accent-color: var(--accent);">
            Auto-scroll
          </label>
          <button class="c-btn c-btn--sm c-btn--ghost" id="thought-clear-btn" title="Clear thoughts">
            <span class="c-btn__icon">${ICONS.trash}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body" style="padding: 0;">
        ${thoughts.length === 0 ? html`
          <div style="text-align: center; padding: var(--space-8); color: var(--text-muted); font-size: var(--font-size-sm);">
            Waiting for agent thoughts…
          </div>
        ` : html`
          <div id="thought-stream" class="c-scroll-area" style="max-height: 60vh; overflow-y: auto; scrollbar-width: thin;">
            ${html.raw(thoughts.map((t) => html`
              <div class="thought-entry" style="padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);">
                <div style="display: flex; align-items: flex-start; gap: var(--space-2);">
                  <span style="font-size: var(--font-size-xxs); color: var(--text-muted); white-space: nowrap; flex-shrink: 0; font-family: var(--font-mono);">
                    ${formatTime(t.timestamp)}
                  </span>
                  <div style="flex: 1; min-width: 0;">
                    <div style="font-size: var(--font-size-sm); color: var(--text-primary); line-height: var(--line-height-relaxed);">
                      ${esc(t.content || '')}
                    </div>
                    ${t.tool ? html`
                      <div style="margin-top: var(--space-1); display: flex; align-items: center; gap: var(--space-2);">
                        <span class="c-badge c-badge--info" style="font-size: 9px;">${esc(t.tool)}</span>
                        ${t.result ? html`
                          <span style="font-size: var(--font-size-xxs); color: var(--text-muted); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            ${esc(t.result)}
                          </span>
                        ` : ''}
                      </div>
                    ` : ''}
                  </div>
                </div>
              </div>
            `).join(''))}
          </div>
        `}
      </div>
    </div>
  `;
}

function renderConversation() {
  const messages = _state.conversation;

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">Conversation</span>
        <span class="c-badge c-badge--accent">${messages.length} messages</span>
      </div>
      <div class="c-card__body" style="padding: 0;">
        ${messages.length === 0 ? html`
          <div style="text-align: center; padding: var(--space-8); color: var(--text-muted); font-size: var(--font-size-sm);">
            No conversation history yet.
          </div>
        ` : html`
          <div style="max-height: 60vh; overflow-y: auto; scrollbar-width: thin;">
            ${html.raw(messages.map((msg) => {
              const isUser = msg.role === 'user';
              return html`
                <div style="display: flex; gap: var(--space-3); padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle); ${isUser ? 'background: var(--surface);' : ''}">
                  <div class="c-avatar c-avatar--sm ${isUser ? '' : 'c-avatar--accent'}" style="flex-shrink: 0;">
                    ${isUser ? 'U' : 'F'}
                  </div>
                  <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
                      <span style="font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); color: var(--text-secondary);">
                        ${isUser ? 'User' : esc(msg.sender || 'Fiona')}
                      </span>
                      <span style="font-size: var(--font-size-xxs); color: var(--text-muted);">${formatTime(msg.timestamp)}</span>
                    </div>
                    <div style="font-size: var(--font-size-sm); color: var(--text-primary); line-height: var(--line-height-relaxed);">
                      ${esc(msg.content || '')}
                    </div>
                  </div>
                </div>
              `;
            }).join(''))}
          </div>
        `}
      </div>
    </div>
  `;
}

function renderToolCalls() {
  const calls = _state.toolCalls;

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">Tool Calls</span>
        <span class="c-badge c-badge--accent">${calls.length} calls</span>
      </div>
      <div class="c-card__body" style="padding: 0;">
        ${calls.length === 0 ? html`
          <div style="text-align: center; padding: var(--space-8); color: var(--text-muted); font-size: var(--font-size-sm);">
            No tool calls recorded yet.
          </div>
        ` : html`
          <div style="max-height: 60vh; overflow-y: auto; scrollbar-width: thin;">
            ${html.raw(calls.map((call) => {
              const status = call.status || 'completed';
              const duration = call.duration_ms || call.durationMs;
              return html`
                <div style="padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);">
                  <div style="display: flex; align-items: center; gap: var(--space-3);">
                    <div style="display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: var(--radius-sm); background: var(--accent-muted); flex-shrink: 0;">
                      ${ICONS.bolt}
                    </div>
                    <div style="flex: 1; min-width: 0;">
                      <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary);">
                        ${esc(call.tool || call.name || 'Unknown')}
                      </div>
                      ${call.input || call.args ? html`
                        <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 1px; font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                          ${esc(JSON.stringify(call.input || call.args || {}))}
                        </div>
                      ` : ''}
                      ${call.result ? html`
                        <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: var(--space-1); padding: var(--space-2); background: var(--surface); border-radius: var(--radius-sm); max-height: 80px; overflow-y: auto;">
                          ${esc(typeof call.result === 'string' ? call.result : JSON.stringify(call.result))}
                        </div>
                      ` : ''}
                    </div>
                    <div style="text-align: right; flex-shrink: 0;">
                      <span class="c-badge c-badge--${status === 'completed' ? 'success' : status === 'error' ? 'danger' : 'default'}" style="font-size: 9px;">
                        ${esc(status)}
                      </span>
                      ${duration ? html`
                        <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 2px;">${formatDuration(duration)}</div>
                      ` : ''}
                    </div>
                  </div>
                  <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: var(--space-1);">
                    ${formatTime(call.timestamp)}
                  </div>
                </div>
              `;
            }).join(''))}
          </div>
        `}
      </div>
    </div>
  `;
}

function renderPerformance() {
  const perf = _state.performance || {};
  const tokensUsed = perf.tokens_used || perf.tokensUsed || 0;
  const avgResponseTime = perf.avg_response_ms || perf.avgResponseMs || 0;
  const totalCalls = perf.total_calls || perf.totalCalls || 0;
  const costEstimate = perf.cost_estimate || perf.costEstimate || 0;

  return html`
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-4);">
      <!-- Token Usage -->
      <div class="c-card">
        <div class="c-card__header">
          <span class="c-card__title">Token Usage</span>
        </div>
        <div class="c-card__body">
          <div class="c-metric">
            <span class="c-metric__value">${tokensUsed.toLocaleString()}</span>
            <span class="c-metric__label">Total Tokens</span>
          </div>
          ${perf.tokens_history && perf.tokens_history.length > 0 ? html`
            <div style="margin-top: var(--space-3);">
              <div style="display: flex; gap: 2px; align-items: flex-end; height: 60px;">
                ${html.raw(perf.tokens_history.slice(-30).map((val) => {
                  const max = Math.max(...perf.tokens_history, 1);
                  const h = (val / max) * 60;
                  return html`<div style="flex: 1; height: ${h}px; background: var(--accent); border-radius: 2px; min-height: 2px; opacity: 0.7;"></div>`;
                }).join(''))}
              </div>
            </div>
          ` : ''}
        </div>
      </div>

      <!-- Response Times -->
      <div class="c-card">
        <div class="c-card__header">
          <span class="c-card__title">Response Times</span>
        </div>
        <div class="c-card__body">
          <div class="c-metric">
            <span class="c-metric__value">${formatDuration(avgResponseTime)}</span>
            <span class="c-metric__label">Average Response Time</span>
          </div>
          <div style="margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--text-muted);">
            Total calls: ${totalCalls}
          </div>
        </div>
      </div>

      <!-- Cost Estimate -->
      <div class="c-card">
        <div class="c-card__header">
          <span class="c-card__title">Cost Estimate</span>
        </div>
        <div class="c-card__body">
          <div class="c-metric">
            <span class="c-metric__value">${costEstimate > 0 ? `$${costEstimate.toFixed(4)}` : '—'}</span>
            <span class="c-metric__label">Estimated Cost</span>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      <div style="margin-bottom: var(--space-3);">
        ${skeletonText({ width: '120px' })}
      </div>
      ${skeletonCard({ height: '100px' })}
      <div style="margin: var(--space-4) 0;">
        <div style="display: flex; gap: var(--space-2);">
          ${Array.from({ length: 4 }, () => html`<div class="c-skeleton" style="width: 120px; height: 32px; border-radius: var(--radius-md);"></div>`)}
        </div>
      </div>
      ${skeletonCard({ height: '300px' })}
    </div>
  `;
}

function renderError(container) {
  container.innerHTML = html`
    <div style="margin-bottom: var(--space-3);">
      <button class="c-btn c-btn--sm c-btn--ghost" id="agent-back-btn-error" style="padding-left: 4px;">
        <span class="c-btn__icon">${ICONS.chevronLeft}</span>
        Back to Agents
      </button>
    </div>
    <div class="empty-state" style="margin-top: 5vh;">
      <div class="empty-state__icon" style="color: var(--danger);">
        ${ICONS.error}
      </div>
      <div class="empty-state__title">Agent Not Found</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Could not load agent details.')}
      </div>
      <button class="c-btn c-btn--primary" id="agent-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  const backBtn = container.querySelector('#agent-back-btn-error');
  if (backBtn) backBtn.addEventListener('click', navigateBack);

  const retryBtn = container.querySelector('#agent-retry-btn');
  if (retryBtn) retryBtn.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    renderSkeletons(container);
    loadAgentData(_state.agentId);
  });
}

function renderEmpty(container) {
  container.innerHTML = html`
    <div style="margin-bottom: var(--space-3);">
      <button class="c-btn c-btn--sm c-btn--ghost" id="agent-back-btn-empty">
        <span class="c-btn__icon">${ICONS.chevronLeft}</span>
        Back to Agents
      </button>
    </div>
    <div class="empty-state" style="margin-top: 5vh;">
      <div class="empty-state__icon">${ICONS.bot}</div>
      <div class="empty-state__title">No Agent Selected</div>
      <div class="empty-state__description">Select an agent from the list to view details.</div>
    </div>
  `;

  const backBtn = container.querySelector('#agent-back-btn-empty');
  if (backBtn) backBtn.addEventListener('click', navigateBack);
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountComponents(container) {
  const listeners = [];

  // Back button
  const backBtn = container.querySelector('#agent-back-btn');
  if (backBtn) {
    const handler = () => navigateBack();
    backBtn.addEventListener('click', handler);
    listeners.push(() => backBtn.removeEventListener('click', handler));
  }

  // Tab switching
  container.querySelectorAll('.c-tab[data-tab]').forEach((tab) => {
    const handler = () => {
      _state.activeTab = tab.dataset.tab;
      if (_state.container) renderPage(_state.container);
    };
    tab.addEventListener('click', handler);
    listeners.push(() => tab.removeEventListener('click', handler));
  });

  // Auto-scroll toggle
  const autoScrollEl = container.querySelector('#thought-auto-scroll');
  if (autoScrollEl) {
    const handler = (e) => { _state.autoScroll = e.target.checked; };
    autoScrollEl.addEventListener('change', handler);
    listeners.push(() => autoScrollEl.removeEventListener('change', handler));
  }

  // Clear thoughts
  const clearBtn = container.querySelector('#thought-clear-btn');
  if (clearBtn) {
    const handler = () => {
      _state.thoughts = [];
      if (_state.container) renderPage(_state.container);
    };
    clearBtn.addEventListener('click', handler);
    listeners.push(() => clearBtn.removeEventListener('click', handler));
  }

  // Agent control buttons
  container.querySelectorAll('.agent-ctrl-btn').forEach((btn) => {
    const handler = () => {
      const action = btn.dataset.action;
      if (!_state.agentId) return;
      switch (action) {
        case 'toggle-pause': togglePauseAgent(_state.agentId); break;
        case 'stop': stopAgent(_state.agentId); break;
        case 'restart': restartAgent(_state.agentId); break;
      }
    };
    btn.addEventListener('click', handler);
    listeners.push(() => btn.removeEventListener('click', handler));
  });

  _state._boundListeners = listeners;

  // Auto-scroll thought stream after mount
  if (_state.activeTab === 'thoughts' && _state.autoScroll) {
    requestAnimationFrame(() => {
      const streamEl = container.querySelector('#thought-stream');
      if (streamEl) streamEl.scrollTop = streamEl.scrollHeight;
    });
  }
}

/* ── Navigation ─────────────────────────────────────────────────────────── */

function navigateBack() {
  const router = window.fiona?.router;
  if (router) {
    router.navigate('/agents');
  }
}

/* ── Actions ────────────────────────────────────────────────────────────── */

async function togglePauseAgent(agentId) {
  const api = getApi();
  if (!api) return;
  const isPaused = _state.agent?.status === 'paused';
  try {
    if (isPaused) {
      await api.post(`/api/v1/agents/${encodeURIComponent(agentId)}/resume`);
      toast.showToast('success', 'Resumed', 'Agent has been resumed.');
    } else {
      await api.post(`/api/v1/agents/${encodeURIComponent(agentId)}/pause`);
      toast.showToast('info', 'Paused', 'Agent has been paused.');
    }
    loadAgentData(agentId);
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
    navigateBack();
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
    loadAgentData(agentId);
  } catch (err) {
    toast.showToast('error', 'Failed', err.message || 'Could not restart agent.');
  }
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadAgentData(agentId) {
  if (_state.destroyed || !agentId) return;
  const api = getApi();
  if (!api) {
    _state.error = true;
    _state.errorMessage = 'API client not available.';
    _state.loading = false;
    if (_state.container) renderPage(_state.container);
    return;
  }

  try {
    const result = await api.get(`/api/v1/agents/${encodeURIComponent(agentId)}`);
    const data = result?.data || result;

    _state.agent = data.agent || data;
    _state.thoughts = (data.thoughts || data.thought_stream || []).slice(0, MAX_THOUGHTS);
    _state.conversation = (data.conversation || data.messages || []).slice(0, MAX_CONVERSATION);
    _state.toolCalls = data.tool_calls || data.toolCalls || [];
    _state.performance = data.performance || data.metrics || null;
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
  } catch (err) {
    console.error('[agent-status] Failed to load agent:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch agent data.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
  }
}

/* ── WebSocket Streaming ────────────────────────────────────────────────── */

function subscribeWebSocket() {
  const api = getApi();
  if (!api) return;

  try {
    const ws = api.connect?.();
    if (ws && typeof ws.on === 'function') {
      const unsub = ws.on('message', (msg) => {
        if (_state.destroyed) return;
        if (!msg || !msg.event) return;

        // Thought stream updates
        if (msg.event === WS_EVENT_THOUGHT) {
          const params = msg.data || msg.params || {};
          if (params.agent_id && params.agent_id !== _state.agentId) return;

          const thought = {
            timestamp: params.timestamp || Date.now(),
            content: params.content || params.text || params.thought || '',
            tool: params.tool || null,
            result: params.result || null,
          };

          if (thought.content) {
            _state.thoughts.push(thought);
            if (_state.thoughts.length > MAX_THOUGHTS) {
              _state.thoughts = _state.thoughts.slice(-MAX_THOUGHTS);
            }

            // Update UI if on thoughts tab
            if (_state.container && _state.activeTab === 'thoughts') {
              const streamEl = _state.container.querySelector('#thought-stream');
              if (streamEl) {
                // Append new thought without full re-render
                const entry = document.createElement('div');
                entry.className = 'thought-entry';
                entry.style.cssText = 'padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);';
                entry.innerHTML = html`
                  <div style="display: flex; align-items: flex-start; gap: var(--space-2);">
                    <span style="font-size: var(--font-size-xxs); color: var(--text-muted); white-space: nowrap; flex-shrink: 0; font-family: var(--font-mono);">
                      ${formatTime(thought.timestamp)}
                    </span>
                    <div style="flex: 1; min-width: 0;">
                      <div style="font-size: var(--font-size-sm); color: var(--text-primary); line-height: var(--line-height-relaxed);">
                        ${esc(thought.content)}
                      </div>
                      ${thought.tool ? html`
                        <div style="margin-top: var(--space-1); display: flex; align-items: center; gap: var(--space-2);">
                          <span class="c-badge c-badge--info" style="font-size: 9px;">${esc(thought.tool)}</span>
                          ${thought.result ? html`
                            <span style="font-size: var(--font-size-xxs); color: var(--text-muted); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                              ${esc(thought.result)}
                            </span>
                          ` : ''}
                        </div>
                      ` : ''}
                    </div>
                  </div>
                `;
                streamEl.appendChild(entry);
                if (_state.autoScroll) {
                  streamEl.scrollTop = streamEl.scrollHeight;
                }
              } else {
                // Stream element not mounted yet, do full re-render
                renderPage(_state.container);
              }
            }
          }
          return;
        }

        // Status updates
        if (msg.event === WS_EVENT_STATUS) {
          const params = msg.data || msg.params || {};
          if (params.agent_id && params.agent_id !== _state.agentId) return;
          if (_state.agent) {
            _state.agent = { ..._state.agent, ...params };
            if (_state.container && !_state.loading) {
              renderPage(_state.container);
            }
          }
          return;
        }
      });

      _state.wsUnsub = unsub;
    }
  } catch (err) {
    console.warn('[agent-status] WS subscription failed:', err);
  }
}

function unsubscribeWebSocket() {
  if (_state.wsUnsub) {
    _state.wsUnsub();
    _state.wsUnsub = null;
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
  if (_state.destroyed || !_state.agentId) return;
  const api = getApi();
  if (!api) return;

  try {
    const result = await api.get(`/api/v1/agents/${encodeURIComponent(_state.agentId)}`);
    const data = result?.data || result;
    if (data.agent || data) {
      _state.agent = data.agent || data;
      if (_state.container && !_state.loading) {
        renderPage(_state.container);
      }
    }
  } catch {
    // Silent fail
  }
}

/* ── Route Extraction ───────────────────────────────────────────────────── */

function extractAgentId(routeInfo) {
  if (!routeInfo) return null;
  // Route info could be a params object, a path string, or a location object
  if (routeInfo.params && routeInfo.params.id) return routeInfo.params.id;
  if (routeInfo.id) return routeInfo.id;
  if (typeof routeInfo === 'string') {
    const parts = routeInfo.split('/');
    return parts[parts.length - 1] || null;
  }
  if (routeInfo.path) {
    const parts = routeInfo.path.split('/');
    return parts[parts.length - 1] || null;
  }
  return null;
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Render — called by the router. Generates the page's HTML string.
 * @param {Object} routeInfo - Route info containing agent ID
 * @returns {string} HTML string
 */
export function render(routeInfo) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.agentId = extractAgentId(routeInfo);

  return '<div id="agent-status-root"></div>';
}

/**
 * Mount — called after HTML is inserted into the DOM.
 * @param {Element} container
 */
export function mount(container) {
  const root = container.querySelector('#agent-status-root') || container;
  _state.container = root;

  renderSkeletons(root);

  if (!_state.agentId) {
    _state.loading = false;
    renderEmpty(root);
    return;
  }

  subscribeWebSocket();
  loadAgentData(_state.agentId).then(() => {
    if (!_state.destroyed) startPolling();
  });
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();
  unsubscribeWebSocket();

  for (const fn of _state._boundListeners) {
    try { fn(); } catch (e) { /* ignore */ }
  }
  _state._boundListeners = [];

  _state.container = null;
  _state.agent = null;
  _state.agentId = null;
  _state.thoughts = [];
  _state.conversation = [];
  _state.toolCalls = [];
  _state.performance = null;
}

/* ── Router-compatible default export ────────────────────────────────────── */

/**
 * Factory function for the SPA router.
 * @param {Object} routeInfo
 * @returns {{ render: Function, mount: Function, destroy: Function }}
 */
export default function createPage(routeInfo) {
  return {
    render() {
      return render(routeInfo);
    },
    mount(container) {
      mount(container);
    },
    destroy,
  };
}
