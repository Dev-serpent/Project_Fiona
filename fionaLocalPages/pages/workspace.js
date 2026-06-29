/* ==========================================================================
   workspace.js — Project Workspace Overview Page
   ==========================================================================
   Displays project info, file stats, git status, recent files, quick
   actions, recent activity, and project health for the current Fiona
   workspace.
   
   Now also provides full Workspace Manager: create, switch, delete
   workspaces, persist to localStorage, sync with store.
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';
import { modal } from '../js/components/Modal.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
  skeletonCircle,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const MAX_RECENT_FILES = 10;
const MAX_ACTIVITY_ITEMS = 10;
const MAX_RECENT_PROJECTS = 8;

const WS_STORAGE_KEY = 'fiona_workspaces';
const WS_ACTIVE_KEY = 'fiona_active_workspace_id';

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  // Workspace management
  workspaces: [],
  activeWorkspaceId: null,

  // Project info
  projectName: '',
  projectDescription: '',
  projectPath: '',
  fileCount: 0,
  dirCount: 0,
  linesOfCode: 0,

  // Git info
  gitBranch: '',
  gitLastCommit: '',
  gitLastAuthor: '',
  gitLastTimestamp: null,

  // Recent files
  recentFiles: [],

  // Quick bookmarks
  bookmarks: [],

  // Recent activity
  recentActivity: [],

  // Project health
  depIssues: [],
  lintIssues: [],
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
  if (sec < 10) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function formatNumber(n) {
  if (n == null) return '—';
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(n);
}

function generateId() {
  return 'ws_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

/* ── Workspace Persistence ──────────────────────────────────────────────── */

