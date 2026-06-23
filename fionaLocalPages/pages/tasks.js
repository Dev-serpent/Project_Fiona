/* ==========================================================================
   tasks.js — Task Queue / Kanban Page
   ==========================================================================
   Kanban-style task queue with three columns: Pending, In Progress,
   Completed.  Supports drag-to-move, search filtering, priority
   indicators, and full CRUD via the Fiona backend API.

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

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 5000;
const STORAGE_KEY = 'fiona_tasks_state';
const COLUMNS = ['pending', 'in_progress', 'completed'];
const COLUMN_LABELS = {
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
};

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',
  tasks: [],
  searchQuery: '',
  pollTimer: null,
  dragSource: null,
  _boundListeners: [],
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

function priorityColor(priority) {
  const map = {
    high: 'var(--danger)',
    medium: 'var(--warning)',
    low: 'var(--text-muted)',
    urgent: 'var(--danger)',
  };
  return map[priority] || 'var(--text-muted)';
}

function priorityLabel(priority) {
  const map = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
    urgent: 'Urgent',
  };
  return map[priority] || priority || 'Normal';
}

function generateId() {
  return `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function persistState() {
  try {
    const data = {
      searchQuery: _state.searchQuery,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    // Silently fail
  }
}

function loadPersistedState() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const data = JSON.parse(stored);
      _state.searchQuery = data.searchQuery || '';
    }
  } catch (e) {
    // Silently fail
  }
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

  // Filter tasks by search query
  const query = _state.searchQuery.toLowerCase().trim();
  const filtered = query
    ? _state.tasks.filter((t) =>
        (t.title || t.name || '').toLowerCase().includes(query) ||
        (t.description || '').toLowerCase().includes(query)
      )
    : _state.tasks;

  // Group by status
  const grouped = {};
  for (const col of COLUMNS) {
    grouped[col] = filtered.filter((t) => (t.status || 'pending') === col);
  }

  const totalCount = _state.tasks.length;

  container.innerHTML = html`
    <!-- Page Header -->
    <div style="margin-bottom: var(--space-5);">
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <div>
          <h1 style="font-size: var(--font-size-xxl); font-weight: var(--font-weight-bold); color: var(--text-primary); margin: 0;">
            Task Queue
          </h1>
          <p style="font-size: var(--font-size-sm); color: var(--text-muted); margin: 2px 0 0 0;">
            ${totalCount} total task${totalCount !== 1 ? 's' : ''}
          </p>
        </div>
        <button class="c-btn c-btn--primary c-btn--sm" id="btn-new-task">
          <span class="c-btn__icon">${ICONS.plus}</span>
          New Task
        </button>
      </div>
    </div>

    <!-- Search Bar -->
    <div style="position: relative; margin-bottom: var(--space-4); max-width: 360px;">
      <span style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); display: flex; color: var(--text-muted); width: 16px; height: 16px; pointer-events: none;">
        ${ICONS.search}
      </span>
      <input type="text" class="c-input" id="tasks-search-input"
             placeholder="Search tasks…"
             value="${esc(_state.searchQuery)}"
             style="padding-left: 32px; height: 34px;"
             autocomplete="off" />
    </div>

    <!-- Kanban Columns -->
    <div id="tasks-kanban" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); min-height: 400px;">
      ${html.raw(COLUMNS.map((col) => renderColumn(col, grouped[col] || [])).join(''))}
    </div>
  `;

  mountComponents(container);
}

function renderColumn(status, tasks) {
  const label = COLUMN_LABELS[status] || status;
  const count = tasks.length;

  return html`
    <div class="c-card task-column" data-column="${esc(status)}" style="display: flex; flex-direction: column; min-height: 300px;">
      <div class="c-card__header" style="padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-subtle); flex-shrink: 0;">
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <span class="c-card__title" style="font-size: var(--font-size-sm); text-transform: capitalize;">${esc(label)}</span>
          <span class="c-badge c-badge--${status === 'pending' ? 'default' : status === 'in_progress' ? 'info' : 'success'}">${count}</span>
        </div>
      </div>
      <div class="c-card__body task-column-body" data-column="${esc(status)}"
           style="flex: 1; padding: var(--space-2); overflow-y: auto; scrollbar-width: thin; min-height: 100px;">
        ${count === 0 ? html`
          <div style="text-align: center; padding: var(--space-6); color: var(--text-muted); font-size: var(--font-size-xs);">
            No tasks
          </div>
        ` : html.raw(tasks.map((task) => renderTaskCard(task)).join(''))}
      </div>
    </div>
  `;
}

function renderTaskCard(task) {
  const title = task.title || task.name || 'Untitled Task';
  const description = task.description || '';
  const priority = task.priority || 'medium';
  const createdAt = task.created_at || task.createdAt || task.timestamp || Date.now();
  const assignedTo = task.assigned_agent || task.assignedAgent || task.agent || null;
  const status = task.status || 'pending';

  return html`
    <div class="task-card" draggable="true"
         data-task-id="${esc(task.id || '')}"
         data-task-status="${esc(status)}"
         style="padding: var(--space-3); margin-bottom: var(--space-2); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); cursor: grab; transition: all var(--transition-fast);">
      <!-- Priority Indicator -->
      <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2);">
        <span style="width: 8px; height: 8px; border-radius: 50%; background: ${priorityColor(priority)}; flex-shrink: 0;"></span>
        <span class="c-badge c-badge--${priority === 'high' ? 'danger' : priority === 'medium' ? 'warning' : 'default'}" style="font-size: 9px; padding: 0 6px;">
          ${esc(priorityLabel(priority))}
        </span>
      </div>

      <!-- Title -->
      <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); margin-bottom: var(--space-1);
                  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
        ${esc(title)}
      </div>

      <!-- Description -->
      ${description ? html`
        <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: var(--space-2);
                    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
          ${esc(description)}
        </div>
      ` : ''}

      <!-- Footer -->
      <div style="display: flex; align-items: center; justify-content: space-between; margin-top: var(--space-2); font-size: var(--font-size-xxs); color: var(--text-muted);">
        <span>${timeAgo(createdAt)}</span>
        ${assignedTo ? html`<span>${esc(assignedTo)}</span>` : ''}
      </div>

      <!-- Action Buttons -->
      <div style="display: flex; gap: var(--space-1); margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-subtle);">
        ${status === 'pending' ? html`
          <button class="c-btn c-btn--sm c-btn--ghost task-action-btn" data-action="start" data-task-id="${esc(task.id || '')}" title="Move to In Progress" style="font-size: var(--font-size-xxs); padding: 2px 8px;">
            ${ICONS.play} Start
          </button>
        ` : ''}
        ${status === 'in_progress' ? html`
          <button class="c-btn c-btn--sm c-btn--ghost task-action-btn" data-action="complete" data-task-id="${esc(task.id || '')}" title="Mark Completed" style="font-size: var(--font-size-xxs); padding: 2px 8px;">
            ${ICONS.check} Complete
          </button>
        ` : ''}
        ${status === 'completed' ? html`
          <button class="c-btn c-btn--sm c-btn--ghost task-action-btn" data-action="reopen" data-task-id="${esc(task.id || '')}" title="Reopen" style="font-size: var(--font-size-xxs); padding: 2px 8px;">
            ${ICONS.refresh} Reopen
          </button>
        ` : ''}
        <button class="c-btn c-btn--sm c-btn--ghost task-action-btn" data-action="delete" data-task-id="${esc(task.id || '')}" title="Delete" style="font-size: var(--font-size-xxs); padding: 2px 8px; color: var(--danger); margin-left: auto;">
          ${ICONS.trash}
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
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4);">
        ${Array.from({ length: 3 }, () => skeletonCard({ height: '400px' }))}
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
        ${esc(_state.errorMessage || 'Unable to fetch tasks from backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="tasks-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  const retryBtn = container.querySelector('#tasks-retry-btn');
  if (retryBtn) retryBtn.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    renderSkeletons(container);
    loadData();
  });
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountComponents(container) {
  const listeners = [];

  // New Task button
  const btnNew = container.querySelector('#btn-new-task');
  if (btnNew) {
    const handler = () => showNewTaskModal();
    btnNew.addEventListener('click', handler);
    listeners.push(() => btnNew.removeEventListener('click', handler));
  }

  // Search input
  const searchEl = container.querySelector('#tasks-search-input');
  if (searchEl) {
    const handler = (e) => {
      _state.searchQuery = e.target.value;
      persistState();
      renderPage(container);
    };
    searchEl.addEventListener('input', handler);
    listeners.push(() => searchEl.removeEventListener('input', handler));
  }

  // Task action buttons (delegated)
  const kanban = container.querySelector('#tasks-kanban');
  if (kanban) {
    const handler = (e) => {
      const btn = e.target.closest('.task-action-btn');
      if (!btn) return;
      e.stopPropagation();

      const action = btn.dataset.action;
      const taskId = btn.dataset.taskId;
      if (!taskId) return;

      switch (action) {
        case 'start': moveTask(taskId, 'in_progress'); break;
        case 'complete': moveTask(taskId, 'completed'); break;
        case 'reopen': moveTask(taskId, 'pending'); break;
        case 'delete': deleteTask(taskId); break;
      }
    };
    kanban.addEventListener('click', handler);
    listeners.push(() => kanban.removeEventListener('click', handler));

    // Drag and drop on kanban
    const dragHandlers = setupDragAndDrop(kanban);
    listeners.push(...dragHandlers);
  }

  _state._boundListeners = listeners;
}

/* ── Drag and Drop ───────────────────────────────────────────────────────── */

