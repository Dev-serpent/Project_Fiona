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
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const POLL_INTERVAL = 5000;
const STORAGE_KEY = 'fiona_tasks_state';
const COLUMNS = ['pending', 'in_progress', 'completed'];
const COLUMN_LABELS = {
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
};

const CATEGORY_COLORS = {
  bug: '#e74c3c',
  feature: '#3498db',
  chore: '#95a5a6',
  docs: '#2ecc71',
  improvement: '#9b59b6',
  question: '#f39c12',
  task: '#1abc9c',
  research: '#e67e22',
};

const SORT_OPTIONS = {
  priority: 'Priority (High→Low)',
  due_date: 'Due Date (Soonest)',
  created: 'Created (Newest)',
  alpha: 'Alphabetical (A→Z)',
};

const PRIORITY_ORDER = { urgent: 0, high: 1, medium: 2, low: 3 };

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
  /* ── New task management features ── */
  sortBy: 'created',
  priorityFilter: '',
  categoryFilter: '',
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

/* ── Due Date Helpers ──────────────────────────────────────────────────── */

function isOverdue(task) {
  if (!task.due_date) return false;
  const due = new Date(task.due_date);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const status = task.status || 'pending';
  return due < now && status !== 'completed';
}

function formatDueDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function daysUntilDue(dateStr) {
  if (!dateStr) return null;
  const due = new Date(dateStr);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const diff = Math.ceil((due - now) / (1000 * 60 * 60 * 24));
  return diff;
}

/* ── Category / Tag Helpers ────────────────────────────────────────────── */

function categoryColor(cat) {
  if (!cat) return 'var(--text-muted)';
  const lower = cat.toLowerCase().trim();
  return CATEGORY_COLORS[lower] || stringToColor(lower);
}