function loadWorkspaces() {
  try {
    const stored = localStorage.getItem(WS_STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveWorkspaces(workspaces) {
  try {
    localStorage.setItem(WS_STORAGE_KEY, JSON.stringify(workspaces));
  } catch (e) {
    console.warn('[workspace] Failed to save workspaces:', e);
  }
}

function loadActiveWorkspaceId() {
  try {
    return localStorage.getItem(WS_ACTIVE_KEY) || null;
  } catch {
    return null;
  }
}

function saveActiveWorkspaceId(id) {
  try {
    if (id) {
      localStorage.setItem(WS_ACTIVE_KEY, id);
    } else {
      localStorage.removeItem(WS_ACTIVE_KEY);
    }
  } catch (e) {
    console.warn('[workspace] Failed to save active workspace ID:', e);
  }
}

function getActiveWorkspace() {
  if (!_state.activeWorkspaceId) return null;
  return _state.workspaces.find((ws) => ws.id === _state.activeWorkspaceId) || null;
}

/* ── Workspace CRUD ─────────────────────────────────────────────────────── */

function findWorkspaceIndex(id) {
  return _state.workspaces.findIndex((ws) => ws.id === id);
}

function addWorkspace(ws) {
  _state.workspaces.push(ws);
  saveWorkspaces(_state.workspaces);
}

function removeWorkspace(id) {
  _state.workspaces = _state.workspaces.filter((ws) => ws.id !== id);
  saveWorkspaces(_state.workspaces);
}

function updateWorkspace(id, updates) {
  const idx = findWorkspaceIndex(id);
  if (idx === -1) return;
  _state.workspaces[idx] = { ..._state.workspaces[idx], ...updates };
  saveWorkspaces(_state.workspaces);
}

/**
 * Switch to a workspace: update store, set active workspace, reload.
 */
function switchToWorkspace(id) {
  const ws = _state.workspaces.find((w) => w.id === id);
  if (!ws) {
    showToast('error', 'Workspace not found.');
    return;
  }

  // Update active workspace ID
  _state.activeWorkspaceId = ws.id;
  saveActiveWorkspaceId(ws.id);

  // Update last opened timestamp
  updateWorkspace(ws.id, { lastOpened: Date.now() });

  // Sync the store
  const store = getStore();
  if (store) {
    store.set('workspace.currentPath', ws.path);
    store.set('workspace.recentFiles', ws.recentFiles || []);
    store.set('workspace.openFiles', ws.openFiles || []);
  }

  // Reload the page data
  _state.error = false;
  _state.loading = true;
  if (_state.container) {
    renderSkeletons(_state.container);
  }
  loadData();
}

/**
 * Delete a workspace after confirmation.
 */
async function confirmDeleteWorkspace(ws) {
  if (!ws) return;

  const result = await modal.showModal({
    title: 'Delete Workspace',
    content: html`
      <p style="color: var(--text-secondary); margin: 0 0 var(--space-3) 0;">
        Are you sure you want to delete the workspace <strong>${esc(ws.name)}</strong>?
      </p>
      <p style="color: var(--text-muted); font-size: var(--font-size-sm); margin: 0;">
        Path: <span style="font-family: var(--font-mono);">${esc(ws.path)}</span>
      </p>
      <p style="color: var(--text-muted); font-size: var(--font-size-sm); margin: var(--space-2) 0 0 0;">
        This does <strong>not</strong> delete any files on disk.
      </p>
    `.html,
    size: 'sm',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Delete', value: 'delete', variant: 'danger' },
    ],
  });

  if (result !== 'delete') return;

  // If this was the active workspace, clear the store reference
  if (_state.activeWorkspaceId === ws.id) {
    _state.activeWorkspaceId = null;
    saveActiveWorkspaceId(null);
    const store = getStore();
    if (store) {
      store.set('workspace.currentPath', null);
    }
  }

  removeWorkspace(ws.id);
  showToast('success', `Workspace "${ws.name}" deleted.`);

  // Re-render
  if (!_state.destroyed && _state.container) {
    renderPage(_state.container);
  }
}

/**
 * Show the create workspace modal and handle submission.
 */
async function openCreateWorkspaceModal() {
  const contentHtml = html`
    <div id="ws-create-form" style="display: flex; flex-direction: column; gap: var(--space-4);">
      <div>
        <label for="ws-create-name" style="display: block; font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin-bottom: var(--space-1);">
          Workspace Name <span style="color: var(--danger);">*</span>
        </label>
        <input type="text" id="ws-create-name" class="c-input" style="width: 100%;"
               placeholder="My Project" value="" />
      </div>
      <div>
        <label for="ws-create-path" style="display: block; font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin-bottom: var(--space-1);">
          Workspace Path <span style="color: var(--danger);">*</span>
        </label>
        <div style="display: flex; gap: var(--space-2);">
          <input type="text" id="ws-create-path" class="c-input" style="flex: 1; font-family: var(--font-mono);"
                 placeholder="/home/user/projects/my-project" value="" />
        </div>
        <div id="ws-create-path-feedback" style="font-size: var(--font-size-xs); margin-top: var(--space-1); color: var(--text-muted);"></div>
      </div>
      <div>
        <label for="ws-create-desc" style="display: block; font-size: var(--font-size-xs); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin-bottom: var(--space-1);">
          Description
        </label>
        <textarea id="ws-create-desc" class="c-input" style="width: 100%; min-height: 60px; resize: vertical;"
                  placeholder="Optional description of this workspace"></textarea>
      </div>
      <div id="ws-create-error" style="color: var(--danger); font-size: var(--font-size-sm); display: none;"></div>
    </div>
  `.html;

  const result = await modal.showModal({
    title: 'Create New Workspace',
    content: contentHtml,
    size: 'md',
    closeable: true,
    closeOnBackdrop: false,
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Create', value: 'create', variant: 'primary' },
    ],
  });

  if (result !== 'create') return;

  // Gather values
  const nameEl = document.getElementById('ws-create-name');
  const pathEl = document.getElementById('ws-create-path');
  const descEl = document.getElementById('ws-create-desc');
  const errorEl = document.getElementById('ws-create-error');
  const feedbackEl = document.getElementById('ws-create-path-feedback');

  if (!nameEl || !pathEl) return;

  const name = nameEl.value.trim();
  const path = pathEl.value.trim();
  const description = descEl ? descEl.value.trim() : '';

  // Validate
  if (!name) {
    if (errorEl) {
      errorEl.textContent = 'Workspace name is required.';
      errorEl.style.display = 'block';
    }
    return;
  }
  if (!path) {
    if (errorEl) {
      errorEl.textContent = 'Workspace path is required.';
      errorEl.style.display = 'block';
    }
    return;
  }

  // Validate path via API if available
  if (feedbackEl) {
    feedbackEl.textContent = 'Validating path…';
    feedbackEl.style.color = 'var(--text-muted)';
  }

  const api = getApi();
  if (api) {
    try {
      const res = await api.get('/api/v1/files/info', { path });
      const info = res?.data || res || {};
      // If we got a response, the path exists
      if (feedbackEl) {
        feedbackEl.textContent = 'Path exists.';
        feedbackEl.style.color = 'var(--success)';
      }
    } catch {
      // Path may not exist or API may be unavailable — warn but still allow
      if (feedbackEl) {
        feedbackEl.textContent = 'Could not verify path (API unavailable). Workspace will still be created.';
        feedbackEl.style.color = 'var(--warning)';
      }
    }
  }

  // Check for duplicate name
  const existing = _state.workspaces.find((w) => w.name === name);
  if (existing) {
    if (errorEl) {
      errorEl.textContent = `A workspace named "${name}" already exists.`;
      errorEl.style.display = 'block';
    }
    return;
  }

  // Create workspace
  const now = Date.now();
  const newWs = {
    id: generateId(),
    name,
    path,
    description,
    createdAt: now,
    lastOpened: now,
    recentFiles: [],
    openFiles: [],
  };

  addWorkspace(newWs);
  showToast('success', `Workspace "${name}" created.`);

  // Switch to it
  switchToWorkspace(newWs.id);
}

/* ── Helpers for dynamic sections ────────────────────────────────────────── */

function buildWorkspaceListHtml() {
  if (_state.workspaces.length === 0) {
    return html`<div style="text-align: center; padding: var(--space-4); color: var(--text-muted); font-size: var(--font-size-sm);">
      No workspaces yet. Click "New Workspace" to create one.
    </div>`.html;
  }

  return html.raw(_state.workspaces.map((ws) => {
    const isActive = ws.id === _state.activeWorkspaceId;
    const activeStyle = isActive
      ? 'background: var(--accent-muted, rgba(56,189,248,0.12)); border-left: 3px solid var(--accent);'
      : 'border-left: 3px solid transparent;';

    return html`
      <div style="display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-3);
                  border-radius: var(--radius-md); cursor: pointer; transition: background var(--transition-fast);
                  ${activeStyle}"
           data-action="switch-workspace" data-workspace-id="${esc(ws.id)}">
        <div style="width: 20px; height: 20px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--accent);">
          ${ICONS.folder}
        </div>
        <div style="flex: 1; min-width: 0;">
          <div style="font-size: var(--font-size-sm); color: var(--text-primary); font-weight: ${isActive ? 'var(--font-weight-bold)' : 'var(--font-weight-normal)'}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${esc(ws.name)}
          </div>
          <div style="font-size: var(--font-size-xxs); color: var(--text-muted); font-family: var(--font-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${esc(ws.path)}
            ${ws.lastOpened ? html.raw(` · ${esc(timeAgo(ws.lastOpened))}`) : ''}
          </div>
        </div>
        <button class="c-btn c-btn--sm c-btn--ghost" data-action="delete-workspace" data-workspace-id="${esc(ws.id)}"
                title="Delete workspace" style="flex-shrink: 0; color: var(--text-muted); padding: 2px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>
    `;
  }).join('')).html;
}

function buildRecentProjectsHtml() {
  // Recent projects = workspaces sorted by lastOpened, excluding active
  const recent = [..._state.workspaces]
    .filter((ws) => ws.id !== _state.activeWorkspaceId)
    .sort((a, b) => (b.lastOpened || 0) - (a.lastOpened || 0))
    .slice(0, MAX_RECENT_PROJECTS);

  if (recent.length === 0) {
    return '';
  }

  return html.raw(recent.map((ws) => html`
    <div style="display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-3);
                border-radius: var(--radius-md); cursor: pointer; transition: background var(--transition-fast);"
         data-action="switch-workspace" data-workspace-id="${esc(ws.id)}">
      <div style="width: 20px; height: 20px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">
        ${ICONS.folder}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(ws.name)}
        </div>
        <div style="font-size: var(--font-size-xxs); color: var(--text-muted); font-family: var(--font-mono);">
          ${esc(ws.path)}
          ${ws.lastOpened ? html.raw(` · ${esc(timeAgo(ws.lastOpened))}`) : ''}
        </div>
      </div>
    </div>
  `).join('')).html;
}

function buildOpenFilesHtml() {
  const ws = getActiveWorkspace();
  if (!ws || !ws.openFiles || ws.openFiles.length === 0) {
    return '';
  }

  return html.raw(ws.openFiles.map((file) => {
    const fileName = typeof file === 'string' ? file.split('/').pop() : (file.name || file.path?.split('/').pop() || 'unknown');
    const filePath = typeof file === 'string' ? file : (file.path || '');
    return html`
      <div style="display: flex; align-items: center; gap: var(--space-2); padding: var(--space-1) var(--space-2);
                  border-radius: var(--radius-sm); cursor: pointer; transition: background var(--transition-fast);"
           data-action="open-file" data-path="${esc(filePath)}">
        <div style="width: 16px; height: 16px; flex-shrink: 0; color: var(--text-muted); display: flex; align-items: center; justify-content: center;">
          ${ICONS.fileText}
        </div>
        <span style="font-size: var(--font-size-xs); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(fileName)}
        </span>
      </div>
    `;
  }).join('')).html;
}

function buildRecentFilesHtml() {
  if (_state.recentFiles.length === 0) {
    return html`<div style="text-align: center; padding: var(--space-4); color: var(--text-muted); font-size: var(--font-size-sm);">No recent files yet.</div>`.html;
  }
  return html.raw(_state.recentFiles.map((file) => html`
    <div style="display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-2);
                border-radius: var(--radius-md); cursor: pointer; transition: background var(--transition-fast);"
         data-action="open-file" data-path="${esc(file.path || file.name || '')}">
      <div style="width: 20px; height: 20px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--text-muted);">
        ${ICONS.fileText}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(file.name || file.path?.split('/').pop() || 'unknown')}
        </div>
        <div style="font-size: var(--font-size-xxs); color: var(--text-muted); font-family: var(--font-mono);">
          ${esc(file.path || '')}
        </div>
      </div>
      <span style="font-size: var(--font-size-xxs); color: var(--text-muted); flex-shrink: 0;">
        ${file.timestamp ? timeAgo(file.timestamp) : ''}
      </span>
    </div>
  `).join('')).html;
}

function buildBookmarksHtml() {
  if (_state.bookmarks.length === 0) {
    return html`<div style="text-align: center; padding: var(--space-4); color: var(--text-muted); font-size: var(--font-size-sm);">No bookmarks yet.</div>`.html;
  }
  return html.raw(_state.bookmarks.map((bm) => html`
    <div style="display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-2);
                border-radius: var(--radius-md); cursor: pointer; transition: background var(--transition-fast);"
         data-action="open-folder" data-path="${esc(bm.path || '')}">
      <div style="width: 20px; height: 20px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--warning);">
        ${ICONS.folder}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(bm.name || bm.path?.split('/').pop() || 'folder')}
        </div>
        <div style="font-size: var(--font-size-xxs); color: var(--text-muted); font-family: var(--font-mono);">
          ${esc(bm.path || '')}
        </div>
      </div>
    </div>
  `).join('')).html;
}

function buildActivityHtml() {
  if (_state.recentActivity.length === 0) {
    return html`<div style="text-align: center; padding: var(--space-6); color: var(--text-muted); font-size: var(--font-size-sm);">No recent activity.</div>`.html;
  }
  return html.raw(_state.recentActivity.map((act) => {
    const type = act.type || act.action_type || 'action';
    const label = (type.charAt(0).toUpperCase() + type.slice(1));
    const iconKey = {
      macro: 'play',
      command: 'bolt',
      chat: 'message',
      terminal: 'terminal',
      file: 'file',
      browser: 'globe',
      system: 'gear',
      agent: 'bot',
      recall: 'search',
    }[type] || 'activity';

    return html`
      <div style="display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-2) var(--space-2);
                  border-radius: var(--radius-md); transition: background var(--transition-fast);">
        <div style="width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: var(--text-muted);">
          ${ICONS[iconKey] || ICONS.activity}
        </div>
        <div style="flex: 1; min-width: 0;">
          <div style="font-size: var(--font-size-sm); color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${esc(act.name || act.action_name || label || 'Action')}
          </div>
          ${act.description ? html`
            <div style="font-size: var(--font-size-xs); color: var(--text-muted);">${esc(act.description)}</div>
          ` : ''}
          <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 1px;">
            ${act.timestamp ? timeAgo(act.timestamp) : ''}
          </div>
        </div>
        <span class="c-badge c-badge--default" style="font-size: 9px; padding: 0 6px; flex-shrink: 0;">
          ${esc(label)}
        </span>
      </div>
    `;
  }).join('')).html;
}

function buildHealthHtml() {
  // Dependencies
  const depSection = _state.depIssues.length === 0
    ? html`<div style="display: flex; align-items: center; gap: var(--space-1); color: var(--success); font-size: var(--font-size-sm);">
        <span>${ICONS['check-circle']}</span>
        <span>All dependencies satisfied</span>
      </div>`.html
    : html`<div style="display: flex; align-items: center; gap: var(--space-1); color: var(--warning); font-size: var(--font-size-sm);">
        <span>${ICONS.warning}</span>
        <span>${_state.depIssues.length} issue(s)</span>
      </div>
      <ul style="margin: var(--space-1) 0 0 0; padding-left: var(--space-4); font-size: var(--font-size-xs); color: var(--text-muted);">
        ${html.raw(_state.depIssues.map((issue) => html`<li>${esc(issue)}</li>`).join(''))}
      </ul>`.html;

  // Lint
  const lintSection = _state.lintIssues.length === 0
    ? html`<div style="display: flex; align-items: center; gap: var(--space-1); color: var(--text-muted); font-size: var(--font-size-sm);">
        <span>${ICONS.info}</span>
        <span>No lint data available</span>
      </div>`.html
    : html`<div style="display: flex; align-items: center; gap: var(--space-1); color: ${_state.lintIssues.length > 10 ? 'var(--danger)' : 'var(--warning)'}; font-size: var(--font-size-sm);">
        <span>${ICONS.warning}</span>
        <span>${_state.lintIssues.length} issue(s)</span>
      </div>`.html;

  return html`
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--space-3);">
      <div style="padding: var(--space-3); background: var(--bg-tertiary); border-radius: var(--radius-md);">
        <div style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-1);">Dependencies</div>
        ${html.raw(depSection)}
      </div>
      <div style="padding: var(--space-3); background: var(--bg-tertiary); border-radius: var(--radius-md);">
        <div style="font-size: var(--font-size-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-1);">Lint</div>
        ${html.raw(lintSection)}
      </div>
    </div>
  `.html;
}

/* ── Render ─────────────────────────────────────────────────────────────── */

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

  // Build dynamic HTML sections
  const workspaceListHtml = buildWorkspaceListHtml();
  const recentProjectsHtml = buildRecentProjectsHtml();
  const openFilesHtml = buildOpenFilesHtml();
  const recentFilesHtml = buildRecentFilesHtml();
  const bookmarksHtml = buildBookmarksHtml();
  const activityHtml = buildActivityHtml();
  const healthHtml = buildHealthHtml();

  const activeWs = getActiveWorkspace();

  const gitBoxStyle = _state.gitBranch
    ? 'background: var(--success-muted, rgba(34,197,94,0.15));'
    : 'background: var(--bg-tertiary);';
  const gitColorStyle = _state.gitBranch
    ? 'color: var(--success);'
    : 'color: var(--text-muted);';

  const data = {
    // Workspace management
    workspaceListHtml,
    recentProjectsHtml,
    openFilesHtml,
    hasActiveWorkspace: !!activeWs,
    activeWorkspaceName: activeWs ? esc(activeWs.name) : '',
    activeWorkspacePath: activeWs ? esc(activeWs.path) : '',
    activeWorkspaceDescription: activeWs ? esc(activeWs.description || '') : '',
    hasOpenFiles: activeWs && activeWs.openFiles && activeWs.openFiles.length > 0,
    openFileCount: activeWs ? (activeWs.openFiles?.length || 0) : 0,
    hasRecentProjects: recentProjectsHtml && recentProjectsHtml.length > 0,

    // Icons
    plusIcon: ICONS.plus?.html || ICONS['add-circle']?.html || ICONS.folder.html,
    trashIcon: ICONS.trash?.html || '',
    folderIcon: ICONS.folder.html,
    refreshIcon: ICONS.refresh.html,
    terminalIcon: ICONS.terminal.html,
    projectIcon: ICONS.folder.html,
    filesIcon: ICONS.fileText.html,
    activityIcon: ICONS.activity.html,
    fileTextIcon: ICONS.fileText.html,

    // Project info
    projectPath: esc(_state.projectPath || (activeWs ? activeWs.path : 'No project open')),
    projectName: esc(_state.projectName || (activeWs ? activeWs.name : 'Untitled')),
    projectDescription: esc(_state.projectDescription || (activeWs ? activeWs.description || '' : '')),
    fileCount: formatNumber(_state.fileCount),
    dirCount: formatNumber(_state.dirCount),
    linesOfCode: formatNumber(_state.linesOfCode),

    // Git info
    gitIcon: ICONS.activity.html,
    gitIconBoxStyle: gitBoxStyle,
    gitIconColor: gitColorStyle,
    gitBranch: esc(_state.gitBranch || ''),
    gitLastCommit: esc(_state.gitLastCommit || 'No commits'),
    gitLastAuthor: esc(_state.gitLastAuthor || ''),
    gitTimestamp: _state.gitLastTimestamp ? timeAgo(_state.gitLastTimestamp) : '',

    // Dynamic HTML sections
    recentFilesHtml,
    bookmarksHtml,
    activityHtml,
    healthHtml,
  };

  container.innerHTML = await loadTemplate('workspace', data);
  mountHandlers(container);
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div style="padding: var(--space-2);">
      ${skeletonHeading({ width: '200px' })}
      ${skeletonText({ width: '300px' })}
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); margin: var(--space-5) 0;">
        ${Array.from({ length: 3 }, () => skeletonCard({ height: '90px' }))}
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-5); margin-bottom: var(--space-5);">
        ${skeletonCard({ height: '280px' })}
        ${skeletonCard({ height: '280px' })}
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
      <div class="empty-state__title">Failed to Load Workspace</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to load workspace data from the backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="ws-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#ws-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    _state.errorMessage = '';
    renderSkeletons(container);
    loadData();
  });
}