function setupDragAndDrop(kanbanEl) {
  const cleanups = [];
  let draggedEl = null;

  // Drag start (delegated)
  const dragStartHandler = (e) => {
    const card = e.target.closest('.task-card');
    if (!card) return;
    draggedEl = card;
    card.style.opacity = '0.5';
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', card.dataset.taskId || '');
    _state.dragSource = card.dataset.taskStatus;
  };
  kanbanEl.addEventListener('dragstart', dragStartHandler);
  cleanups.push(() => kanbanEl.removeEventListener('dragstart', dragStartHandler));

  // Drag end
  const dragEndHandler = () => {
    if (draggedEl) {
      draggedEl.style.opacity = '1';
      draggedEl = null;
    }
    _state.dragSource = null;
    // Remove drag-over highlights
    kanbanEl.querySelectorAll('.task-column-body').forEach((col) => {
      col.style.background = '';
    });
  };
  kanbanEl.addEventListener('dragend', dragEndHandler);
  cleanups.push(() => kanbanEl.removeEventListener('dragend', dragEndHandler));

  // Drag over columns
  kanbanEl.querySelectorAll('.task-column-body').forEach((col) => {
    const handler = (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      col.style.background = 'var(--accent-muted)';
    };
    col.addEventListener('dragover', handler);
    cleanups.push(() => col.removeEventListener('dragover', handler));

    const leaveHandler = () => {
      col.style.background = '';
    };
    col.addEventListener('dragleave', leaveHandler);
    cleanups.push(() => col.removeEventListener('dragleave', leaveHandler));

    const dropHandler = async (e) => {
      e.preventDefault();
      col.style.background = '';
      const taskId = e.dataTransfer.getData('text/plain');
      const targetStatus = col.dataset.column;
      if (!taskId || !targetStatus) return;
      // Check that the task actually moved to a different column
      const task = _state.tasks.find((t) => t.id === taskId);
      if (task && task.status !== targetStatus) {
        await moveTask(taskId, targetStatus);
      }
    };
    col.addEventListener('drop', dropHandler);
    cleanups.push(() => col.removeEventListener('drop', dropHandler));
  });

  return cleanups;
}