function stringToColor(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 55%, 50%)`;
}

function collectCategories(tasks) {
  const cats = new Set();
  for (const t of tasks) {
    if (t.category) cats.add(t.category.trim());
  }
  return Array.from(cats).sort();
}

function generateId() {
  return `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function generateSubtaskId() {
  return `st-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

/* ── Sorting ──────────────────────────────────────────────────────────── */

function sortTasks(tasks, sortBy) {
  const sorted = [...tasks];
  switch (sortBy) {
    case 'priority':
      sorted.sort((a, b) => {
        const pa = PRIORITY_ORDER[a.priority] ?? 3;
        const pb = PRIORITY_ORDER[b.priority] ?? 3;
        if (pa !== pb) return pa - pb;
        // Secondary: by created date desc
        return (b.created_at || b.createdAt || 0) - (a.created_at || a.createdAt || 0);
      });
      break;
    case 'due_date':
      sorted.sort((a, b) => {
        const da = a.due_date ? new Date(a.due_date).getTime() : Infinity;
        const db = b.due_date ? new Date(b.due_date).getTime() : Infinity;
        if (da !== db) return da - db;
        return (b.created_at || b.createdAt || 0) - (a.created_at || a.createdAt || 0);
      });
      break;
    case 'alpha':
      sorted.sort((a, b) => {
        const ta = (a.title || a.name || '').toLowerCase();
        const tb = (b.title || b.name || '').toLowerCase();
        return ta.localeCompare(tb);
      });
      break;
    case 'created':
    default:
      sorted.sort((a, b) => (b.created_at || b.createdAt || 0) - (a.created_at || a.createdAt || 0));
      break;
  }
  return sorted;
}

/* ── Progress ──────────────────────────────────────────────────────────── */

function computeProgress(task) {
  if (task.subtasks && Array.isArray(task.subtasks) && task.subtasks.length > 0) {
    const done = task.subtasks.filter((st) => st.completed).length;
    return Math.round((done / task.subtasks.length) * 100);
  }
  return task.progress != null ? Math.min(100, Math.max(0, Number(task.progress))) : 0;
}

function persistState() {
  try {
    const data = {
      searchQuery: _state.searchQuery,
      sortBy: _state.sortBy,
      priorityFilter: _state.priorityFilter,
      categoryFilter: _state.categoryFilter,
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
      _state.sortBy = data.sortBy || 'created';
      _state.priorityFilter = data.priorityFilter || '';
      _state.categoryFilter = data.categoryFilter || '';
    }
  } catch (e) {
    // Silently fail
  }
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

  // Filter tasks by search query (enhanced: covers title, description, category, tags)
  const query = _state.searchQuery.toLowerCase().trim();
  let filtered = query
    ? _state.tasks.filter((t) => {
        const searchable = [
          t.title || t.name || '',
          t.description || '',
          t.category || '',
          ...(Array.isArray(t.tags) ? t.tags : []),
        ].join(' ').toLowerCase();
        return searchable.includes(query);
      })
    : _state.tasks;

  // Filter by priority
  if (_state.priorityFilter) {
    filtered = filtered.filter((t) => (t.priority || 'medium') === _state.priorityFilter);
  }

  // Filter by category
  if (_state.categoryFilter) {
    filtered = filtered.filter((t) => (t.category || '').toLowerCase() === _state.categoryFilter.toLowerCase());
  }

  // Sort within columns
  const totalCount = _state.tasks.length;

  // Group by status, then sort within each group
  const grouped = {};
  for (const col of COLUMNS) {
    const columnTasks = filtered.filter((t) => (t.status || 'pending') === col);
    grouped[col] = sortTasks(columnTasks, _state.sortBy);
  }

  // Build toolbar + kanban content
  const categories = collectCategories(_state.tasks);
  const toolbarContent = renderToolbar(categories);
  const kanbanContent = COLUMNS.map((col) => renderColumn(col, grouped[col] || [])).join('');

  const data = {
    taskCount: totalCount,
    taskPlural: totalCount !== 1 ? 's' : '',
    plusIcon: ICONS.plus.html,
    searchIcon: ICONS.search.html,
    searchQuery: esc(_state.searchQuery),
    toolbarContent,
    kanbanContent,
  };

  container.innerHTML = await loadTemplate('tasks', data);
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
  const dueDate = task.due_date || null;
  const category = task.category || null;
  const tags = Array.isArray(task.tags) ? task.tags : (task.tags ? [task.tags] : []);
  const overdue = isOverdue(task);
  const progress = computeProgress(task);
  const subtaskCount = (task.subtasks && Array.isArray(task.subtasks)) ? task.subtasks.length : 0;
  const subtaskDone = subtaskCount ? task.subtasks.filter((st) => st.completed).length : 0;

  // Due date display
  let dueDisplay = '';
  let dueLabel = '';
  if (dueDate) {
    const days = daysUntilDue(dueDate);
    if (days !== null) {
      if (days < 0) dueLabel = 'OVERDUE';
      else if (days === 0) dueLabel = 'Due today';
      else if (days === 1) dueLabel = 'Due tomorrow';
      else if (days <= 7) dueLabel = `Due in ${days}d`;
      else dueLabel = formatDueDate(dueDate);
    }
    dueDisplay = dueLabel;
  }

  return html`
    <div class="task-card${overdue ? ' task-card--overdue' : ''}" draggable="true"
         data-task-id="${esc(task.id || '')}"
         data-task-status="${esc(status)}"
         style="padding: var(--space-3); margin-bottom: var(--space-2); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); cursor: grab; transition: all var(--transition-fast);">
      <!-- Row 1: Priority + Category + Due Date -->
      <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1); flex-wrap: wrap;">
        <!-- Priority Dot -->
        <span style="width: 8px; height: 8px; border-radius: 50%; background: ${priorityColor(priority)}; flex-shrink: 0;"></span>
        <span class="c-badge c-badge--${priority === 'high' ? 'danger' : priority === 'medium' ? 'warning' : 'default'}" style="font-size: 9px; padding: 0 6px;">
          ${esc(priorityLabel(priority))}
        </span>

        <!-- Category Badge -->
        ${category ? html`
          <span class="category-badge" style="background: ${categoryColor(category)}22; color: ${categoryColor(category)}; border: 1px solid ${categoryColor(category)}44;">
            ${esc(category)}
          </span>
        ` : ''}

        <!-- Due Date -->
        ${dueDisplay ? html`
          <span class="${overdue ? 'overdue-text' : ''}" style="font-size: 9px; margin-left: auto; white-space: nowrap;">
            ${overdue ? html`${ICONS.warning} ` : ''}${esc(dueDisplay)}
          </span>
        ` : ''}
      </div>

      <!-- Title -->
      <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); margin-bottom: var(--space-1);
                  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
        ${esc(title)}
      </div>

      <!-- Description -->
      ${description ? html`
        <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: var(--space-1);
                    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
          ${esc(description)}
        </div>
      ` : ''}

      <!-- Tags -->
      ${tags.length > 0 ? html`
        <div style="display: flex; flex-wrap: wrap; gap: 3px; margin-bottom: var(--space-1);">
          ${html.raw(tags.map((tag) => html`
            <span class="tag-badge" style="background: ${stringToColor(tag)}22; color: ${stringToColor(tag)}; border: 1px solid ${stringToColor(tag)}44;">
              ${esc(tag)}
            </span>
          `).join(''))}
        </div>
      ` : ''}

      <!-- Progress Bar -->
      ${progress > 0 || subtaskCount > 0 ? html`
        <div style="margin: var(--space-1) 0;">
          <div class="task-progress-bar">
            <div class="task-progress-fill" style="width: ${progress}%; background: ${progress === 100 ? 'var(--success)' : 'var(--accent)'};"></div>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 8px; color: var(--text-muted);">
            <span>${subtaskCount ? `${subtaskDone}/${subtaskCount} subtasks` : `${progress}%`}</span>
          </div>
        </div>
      ` : ''}

      <!-- Footer -->
      <div style="display: flex; align-items: center; justify-content: space-between; margin-top: var(--space-1); font-size: var(--font-size-xxs); color: var(--text-muted);">
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
        <button class="c-btn c-btn--sm c-btn--ghost task-action-btn" data-action="edit" data-task-id="${esc(task.id || '')}" title="Edit Task" style="font-size: var(--font-size-xxs); padding: 2px 8px;">
          ${ICONS.edit}
        </button>
        <button class="c-btn c-btn--sm c-btn--ghost task-action-btn" data-action="delete" data-task-id="${esc(task.id || '')}" title="Delete" style="font-size: var(--font-size-xxs); padding: 2px 8px; color: var(--danger); margin-left: auto;">
          ${ICONS.trash}
        </button>
      </div>
    </div>
  `;
}

/* ── Toolbar Renderer ──────────────────────────────────────────────────── */

function renderToolbar(categories) {
  const sortBy = _state.sortBy || 'created';
  const priorityFilter = _state.priorityFilter || '';
  const categoryFilter = _state.categoryFilter || '';

  // Build sort options
  const sortOptions = Object.entries(SORT_OPTIONS).map(([value, label]) =>
    `<option value="${value}"${value === sortBy ? ' selected' : ''}>${esc(label)}</option>`
  ).join('');

  // Build priority filter options
  const priorityOptions = [
    '<option value="">All Priorities</option>',
    '<option value="urgent"' + (priorityFilter === 'urgent' ? ' selected' : '') + '>Urgent</option>',
    '<option value="high"' + (priorityFilter === 'high' ? ' selected' : '') + '>High</option>',
    '<option value="medium"' + (priorityFilter === 'medium' ? ' selected' : '') + '>Medium</option>',
    '<option value="low"' + (priorityFilter === 'low' ? ' selected' : '') + '>Low</option>',
  ].join('');

  // Build category filter options
  const categoryOptions = [
    '<option value="">All Categories</option>',
    ...categories.map((cat) =>
      `<option value="${esc(cat)}"${cat === categoryFilter ? ' selected' : ''}>${esc(cat)}</option>`
    ),
  ].join('');

  return `
    <div class="task-toolbar">
      <div class="task-toolbar__group">
        <span class="task-toolbar__label">Sort:</span>
        <select data-toolbar="sort" id="toolbar-sort">${sortOptions}</select>
      </div>
      <div class="task-toolbar__group">
        <span class="task-toolbar__label">Priority:</span>
        <select data-toolbar="priority-filter" id="toolbar-priority">${priorityOptions}</select>
      </div>
      <div class="task-toolbar__group">
        <span class="task-toolbar__label">Category:</span>
        <select data-toolbar="category-filter" id="toolbar-category">${categoryOptions}</select>
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
    const handler = async (e) => {
      _state.searchQuery = e.target.value;
      persistState();
      await renderPage(container);
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
        case 'edit': showEditTaskModal(taskId); break;
        case 'delete': deleteTask(taskId); break;
        case 'toggle-subtask': {
          const subtaskId = btn.dataset.subtaskId;
          if (subtaskId) toggleSubtask(taskId, subtaskId);
          break;
        }
      }
    };
    kanban.addEventListener('click', handler);
    listeners.push(() => kanban.removeEventListener('click', handler));

    // Drag and drop on kanban
    const dragHandlers = setupDragAndDrop(kanban);
    listeners.push(...dragHandlers);
  }

  // Toolbar: Sort
  const sortEl = container.querySelector('#toolbar-sort');
  if (sortEl) {
    const handler = async (e) => {
      _state.sortBy = e.target.value;
      persistState();
      await renderPage(container);
    };
    sortEl.addEventListener('change', handler);
    listeners.push(() => sortEl.removeEventListener('change', handler));
  }

  // Toolbar: Priority filter
  const priorityEl = container.querySelector('#toolbar-priority');
  if (priorityEl) {
    const handler = async (e) => {
      _state.priorityFilter = e.target.value;
      persistState();
      await renderPage(container);
    };
    priorityEl.addEventListener('change', handler);
    listeners.push(() => priorityEl.removeEventListener('change', handler));
  }

  // Toolbar: Category filter
  const catEl = container.querySelector('#toolbar-category');
  if (catEl) {
    const handler = async (e) => {
      _state.categoryFilter = e.target.value;
      persistState();
      await renderPage(container);
    };
    catEl.addEventListener('change', handler);
    listeners.push(() => catEl.removeEventListener('change', handler));
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
  if (_state.container) await renderPage(_state.container);

  try {
    await api.put(`/api/v1/tasks/${encodeURIComponent(taskId)}`, { status: newStatus });
    toast.showToast('success', 'Updated', `Task moved to ${COLUMN_LABELS[newStatus] || newStatus}.`);
  } catch (err) {
    // Revert on failure
    task.status = prevStatus;
    if (_state.container) await renderPage(_state.container);
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
  if (_state.container) await renderPage(_state.container);

  try {
    await api.del(`/api/v1/tasks/${encodeURIComponent(taskId)}`);
    toast.showToast('info', 'Deleted', 'Task has been deleted.');
  } catch (err) {
    // Revert: re-add the task
    _state.tasks.push(task);
    if (_state.container) await renderPage(_state.container);
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

  // Collect existing categories for the datalist
  const categories = collectCategories(_state.tasks);
  const categoryListId = 'new-task-category-list';
  const categoryDatalist = categories.length > 0
    ? `<datalist id="${categoryListId}">${categories.map((c) => `<option value="${esc(c)}">`).join('')}</datalist>`
    : '';

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
            <option value="urgent">Urgent</option>
          </select>
        </div>
        <div class="c-form-group">
          <label class="c-form-group__label">Due Date</label>
          <input type="date" class="c-input" id="new-task-due" />
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4);">
        <div class="c-form-group">
          <label class="c-form-group__label">Category</label>
          <input type="text" class="c-input" id="new-task-category" placeholder="e.g. bug, feature" list="${categoryDatalist ? categoryListId : ''}" />
          ${html.raw(categoryDatalist)}
        </div>
        <div class="c-form-group">
          <label class="c-form-group__label">Tags</label>
          <input type="text" class="c-input" id="new-task-tags" placeholder="Comma-separated" />
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4);">
        <div class="c-form-group">
          <label class="c-form-group__label">Assigned Agent</label>
          <select class="c-select" id="new-task-agent">
            ${html.raw(agentOptions)}
          </select>
        </div>
        <div class="c-form-group">
          <label class="c-form-group__label">Progress</label>
          <div style="display: flex; align-items: center; gap: var(--space-2);">
            <input type="range" class="progress-slider" id="new-task-progress" min="0" max="100" value="0" />
            <span style="font-size: var(--font-size-xs); min-width: 30px; text-align: right;" id="new-task-progress-label">0%</span>
          </div>
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
  const dueEl = document.getElementById('new-task-due');
  const categoryEl = document.getElementById('new-task-category');
  const tagsEl = document.getElementById('new-task-tags');
  const agentEl = document.getElementById('new-task-agent');
  const progressEl = document.getElementById('new-task-progress');

  const title = titleEl?.value?.trim();
  if (!title) {
    toast.showToast('warning', 'Validation', 'Task title is required.');
    return;
  }

  const description = descEl?.value?.trim() || '';
  const priority = priorityEl?.value || 'medium';
  const dueDate = dueEl?.value || null;
  const category = categoryEl?.value?.trim() || null;
  const tagsStr = tagsEl?.value?.trim() || '';
  const tags = tagsStr ? tagsStr.split(',').map((t) => t.trim()).filter(Boolean) : [];
  const assignedAgent = agentEl?.value || null;
  const progress = progressEl ? parseInt(progressEl.value, 10) : 0;

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
    due_date: dueDate,
    category,
    tags,
    assigned_agent: assignedAgent,
    progress,
    subtasks: [],
    created_at: Date.now(),
  };
  _state.tasks.unshift(newTask);
  if (_state.container) await renderPage(_state.container);

  try {
    const result = await api.post('/api/v1/tasks', {
      title,
      description,
      priority,
      due_date: dueDate,
      category,
      tags,
      assigned_agent: assignedAgent,
      progress,
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
    if (_state.container) await renderPage(_state.container);
    toast.showToast('error', 'Failed', err.message || 'Could not create task.');
  }
}

/* ── Edit Task Modal ────────────────────────────────────────────────────── */

async function showEditTaskModal(taskId) {
  const task = _state.tasks.find((t) => t.id === taskId);
  if (!task) return;

  const { modal } = await import('../js/components/Modal.js');

  // Build a list of agents for the assignee dropdown
  let agentOptions = '<option value="">Unassigned</option>';
  try {
    const api = getApi();
    if (api) {
      const result = await api.get('/api/v1/agents');
      const agents = Array.isArray(result?.data) ? result.data : Array.isArray(result) ? result : [];
      agentOptions += agents.map((a) =>
        `<option value="${esc(a.id || a.name || '')}"${(a.id === (task.assigned_agent || task.assignedAgent)) ? ' selected' : ''}>${esc(a.name || a.id || '')}</option>`
      ).join('');
    }
  } catch (e) { /* Fall back */ }

  // Collect existing categories for datalist
  const categories = collectCategories(_state.tasks);
  const categoryListId = 'edit-task-category-list';
  const categoryDatalist = categories.length > 0
    ? `<datalist id="${categoryListId}">${categories.map((c) => `<option value="${esc(c)}">`).join('')}</datalist>`
    : '';

  // Build subtask list HTML
  const subtasks = Array.isArray(task.subtasks) ? task.subtasks : [];
  const subtasksHtml = subtasks.length === 0
    ? '<div style="font-size: var(--font-size-xs); color: var(--text-muted); padding: var(--space-2);">No subtasks yet</div>'
    : subtasks.map((st, idx) =>
        `<div class="subtask-item" data-subtask-idx="${idx}">
          <input type="checkbox" class="edit-subtask-checkbox" data-subtask-id="${esc(st.id || '')}" ${st.completed ? 'checked' : ''} />
          <input type="text" class="c-input edit-subtask-input" value="${esc(st.title)}" style="flex: 1; height: 28px; font-size: var(--font-size-xs);" />
          <button type="button" class="c-btn c-btn--sm c-btn--ghost edit-subtask-remove" data-subtask-id="${esc(st.id || '')}" style="color: var(--danger); padding: 2px 4px;">${ICONS.trash}</button>
        </div>`
      ).join('');

  const progress = computeProgress(task);

  const result = await modal.showModal({
    title: 'Edit Task',
    content: html`
      <div class="c-form-group" style="margin-bottom: var(--space-4);">
        <label class="c-form-group__label">Task Title *</label>
        <input type="text" class="c-input" id="edit-task-title" value="${esc(task.title || task.name || '')}" autofocus />
      </div>
      <div class="c-form-group" style="margin-bottom: var(--space-4);">
        <label class="c-form-group__label">Description</label>
        <textarea class="c-textarea" id="edit-task-desc" rows="3">${esc(task.description || '')}</textarea>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4);">
        <div class="c-form-group">
          <label class="c-form-group__label">Priority</label>
          <select class="c-select" id="edit-task-priority">
            <option value="low"${task.priority === 'low' ? ' selected' : ''}>Low</option>
            <option value="medium"${(!task.priority || task.priority === 'medium') ? ' selected' : ''}>Medium</option>
            <option value="high"${task.priority === 'high' ? ' selected' : ''}>High</option>
            <option value="urgent"${task.priority === 'urgent' ? ' selected' : ''}>Urgent</option>
          </select>
        </div>
        <div class="c-form-group">
          <label class="c-form-group__label">Due Date</label>
          <input type="date" class="c-input" id="edit-task-due" value="${esc(task.due_date || '')}" />
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4);">
        <div class="c-form-group">
          <label class="c-form-group__label">Category</label>
          <input type="text" class="c-input" id="edit-task-category" value="${esc(task.category || '')}" placeholder="e.g. bug, feature" list="${categoryDatalist ? categoryListId : ''}" />
          ${html.raw(categoryDatalist)}
        </div>
        <div class="c-form-group">
          <label class="c-form-group__label">Tags</label>
          <input type="text" class="c-input" id="edit-task-tags" value="${esc(Array.isArray(task.tags) ? task.tags.join(', ') : (task.tags || ''))}" placeholder="Comma-separated" />
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4);">
        <div class="c-form-group">
          <label class="c-form-group__label">Assigned Agent</label>
          <select class="c-select" id="edit-task-agent">
            ${html.raw(agentOptions)}
          </select>
        </div>
        <div class="c-form-group">
          <label class="c-form-group__label">Progress: <span id="edit-task-progress-label">${progress}%</span></label>
          <input type="range" class="progress-slider" id="edit-task-progress" min="0" max="100" value="${progress}" />
        </div>
      </div>

      <!-- Subtasks Section -->
      <div style="margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--border-subtle);">
        <label class="c-form-group__label" style="margin-bottom: var(--space-2);">Subtasks</label>
        <div id="edit-subtask-list">
          ${html.raw(subtasksHtml)}
        </div>
        <div style="display: flex; gap: var(--space-2); margin-top: var(--space-2);">
          <input type="text" class="c-input" id="edit-subtask-new-input" placeholder="New subtask title…" style="flex: 1; height: 30px; font-size: var(--font-size-xs);" />
          <button type="button" class="c-btn c-btn--sm c-btn--ghost" id="edit-subtask-add-btn" style="font-size: var(--font-size-xs);">+ Add</button>
        </div>
      </div>
    `,
    size: 'md',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Save Changes', value: 'save', variant: 'primary' },
    ],
  });

  if (result !== 'save') return;

  // Gather subtask data from the modal
  const modalSubtaskItems = document.querySelectorAll('#edit-subtask-list .subtask-item');
  const updatedSubtasks = [];
  modalSubtaskItems.forEach((item) => {
    const checkbox = item.querySelector('.edit-subtask-checkbox');
    const input = item.querySelector('.edit-subtask-input');
    const id = checkbox ? checkbox.dataset.subtaskId : generateSubtaskId();
    if (input && input.value.trim()) {
      updatedSubtasks.push({
        id: id || generateSubtaskId(),
        title: input.value.trim(),
        completed: checkbox ? checkbox.checked : false,
      });
    }
  });

  // Gather new subtask from the add input
  const newSubtaskInput = document.getElementById('edit-subtask-new-input');
  if (newSubtaskInput && newSubtaskInput.value.trim()) {
    updatedSubtasks.push({
      id: generateSubtaskId(),
      title: newSubtaskInput.value.trim(),
      completed: false,
    });
  }

  const title = document.getElementById('edit-task-title')?.value?.trim();
  if (!title) {
    toast.showToast('warning', 'Validation', 'Task title is required.');
    return;
  }

  const updates = {
    title,
    description: document.getElementById('edit-task-desc')?.value?.trim() || '',
    priority: document.getElementById('edit-task-priority')?.value || 'medium',
    due_date: document.getElementById('edit-task-due')?.value || null,
    category: document.getElementById('edit-task-category')?.value?.trim() || null,
    tags: (document.getElementById('edit-task-tags')?.value?.trim() || '').split(',').map((t) => t.trim()).filter(Boolean),
    assigned_agent: document.getElementById('edit-task-agent')?.value || null,
    progress: parseInt(document.getElementById('edit-task-progress')?.value || '0', 10),
    subtasks: updatedSubtasks,
  };

  await updateTask(taskId, updates);
}