/* ── Event Handlers ─────────────────────────────────────────────────────── */

function mountHandlers(container) {
  // ── Create workspace ──
  container.querySelector('#ws-create-btn')?.addEventListener('click', () => {
    openCreateWorkspaceModal();
  });

  // ── Switch workspace ──
  container.querySelectorAll('[data-action="switch-workspace"]').forEach((el) => {
    el.addEventListener('click', () => {
      const wsId = el.dataset.workspaceId;
      if (wsId) {
        switchToWorkspace(wsId);
      }
    });
  });

  // ── Delete workspace (from list item) ──
  container.querySelectorAll('[data-action="delete-workspace"]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const wsId = el.dataset.workspaceId;
      const ws = _state.workspaces.find((w) => w.id === wsId);
      if (ws) {
        confirmDeleteWorkspace(ws);
      }
    });
  });

  // ── Delete active workspace ──
  container.querySelector('#ws-delete-active')?.addEventListener('click', () => {
    const ws = getActiveWorkspace();
    if (ws) {
      confirmDeleteWorkspace(ws);
    }
  });

  // ── Open in Files ──
  container.querySelector('#ws-open-in-files')?.addEventListener('click', () => {
    const ws = getActiveWorkspace();
    if (ws && ws.path) {
      window.fiona?.router?.navigate(`/files?path=${encodeURIComponent(ws.path)}`);
    } else {
      showToast('info', 'No workspace path configured.');
    }
  });

  // ── Terminal Here ──
  container.querySelector('#ws-open-terminal-here')?.addEventListener('click', () => {
    const ws = getActiveWorkspace();
    if (ws && ws.path) {
      const store = getStore();
      if (store) {
        store.set('terminal.cwd', ws.path);
      }
      window.fiona?.router?.navigate('/terminal');
    } else {
      showToast('info', 'No workspace path configured.');
    }
  });

  // Open in file explorer (system)
  container.querySelector('#ws-open-explorer')?.addEventListener('click', () => {
    const api = getApi();
    const path = _state.projectPath || (getActiveWorkspace()?.path);
    if (api && path) {
      api.post('/api/v1/files/open', { path }).catch((err) => {
        console.warn('[workspace] Failed to open explorer:', err);
        showToast('error', 'Failed to open file explorer.');
      });
    } else {
      showToast('info', 'No project path configured.');
    }
  });

  // Refresh
  container.querySelector('#ws-refresh')?.addEventListener('click', loadData);

  // Open file manager page
  container.querySelector('#ws-open-file-manager')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/files');
  });

  // Open file
  container.querySelectorAll('[data-action="open-file"]').forEach((el) => {
    el.addEventListener('click', () => {
      const path = el.dataset.path;
      if (path) {
        window.fiona?.router?.navigate(`/files?path=${encodeURIComponent(path)}`);
      }
    });
  });

  // Open folder in file explorer page
  container.querySelectorAll('[data-action="open-folder"]').forEach((el) => {
    el.addEventListener('click', () => {
      const path = el.dataset.path;
      if (path) {
        window.fiona?.router?.navigate(`/files?path=${encodeURIComponent(path)}`);
      }
    });
  });

  // Quick actions
  container.querySelector('[data-action="open-terminal"]')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/terminal');
  });
  container.querySelector('[data-action="open-explorer-page"]')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/files');
  });
  container.querySelector('[data-action="run-diagnostics"]')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/diagnostics');
  });
  container.querySelector('[data-action="view-logs"]')?.addEventListener('click', () => {
    window.fiona?.router?.navigate('/logs');
  });
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadData() {
  if (_state.destroyed) return;
  const api = getApi();

  _state.loading = true;
  if (_state.container) renderSkeletons(_state.container);

  try {
    // ── 1. Load workspaces from localStorage ──
    _state.workspaces = loadWorkspaces();
    _state.activeWorkspaceId = loadActiveWorkspaceId();

    // Validate active workspace still exists
    if (_state.activeWorkspaceId) {
      const exists = _state.workspaces.find((ws) => ws.id === _state.activeWorkspaceId);
      if (!exists) {
        _state.activeWorkspaceId = null;
        saveActiveWorkspaceId(null);
      }
    }

    // Get the active workspace
    const activeWs = getActiveWorkspace();

    // ── 2. Sync active workspace to store ──
    const store = getStore();
    if (store && activeWs) {
      store.set('workspace.currentPath', activeWs.path);
      store.set('workspace.recentFiles', activeWs.recentFiles || []);
      store.set('workspace.openFiles', activeWs.openFiles || []);
    } else if (store) {
      store.set('workspace.currentPath', null);
    }

    // ── 3. Set project info from active workspace ──
    if (activeWs) {
      _state.projectPath = activeWs.path;
      _state.projectName = activeWs.name;
      _state.projectDescription = activeWs.description || '';
    }

    // ── 4. Try to load file info from API ──
    let fileInfo = {};
    if (api && activeWs && activeWs.path) {
      try {
        const res = await api.get('/api/v1/files/info', { path: activeWs.path });
        fileInfo = res?.data || res || {};
      } catch { /* fallback to workspace data */ }
    }

    if (fileInfo.project_name || fileInfo.name) {
      _state.projectName = fileInfo.project_name || fileInfo.name || _state.projectName;
    }
    if (fileInfo.description) {
      _state.projectDescription = fileInfo.description || _state.projectDescription;
    }
    _state.fileCount = fileInfo.file_count ?? _state.fileCount;
    _state.dirCount = fileInfo.dir_count ?? _state.dirCount;
    _state.linesOfCode = fileInfo.lines_of_code ?? fileInfo.loc ?? _state.linesOfCode;

    // ── 5. Load git info ──
    if (api) {
      try {
        const gitRes = await api.get('/api/v1/system/git-info');
        const git = gitRes?.data || gitRes || {};
        _state.gitBranch = git.branch || git.current_branch || '';
        _state.gitLastCommit = git.last_commit || git.commit?.message || '';
        _state.gitLastAuthor = git.last_author || git.commit?.author || '';
        _state.gitLastTimestamp = git.last_timestamp || git.commit?.timestamp || null;
      } catch {
        _state.gitBranch = '';
        _state.gitLastCommit = '';
        _state.gitLastAuthor = '';
        _state.gitLastTimestamp = null;
      }
    }

    // ── 6. Load recent files ──
    _state.recentFiles = [];
    if (api) {
      try {
        const filesRes = await api.get('/api/v1/files/recent', { limit: MAX_RECENT_FILES });
        const files = filesRes?.data || filesRes || [];
        _state.recentFiles = Array.isArray(files) ? files.slice(0, MAX_RECENT_FILES) : [];
      } catch { /* fallback empty */ }
    }

    // If no API recent files but workspace has recent files, use those
    if (_state.recentFiles.length === 0 && activeWs && activeWs.recentFiles) {
      _state.recentFiles = activeWs.recentFiles.slice(0, MAX_RECENT_FILES);
    }

    // ── 7. Load bookmarks from localStorage ──
    try {
      const stored = localStorage.getItem('fiona_workspace_bookmarks');
      _state.bookmarks = stored ? JSON.parse(stored) : [];
    } catch {
      _state.bookmarks = [];
    }

    // ── 8. Load recent activity ──
    _state.recentActivity = [];
    if (api) {
      try {
        const actRes = await api.get('/api/v1/actions/history', { limit: MAX_ACTIVITY_ITEMS });
        const acts = actRes?.data || actRes || [];
        _state.recentActivity = Array.isArray(acts) ? acts.slice(0, MAX_ACTIVITY_ITEMS) : [];
      } catch { /* fallback empty */ }
    }

    // ── 9. Load dep/lint status ──
    if (api) {
      try {
        const healthRes = await api.get('/api/v1/project/health');
        const health = healthRes?.data || healthRes || {};
        _state.depIssues = health.dependency_issues || health.dep_issues || [];
        _state.lintIssues = health.lint_issues || [];
      } catch {
        _state.depIssues = [];
        _state.lintIssues = [];
      }
    }

    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  } catch (err) {
    console.error('[workspace] Failed to load data:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to load workspace data.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      await renderPage(_state.container);
    }
  }
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

/* ── Lifecycle ──────────────────────────────────────────────────────────── */

export function render(container) {
  _state.destroyed = false;
  _state.loading = true;
  _state.error = false;
  _state.errorMessage = '';
  _state.container = container;

  renderSkeletons(container);
  loadData();
}

export async function mount(container) {
  if (container && !_state.container) {
    _state.container = container;
  }
  if (!_state.loading && _state.container) {
    await renderPage(_state.container);
  }
}

export function destroy() {
  _state.destroyed = true;
  _state.container = null;
  _state.workspaces = [];
  _state.activeWorkspaceId = null;
  _state.recentFiles = [];
  _state.recentActivity = [];
  _state.bookmarks = [];
  _state.depIssues = [];
  _state.lintIssues = [];
}

/* ── Router-compatible default export ───────────────────────────────────── */

export default function createPage(_routeInfo) {
  return {
    render() {
      return '<div id="ws-root"></div>';
    },
    mount(container) {
      const root = container.querySelector('#ws-root') || container;
      render(root);
    },
    destroy,
  };
}