/* ── Actions ────────────────────────────────────────────────────────────── */

async function moveTask(taskId, newStatus) {
  const api = getApi();
  if (!api) return;

  // Optimistic update
  const task = _state.tasks.find((t) => t.id === taskId);
  if (!task) return;
  const prevStatus = task.status;
  task.status = newStatus;

  // Re-render optimistically
  if (_state.container) renderPage(_state.container);

  try {
    await api.put(`/api/v1/tasks/${encodeURIComponent(taskId)}`, { status: newStatus });
    toast.showToast('success', 'Updated', `Task moved to ${COLUMN_LABELS[newStatus] || newStatus}.`);
  } catch (err) {
    // Revert on failure
    task.status = prevStatus;
    if (_state.container) renderPage(_state.container);
    toast.showToast('error', 'Failed', err.message || 'Could not update task.');
  }
}

async function deleteTask(taskId) {
  const api = getApi();
  if (!api) return;

  const task = _state.tasks.find((t) => t.id === taskId);
  if (!task) return;

  // Optimistic removal
  _state.tasks = _state.tasks.filter((t) => t.id !== taskId);
  if (_state.container) renderPage(_state.container);

  try {
    await api.del(`/api/v1/tasks/${encodeURIComponent(taskId)}`);
    toast.showToast('info', 'Deleted', 'Task has been deleted.');
  } catch (err) {
    // Revert: re-add the task
    _state.tasks.push(task);
    if (_state.container) renderPage(_state.container);
    toast.showToast('error', 'Failed', err.message || 'Could not delete task.');
  }
}