async function updateTask(taskId, updates) {
  const api = getApi();
  if (!api) return;

  const task = _state.tasks.find((t) => t.id === taskId);
  if (!task) return;

  // Save previous state for rollback
  const prevState = { ...task };

  // Optimistic update
  Object.assign(task, updates);
  if (_state.container) await renderPage(_state.container);

  try {
    await api.put(`/api/v1/tasks/${encodeURIComponent(taskId)}`, updates);
    toast.showToast('success', 'Updated', 'Task has been updated.');
  } catch (err) {
    // Revert on failure
    Object.assign(task, prevState);
    if (_state.container) await renderPage(_state.container);
    toast.showToast('error', 'Failed', err.message || 'Could not update task.');
  }
}

async function toggleSubtask(taskId, subtaskId) {
  const task = _state.tasks.find((t) => t.id === taskId);
  if (!task || !Array.isArray(task.subtasks)) return;

  const subtask = task.subtasks.find((st) => st.id === subtaskId);
  if (!subtask) return;

  subtask.completed = !subtask.completed;

  // Re-render
  if (_state.container) await renderPage(_state.container);

  // Sync to backend
  const api = getApi();
  if (api) {
    try {
      await api.put(`/api/v1/tasks/${encodeURIComponent(taskId)}`, {
        subtasks: task.subtasks,
      });
    } catch (err) {
      // Silent fail — the toggle already happened optimistically
    }
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
    const result = await api.get('/api/v1/tasks');
    const tasks = Array.isArray(result?.data) ? result.data : Array.isArray(result) ? result : [];

    _state.tasks = tasks;
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  } catch (err) {
    console.error('[tasks] Failed to load tasks:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch tasks.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
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
      await renderPage(_state.container);
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
