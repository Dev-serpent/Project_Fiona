/* ==========================================================================
   workspace.js — Project Workspace Overview Page
   ==========================================================================
   Displays project info, file stats, git status, recent files, quick
   actions, recent activity, and project health for the current Fiona
   workspace.
   
   Exports: { render(container), mount(container), destroy() }
   Default export: factory for the SPA router.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
  skeletonCircle,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const MAX_RECENT_FILES = 10;
const MAX_ACTIVITY_ITEMS = 10;

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

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

/* ── Helpers for dynamic sections ────────────────────────────────────────── */

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

  // Build raw HTML sections
  const recentFilesHtml = buildRecentFilesHtml();
  const bookmarksHtml = buildBookmarksHtml();
  const activityHtml = buildActivityHtml();
  const healthHtml = buildHealthHtml();

  const gitBoxStyle = _state.gitBranch
    ? 'background: var(--success-muted, rgba(34,197,94,0.15));'
    : 'background: var(--bg-tertiary);';
  const gitColorStyle = _state.gitBranch
    ? 'color: var(--success);'
    : 'color: var(--text-muted);';

  const data = {
    projectPath: esc(_state.projectPath || 'No project open'),
    folderIcon: ICONS.folder.html,
    refreshIcon: ICONS.refresh.html,
    projectIcon: ICONS.folder.html,
    projectName: esc(_state.projectName || 'Untitled'),
    projectDescription: esc(_state.projectDescription || ''),
    filesIcon: ICONS.fileText.html,
    fileCount: formatNumber(_state.fileCount),
    dirCount: formatNumber(_state.dirCount),
    linesOfCode: formatNumber(_state.linesOfCode),
    gitIcon: ICONS.activity.html,
    gitIconBoxStyle: gitBoxStyle,
    gitIconColor: gitColorStyle,
    gitBranch: esc(_state.gitBranch || ''),
    gitLastCommit: esc(_state.gitLastCommit || 'No commits'),
    gitLastAuthor: esc(_state.gitLastAuthor || ''),
    gitTimestamp: _state.gitLastTimestamp ? timeAgo(_state.gitLastTimestamp) : '',
    terminalIcon: ICONS.terminal.html,
    activityIcon: ICONS.activity.html,
    fileTextIcon: ICONS.fileText.html,
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
  // Open in file explorer (system)
  container.querySelector('#ws-open-explorer')?.addEventListener('click', () => {
    const api = getApi();
    if (api && _state.projectPath) {
      api.post('/api/v1/files/open', { path: _state.projectPath }).catch((err) => {
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
    // Try to get project path from store or API
    const store = window.fiona?.store;
    _state.projectPath = store?.get?.('workspace.path') || '';

    // Load file info
    let fileInfo = {};
    if (api && _state.projectPath) {
      try {
        const res = await api.get('/api/v1/files/info', { path: _state.projectPath });
        fileInfo = res?.data || res || {};
      } catch { /* fallback to defaults */ }
    }

    _state.projectName = fileInfo.project_name || fileInfo.name || _state.projectPath?.split('/').pop() || 'Fiona Project';
    _state.projectDescription = fileInfo.description || '';
    _state.fileCount = fileInfo.file_count ?? 0;
    _state.dirCount = fileInfo.dir_count ?? 0;
    _state.linesOfCode = fileInfo.lines_of_code ?? fileInfo.loc ?? 0;

    // Load git info
    if (api) {
      try {
        const gitRes = await api.get('/api/v1/system/git-info');
        const git = gitRes?.data || gitRes || {};
        _state.gitBranch = git.branch || git.current_branch || '';
        _state.gitLastCommit = git.last_commit || git.commit?.message || '';
        _state.gitLastAuthor = git.last_author || git.commit?.author || '';
        _state.gitLastTimestamp = git.last_timestamp || git.commit?.timestamp || null;
      } catch {
        // Git info may not be available
        _state.gitBranch = '';
        _state.gitLastCommit = '';
        _state.gitLastAuthor = '';
        _state.gitLastTimestamp = null;
      }
    }

    // Load recent files
    _state.recentFiles = [];
    if (api) {
      try {
        const filesRes = await api.get('/api/v1/files/recent', { limit: MAX_RECENT_FILES });
        const files = filesRes?.data || filesRes || [];
        _state.recentFiles = Array.isArray(files) ? files.slice(0, MAX_RECENT_FILES) : [];
      } catch { /* fallback empty */ }
    }

    // Load bookmarks from localStorage
    try {
      const stored = localStorage.getItem('fiona_workspace_bookmarks');
      _state.bookmarks = stored ? JSON.parse(stored) : [];
    } catch {
      _state.bookmarks = [];
    }

    // Load recent activity
    _state.recentActivity = [];
    if (api) {
      try {
        const actRes = await api.get('/api/v1/actions/history', { limit: MAX_ACTIVITY_ITEMS });
        const acts = actRes?.data || actRes || [];
        _state.recentActivity = Array.isArray(acts) ? acts.slice(0, MAX_ACTIVITY_ITEMS) : [];
      } catch { /* fallback empty */ }
    }

    // Load dep/lint status (future — may not exist yet)
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