async function showNewTaskModal() {
  const { modal } = await import('../js/components/Modal.js');

  // Build a list of agents for the assignee dropdown
  let agentOptions = '<option value="">Unassigned</option>';
  try {
    const api = getApi();
    if (api) {
      const result = await api.get('/api/v1/agents');
      const agents = Array.isArray(result?.data) ? result.data : Array.isArray(result) ? result : [];
      agentOptions += agents.map((a) =>
        `<option value="${esc(a.id || a.name || '')}">${esc(a.name || a.id || '')}</option>`
      ).join('');
    }
  } catch (e) {
    // Fall back to no agents
  }

  const result = await modal.showModal({
    title: 'New Task',
    content: html`
      <div class="c-form-group" style="margin-bottom: var(--space-4);">
        <label class="c-form-group__label">Task Title *</label>
        <input type="text" class="c-input" id="new-task-title" placeholder="Enter task title" autofocus />
      </div>
      <div class="c-form-group" style="margin-bottom: var(--space-4);">
        <label class="c-form-group__label">Description</label>
        <textarea class="c-textarea" id="new-task-desc" placeholder="Optional description…" rows="3"></textarea>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4);">
        <div class="c-form-group">
          <label class="c-form-group__label">Priority</label>
          <select class="c-select" id="new-task-priority">
            <option value="low">Low</option>
            <option value="medium" selected>Medium</option>
            <option value="high">High</option>
          </select>
        </div>
        <div class="c-form-group">
          <label class="c-form-group__label">Assigned Agent</label>
          <select class="c-select" id="new-task-agent">
            ${html.raw(agentOptions)}
          </select>
        </div>
      </div>
    `,
    size: 'md',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Create Task', value: 'create', variant: 'primary' },
    ],
  });

  if (result !== 'create') return;

  const titleEl = document.getElementById('new-task-title');
  const descEl = document.getElementById('new-task-desc');
  const priorityEl = document.getElementById('new-task-priority');
  const agentEl = document.getElementById('new-task-agent');

  const title = titleEl?.value?.trim();
  if (!title) {
    toast.showToast('warning', 'Validation', 'Task title is required.');
    return;
  }

  const description = descEl?.value?.trim() || '';
  const priority = priorityEl?.value || 'medium';
  const assignedAgent = agentEl?.value || null;

  const api = getApi();
  if (!api) {
    toast.showToast('error', 'Error', 'API client not available.');
    return;
  }

  // Optimistic add
  const tempId = generateId();
  const newTask = {
    id: tempId,
    title,
    description,
    priority,
    status: 'pending',
    assigned_agent: assignedAgent,
    created_at: Date.now(),
  };
  _state.tasks.unshift(newTask);
  if (_state.container) renderPage(_state.container);

  try {
    const result = await api.post('/api/v1/tasks', {
      title,
      description,
      priority,
      assigned_agent: assignedAgent,
    });
    toast.showToast('success', 'Created', `Task "${title}" has been created.`);

    // Replace temp ID with real ID
    const realTask = result?.data || result;
    if (realTask && realTask.id) {
      const idx = _state.tasks.findIndex((t) => t.id === tempId);
      if (idx >= 0) {
        _state.tasks[idx] = { ...newTask, ...realTask };
      }
    }
  } catch (err) {
    // Remove optimistic task
    _state.tasks = _state.tasks.filter((t) => t.id !== tempId);
    if (_state.container) renderPage(_state.container);
    toast.showToast('error', 'Failed', err.message || 'Could not create task.');
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
    if (_state.container) renderPage(_state.container);
    return;
  }

  try {
    const result = await api.get('/api/v1/tasks');
    const tasks = Array.isArray(result?.data) ? result.data : Array.isArray(result) ? result : [];

    _state.tasks = tasks;
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
  } catch (err) {
    console.error('[tasks] Failed to load tasks:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch tasks.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
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
    const result = await api.get('/api/v1/tasks');
    const tasks = Array.isArray(result?.data) ? result.data : Array.isArray(result) ? result : [];
    _state.tasks = tasks;
    if (_state.container && !_state.loading) {
      renderPage(_state.container);
    }
  } catch {
    // Silent fail during poll
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

  loadPersistedState();
  renderSkeletons(container);
  loadData().then(() => {
    if (!_state.destroyed) startPolling();
  });
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();

  for (const fn of _state._boundListeners) {
    try { fn(); } catch (e) { /* ignore */ }
  }
  _state._boundListeners = [];

  _state.container = null;
  _state.tasks = [];
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
      return '<div id="tasks-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#tasks-root') || container;
      render(root);
    },
    destroy,
  };
}
