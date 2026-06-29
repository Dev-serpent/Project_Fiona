/* ==========================================================================
   desktop.js — SeeOnDesk (Desktop Awareness) Page
   ==========================================================================
   Displays the current active window, desktop snapshot, running processes,
   installed applications, virtual workspaces, and system resource usage.
   Active window auto-refreshes every 2 seconds; other tabs load on demand.
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { createDataTable } from '../js/components/DataTable.js';
import {
  skeletonCard,
  skeletonText,
  skeletonHeading,
} from '../js/components/LoadingSkeleton.js';
import { loadTemplate } from '../js/template-loader.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const ACTIVE_POLL_INTERVAL = 2000;

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,

  // Active window state
  activeLoading: true,
  activeError: false,
  activeErrorMessage: '',
  activeData: null,
  autoRefresh: false,
  pollTimer: null,

  // Snapshot state
  snapshotLoading: true,
  snapshotError: false,
  snapshotErrorMessage: '',
  snapshotData: null,

  // Tab state
  activeTab: 'active-window',

  // Processes tab state
  processesLoading: false,
  processesError: false,
  processesErrorMessage: '',
  processesData: null,
  processesTable: null,
  processesAutoRefresh: false,
  processesPollTimer: null,
  processFilterValue: '',

  // Applications tab state
  applicationsLoading: false,
  applicationsError: false,
  applicationsErrorMessage: '',
  applicationsData: null,
  applicationsFilterValue: '',

  // Workspaces tab state
  workspacesLoading: false,
  workspacesError: false,
  workspacesErrorMessage: '',
  workspacesData: null,

  // Resources tab state
  resourcesLoading: false,
  resourcesError: false,
  resourcesErrorMessage: '',
  resourcesData: null,
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

function timeAgo(timestamp) {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;
  const sec = Math.floor(diff / 1000);
  if (sec < 5) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const idx = Math.min(i, units.length - 1);
  return `${(bytes / Math.pow(1024, idx)).toFixed(1)} ${units[idx]}`;
}

/* ── HTML Renderers ─────────────────────────────────────────────────────── */

async function renderPage(container) {
  if (_state.destroyed) return;
  _state.container = container;

  const data = {
    activeColumnContent: renderActiveWindowCard(),
    snapshotColumnContent: renderSnapshotCard(),
  };

  container.innerHTML = await loadTemplate('desktop', data);
  mountComponents(container);
}

/* ── Active Window Card ─────────────────────────────────────────────────── */

function renderActiveWindowCard() {
  if (_state.activeLoading) {
    return renderActiveSkeleton();
  }

  if (_state.activeError) {
    return renderActiveError();
  }

  const _data = _state.activeData || {};

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.eye}
            </span>
            Active Window
          </span>
        </span>
        <div style="display: flex; align-items: center; gap: var(--space-3);">
          <label style="display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--text-muted); cursor: pointer; user-select: none;">
            <input type="checkbox" id="desktop-auto-refresh" ${_state.autoRefresh ? 'checked' : ''}
                   style="accent-color: var(--accent);">
            Auto-refresh
          </label>
          <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-active-refresh-btn" title="Refresh active window">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body">
        <div style="display: grid; grid-template-columns: auto 1fr; gap: var(--space-2) var(--space-4); font-size: var(--font-size-sm);">
          <div style="color: var(--text-muted); white-space: nowrap;">Window Title</div>
          <div style="color: var(--text-primary); font-weight: var(--font-weight-medium); word-break: break-word;">
            ${_data.title ? esc(_data.title) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>

          <div style="color: var(--text-muted); white-space: nowrap;">Application</div>
          <div style="color: var(--text-primary); display: flex; align-items: center; gap: var(--space-2);">
            <span style="width: 16px; height: 16px; display: inline-flex; align-items: center; justify-content: center; color: var(--text-muted); flex-shrink: 0;">
              ${ICONS.puzzle}
            </span>
            ${_data.app_name ? esc(_data.app_name) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>

          <div style="color: var(--text-muted); white-space: nowrap;">Window ID</div>
          <div style="color: var(--text-primary); font-family: var(--font-mono); font-size: var(--font-size-xs);">
            ${_data.window_id ? esc(_data.window_id) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>

          <div style="color: var(--text-muted); white-space: nowrap;">Geometry</div>
          <div style="color: var(--text-primary); font-family: var(--font-mono); font-size: var(--font-size-xs);">
            ${_data.geometry ? renderGeometry(_data.geometry) : html`<span style="color: var(--text-muted); font-style: italic;">—</span>`}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderGeometry(geom) {
  if (typeof geom === 'object' && geom !== null) {
    const x = geom.x ?? geom.left ?? '?';
    const y = geom.y ?? geom.top ?? '?';
    const w = geom.width ?? geom.w ?? '?';
    const h = geom.height ?? geom.h ?? '?';
    return html`x: ${esc(String(x))}, y: ${esc(String(y))} · ${esc(String(w))}×${esc(String(h))}`;
  }
  if (typeof geom === 'string') {
    return esc(geom);
  }
  return html`<span style="color: var(--text-muted); font-style: italic;">—</span>`;
}

function renderActiveSkeleton() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="width: 18px; height: 18px;"></span>
            Active Window
          </span>
        </span>
      </div>
      <div class="c-card__body">
        <div style="display: flex; flex-direction: column; gap: var(--space-3);">
          ${skeletonText({ lines: 4 })}
        </div>
      </div>
    </div>
  `;
}

function renderActiveError() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--danger); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.eye}
            </span>
            Active Window
          </span>
        </span>
        <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-active-refresh-btn" title="Retry">
          <span class="c-btn__icon">${ICONS.refresh}</span>
        </button>
      </div>
      <div class="c-card__body">
        <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
          <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
            ${esc(_state.activeErrorMessage || 'Failed to fetch active window.')}
          </span>
        </div>
      </div>
    </div>
  `;
}

/* ── Desktop Snapshot Card ──────────────────────────────────────────────── */

function renderSnapshotCard() {
  if (_state.snapshotLoading) {
    return renderSnapshotSkeleton();
  }

  if (_state.snapshotError) {
    return renderSnapshotError();
  }

  const _data = _state.snapshotData || {};
  const windows = Array.isArray(_data.windows) ? _data.windows : [];
  const focusedWindowId = _data.focused_window || null;
  const timestamp = _data.timestamp || null;

  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.maximize}
            </span>
            Desktop Snapshot
          </span>
        </span>
        <div style="display: flex; align-items: center; gap: var(--space-3);">
          ${timestamp ? html`
            <span style="font-size: var(--font-size-xs); color: var(--text-muted); display: flex; align-items: center; gap: 4px;">
              <span style="width: 12px; height: 12px; display: inline-flex; align-items: center; justify-content: center;">${ICONS.clock}</span>
              ${timeAgo(timestamp)}
            </span>
          ` : ''}
          <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-snapshot-refresh-btn" title="Refresh snapshot">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body" style="padding: var(--space-2);">
        ${windows.length === 0 ? renderSnapshotEmpty() : html`
          <div style="display: flex; flex-direction: column; gap: 1px; max-height: 420px; overflow-y: auto;">
            ${html.raw(windows.map((win) => renderWindowItem(win, focusedWindowId)).join(''))}
          </div>
        `}
      </div>
    </div>
  `;
}

function renderWindowItem(win, focusedWindowId) {
  const isFocused = win.window_id && focusedWindowId && String(win.window_id) === String(focusedWindowId);
  const geom = win.geometry;

  return html`
    <div style="display: flex; gap: var(--space-3); padding: var(--space-2) var(--space-3);
                border-left: ${isFocused ? '3px solid var(--accent)' : '3px solid transparent'};
                background: ${isFocused ? 'var(--accent-muted)' : 'transparent'};
                border-radius: var(--radius-sm);
                transition: background var(--transition-fast);">
      <div style="width: 20px; height: 20px; display: flex; align-items: center; justify-content: center;
                  flex-shrink: 0; color: var(--text-muted); margin-top: 1px;">
        ${ICONS.puzzle}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="display: flex; align-items: center; gap: var(--space-2);">
          <span style="font-size: var(--font-size-sm); font-weight: ${isFocused ? 'var(--font-weight-semibold)' : 'var(--font-weight-medium)'};
                       color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${win.title ? esc(win.title) : html`<span style="color: var(--text-muted); font-style: italic;">Untitled</span>`}
          </span>
          ${isFocused ? html`
            <span class="c-badge c-badge--accent" style="font-size: 9px; padding: 0 6px; flex-shrink: 0; line-height: 16px;">Focused</span>
          ` : ''}
        </div>
        <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 1px; display: flex; align-items: center; gap: var(--space-2);">
          <span>${win.app_name ? esc(win.app_name) : '—'}</span>
          ${geom ? html`
            <span>·</span>
            <span style="font-family: var(--font-mono); font-size: var(--font-size-xxs);">
              ${renderGeometryInline(geom)}
            </span>
          ` : ''}
        </div>
      </div>
    </div>
  `;
}

function renderGeometryInline(geom) {
  if (typeof geom === 'object' && geom !== null) {
    const x = geom.x ?? geom.left ?? '?';
    const y = geom.y ?? geom.top ?? '?';
    const w = geom.width ?? geom.w ?? '?';
    const h = geom.height ?? geom.h ?? '?';
    return `${esc(String(x))},${esc(String(y))} ${esc(String(w))}×${esc(String(h))}`;
  }
  if (typeof geom === 'string') {
    return esc(geom);
  }
  return '';
}

function renderSnapshotEmpty() {
  return html`
    <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-8) var(--space-4); text-align: center;">
      <span style="color: var(--text-muted); width: 40px; height: 40px;">${ICONS.maximize}</span>
      <div style="font-size: var(--font-size-sm); color: var(--text-muted);">
        No windows detected.
      </div>
      <div style="font-size: var(--font-size-xs); color: var(--text-muted);">
        The snapshot returned an empty window list.
      </div>
    </div>
  `;
}

function renderSnapshotSkeleton() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="width: 18px; height: 18px;"></span>
            Desktop Snapshot
          </span>
        </span>
      </div>
      <div class="c-card__body" style="padding: var(--space-2);">
        <div style="display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-2);">
          ${Array.from({ length: 4 }, () => skeletonText({ width: '90%' }))}
        </div>
      </div>
    </div>
  `;
}

function renderSnapshotError() {
  return html`
    <div class="c-card">
      <div class="c-card__header">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="width: 18px; height: 18px;"></span>
            Desktop Snapshot
          </span>
        </span>
        <button class="c-btn c-btn--sm c-btn--ghost" id="desktop-snapshot-refresh-btn" title="Retry">
          <span class="c-btn__icon">${ICONS.refresh}</span>
        </button>
      </div>
      <div class="c-card__body">
        <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
          <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
            ${esc(_state.snapshotErrorMessage || 'Failed to fetch desktop snapshot.')}
          </span>
        </div>
      </div>
    </div>
  `;
}

/* ── Processes Tab ──────────────────────────────────────────────────────── */

function renderProcessesTabContent() {
  const container = document.getElementById('desktop-processes-tab');
  if (!container) return;

  container.innerHTML = html`
    <div class="c-card">
      <div class="c-card__header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--space-2);">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.puzzle}
            </span>
            Running Processes
          </span>
        </span>
        <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
          <input type="text" id="process-filter-input" placeholder="Filter processes..."
                 value="${esc(_state.processFilterValue)}"
                 style="padding: 4px 8px; border: 1px solid var(--border); border-radius: var(--radius-sm);
                        font-size: var(--font-size-sm); background: var(--bg-primary); color: var(--text-primary);
                        min-width: 160px;">
          <label style="display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs);
                        color: var(--text-muted); cursor: pointer; user-select: none; white-space: nowrap;">
            <input type="checkbox" id="process-auto-refresh" ${_state.processesAutoRefresh ? 'checked' : ''}
                   style="accent-color: var(--accent);">
            Auto-refresh
          </label>
          <button class="c-btn c-btn--sm c-btn--ghost" id="processes-refresh-btn" title="Refresh processes">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body">
        <div id="processes-table-container"></div>
      </div>
    </div>
  `;

  // Bind filter events
  const filterInput = container.querySelector('#process-filter-input');
  if (filterInput) {
    filterInput.addEventListener('input', (e) => {
      _state.processFilterValue = e.target.value;
      applyProcessFilter();
    });
  }

  // Bind refresh
  container.querySelectorAll('#processes-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadProcesses());
  });

  // Bind auto-refresh toggle
  const autoToggle = container.querySelector('#process-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', (e) => {
      _state.processesAutoRefresh = e.target.checked;
      if (_state.processesAutoRefresh) {
        startProcessesPolling();
      } else {
        stopProcessesPolling();
      }
    });
  }

  // Render the table (or skeleton/error)
  renderProcessesTable();
}

function renderProcessesTable() {
  const container = document.getElementById('processes-table-container');
  if (!container) return;

  if (_state.processesLoading) {
    container.innerHTML = skeletonText({ lines: 8 });
    return;
  }

  if (_state.processesError) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
        <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
          ${esc(_state.processesErrorMessage || 'Failed to fetch processes.')}
        </span>
      </div>
    `;
    return;
  }

  const data = _state.processesData;
  if (!data || !Array.isArray(data) || data.length === 0) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="font-size: var(--font-size-sm); color: var(--text-muted);">No process data available.</span>
      </div>
    `;
    return;
  }

  // Filter data
  let filtered = data;
  if (_state.processFilterValue) {
    const q = _state.processFilterValue.toLowerCase();
    filtered = data.filter((p) =>
      String(p.pid).includes(q) ||
      (p.name || '').toLowerCase().includes(q) ||
      (p.status || '').toLowerCase().includes(q)
    );
  }

  const columns = [
    { key: 'pid', label: 'PID', sortable: true, filterable: false, width: '80px' },
    { key: 'name', label: 'Name', sortable: true, filterable: true },
    {
      key: 'cpu_percent',
      label: 'CPU%',
      sortable: true,
      filterable: false,
      width: '80px',
      render: (val) => {
        const v = typeof val === 'number' ? val : 0;
        return `<span style="font-family: var(--font-mono); font-size: var(--font-size-xs);">${v.toFixed(1)}%</span>`;
      },
    },
    {
      key: 'memory_percent',
      label: 'Mem%',
      sortable: true,
      filterable: false,
      width: '80px',
      render: (val) => {
        const v = typeof val === 'number' ? val : 0;
        return `<span style="font-family: var(--font-mono); font-size: var(--font-size-xs);">${v.toFixed(1)}%</span>`;
      },
    },
    {
      key: 'memory_rss',
      label: 'Memory (RSS)',
      sortable: true,
      filterable: false,
      width: '120px',
      render: (val) => {
        const v = typeof val === 'number' ? val : 0;
        return `<span style="font-family: var(--font-mono); font-size: var(--font-size-xs);">${formatBytes(v * 1024)}</span>`;
      },
    },
    { key: 'status', label: 'Status', sortable: true, filterable: true, width: '100px' },
  ];

  // Destroy previous table if exists
  if (_state.processesTable) {
    _state.processesTable.destroy();
    _state.processesTable = null;
  }

  _state.processesTable = createDataTable(container, columns, filtered, {
    pageSize: 50,
    defaultSortKey: 'cpu_percent',
    defaultSortDir: 'desc',
  });
}

function applyProcessFilter() {
  renderProcessesTable();
}

/* ── Applications Tab ───────────────────────────────────────────────────── */

function renderApplicationsTabContent() {
  const container = document.getElementById('desktop-applications-tab');
  if (!container) return;

  container.innerHTML = html`
    <div class="c-card">
      <div class="c-card__header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--space-2);">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.puzzle}
            </span>
            Installed Applications
          </span>
        </span>
        <div style="display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;">
          <input type="text" id="applications-filter-input" placeholder="Search apps..."
                 value="${esc(_state.applicationsFilterValue)}"
                 style="padding: 4px 8px; border: 1px solid var(--border); border-radius: var(--radius-sm);
                        font-size: var(--font-size-sm); background: var(--bg-primary); color: var(--text-primary);
                        min-width: 160px;">
          <button class="c-btn c-btn--sm c-btn--ghost" id="applications-refresh-btn" title="Refresh applications">
            <span class="c-btn__icon">${ICONS.refresh}</span>
          </button>
        </div>
      </div>
      <div class="c-card__body">
        <div id="applications-grid-container"></div>
      </div>
    </div>
  `;

  // Bind filter
  const filterInput = container.querySelector('#applications-filter-input');
  if (filterInput) {
    filterInput.addEventListener('input', (e) => {
      _state.applicationsFilterValue = e.target.value;
      renderApplicationsGrid();
    });
  }

  // Bind refresh
  container.querySelectorAll('#applications-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadApplications());
  });

  renderApplicationsGrid();
}

function renderApplicationsGrid() {
  const container = document.getElementById('applications-grid-container');
  if (!container) return;

  if (_state.applicationsLoading) {
    container.innerHTML = html`
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--space-2);">
        ${Array.from({ length: 6 }, () => skeletonText({ width: '100%' }))}
      </div>
    `;
    return;
  }

  if (_state.applicationsError) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
        <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
          ${esc(_state.applicationsErrorMessage || 'Failed to fetch applications.')}
        </span>
      </div>
    `;
    return;
  }

  const data = _state.applicationsData;
  if (!data || !Array.isArray(data) || data.length === 0) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="font-size: var(--font-size-sm); color: var(--text-muted);">No applications found.</span>
      </div>
    `;
    return;
  }

  // Filter
  let filtered = data;
  if (_state.applicationsFilterValue) {
    const q = _state.applicationsFilterValue.toLowerCase();
    filtered = data.filter((a) =>
      (a.name || '').toLowerCase().includes(q) ||
      (a.comment || '').toLowerCase().includes(q) ||
      (a.categories || '').toLowerCase().includes(q)
    );
  }

  if (filtered.length === 0) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="font-size: var(--font-size-sm); color: var(--text-muted);">No applications match your filter.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = html`
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--space-2);">
      ${html.raw(filtered.map((app) => renderAppCard(app)).join(''))}
    </div>
  `;

  // Bind click handlers for launch
  container.querySelectorAll('.app-launch-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const execCmd = e.currentTarget.dataset.exec;
      if (execCmd) {
        launchApp(execCmd);
      }
    });
  });
}

function renderAppCard(app) {
  const iconName = app.icon || '';
  const iconHtml = iconName
    ? `<img src="/api/v1/files/icon?name=${esc(iconName)}" alt="" style="width: 32px; height: 32px; object-fit: contain;"
           onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
       <span style="display: none; width: 32px; height: 32px; align-items: center; justify-content: center;
                    color: var(--text-muted); font-size: 16px;">${ICONS.puzzle}</span>`
    : `<span style="width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
                 color: var(--text-muted);">${ICONS.puzzle}</span>`;

  const categories = app.categories || '';
  const comment = app.comment || '';

  return `
    <div style="display: flex; gap: var(--space-3); padding: var(--space-3);
                border: 1px solid var(--border); border-radius: var(--radius-md);
                background: var(--bg-primary); transition: box-shadow var(--transition-fast);
                align-items: flex-start;">
      <div style="flex-shrink: 0;">
        ${iconHtml}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold);
                    color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          ${esc(app.name)}
        </div>
        ${comment ? html`
          <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 2px;
                      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
            ${esc(comment)}
          </div>
        ` : ''}
        ${categories ? html`
          <div style="font-size: var(--font-size-xxs); color: var(--text-muted); margin-top: 4px;">
            ${esc(categories)}
          </div>
        ` : ''}
        <button class="c-btn c-btn--sm c-btn--accent app-launch-btn"
                data-exec="${esc(app.exec)}"
                style="margin-top: var(--space-2);"
                title="Launch ${esc(app.name)}">
          <span class="c-btn__icon">${ICONS.play}</span>
          Launch
        </button>
      </div>
    </div>
  `;
}

/* ── Workspaces Tab ─────────────────────────────────────────────────────── */

function renderWorkspacesTabContent() {
  const container = document.getElementById('desktop-workspaces-tab');
  if (!container) return;

  container.innerHTML = html`
    <div class="c-card">
      <div class="c-card__header" style="display: flex; justify-content: space-between; align-items: center;">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.maximize}
            </span>
            Virtual Desktops
          </span>
        </span>
        <button class="c-btn c-btn--sm c-btn--ghost" id="workspaces-refresh-btn" title="Refresh workspaces">
          <span class="c-btn__icon">${ICONS.refresh}</span>
        </button>
      </div>
      <div class="c-card__body">
        <div id="workspaces-list-container"></div>
      </div>
    </div>
  `;

  container.querySelectorAll('#workspaces-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadWorkspaces());
  });

  renderWorkspacesList();
}

function renderWorkspacesList() {
  const container = document.getElementById('workspaces-list-container');
  if (!container) return;

  if (_state.workspacesLoading) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; gap: var(--space-2);">
        ${skeletonText({ lines: 3 })}
      </div>
    `;
    return;
  }

  if (_state.workspacesError) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
        <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
          ${esc(_state.workspacesErrorMessage || 'Failed to fetch workspaces.')}
        </span>
      </div>
    `;
    return;
  }

  const data = _state.workspacesData;
  if (!data || !Array.isArray(data) || data.length === 0) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="font-size: var(--font-size-sm); color: var(--text-muted);">No workspaces detected.</span>
        <span style="font-size: var(--font-size-xs); color: var(--text-muted);">
          Your desktop environment may not support virtual desktops, or the required tools are not installed.
        </span>
      </div>
    `;
    return;
  }

  container.innerHTML = html`
    <div style="display: flex; flex-direction: column; gap: var(--space-2);">
      ${html.raw(data.map((ws) => renderWorkspaceItem(ws)).join(''))}
    </div>
  `;
}

function renderWorkspaceItem(ws) {
  const isActive = ws.is_active;

  return html`
    <div style="display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4);
                border: 1px solid ${isActive ? 'var(--accent)' : 'var(--border)'};
                border-radius: var(--radius-md);
                background: ${isActive ? 'var(--accent-muted)' : 'var(--bg-primary)'};
                transition: background var(--transition-fast);">
      <div style="width: 12px; height: 12px; border-radius: 50%;
                  background: ${isActive ? 'var(--accent)' : 'var(--text-muted)'};
                  opacity: ${isActive ? '1' : '0.3'};
                  flex-shrink: 0;"></div>
      <div style="flex: 1;">
        <div style="font-size: var(--font-size-sm); font-weight: ${isActive ? 'var(--font-weight-semibold)' : 'var(--font-weight-medium)'};
                    color: var(--text-primary);">
          ${esc(ws.name || `Workspace ${ws.id}`)}
        </div>
        <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 2px;">
          ID: ${esc(ws.id)} · ${typeof ws.window_count === 'number' ? `${ws.window_count} window${ws.window_count !== 1 ? 's' : ''}` : '—'}
        </div>
      </div>
      ${isActive ? html`
        <span class="c-badge c-badge--accent" style="flex-shrink: 0;">Active</span>
      ` : ''}
    </div>
  `;
}

/* ── System Resources Tab ───────────────────────────────────────────────── */

function renderResourcesTabContent() {
  const container = document.getElementById('desktop-resources-tab');
  if (!container) return;

  container.innerHTML = html`
    <div class="c-card">
      <div class="c-card__header" style="display: flex; justify-content: space-between; align-items: center;">
        <span class="c-card__title">
          <span style="display: inline-flex; align-items: center; gap: var(--space-2);">
            <span style="color: var(--accent); width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;">
              ${ICONS.activity}
            </span>
            System Resources
          </span>
        </span>
        <button class="c-btn c-btn--sm c-btn--ghost" id="resources-refresh-btn" title="Refresh resources">
          <span class="c-btn__icon">${ICONS.refresh}</span>
        </button>
      </div>
      <div class="c-card__body">
        <div id="resources-content-container"></div>
      </div>
    </div>
  `;

  container.querySelectorAll('#resources-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadResources());
  });

  renderResourcesContent();
}

function renderResourcesContent() {
  const container = document.getElementById('resources-content-container');
  if (!container) return;

  if (_state.resourcesLoading) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; gap: var(--space-4);">
        ${skeletonCard()}
      </div>
    `;
    return;
  }

  if (_state.resourcesError) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="color: var(--danger); width: 32px; height: 32px;">${ICONS.error}</span>
        <span style="font-size: var(--font-size-sm); color: var(--text-muted); text-align: center;">
          ${esc(_state.resourcesErrorMessage || 'Failed to fetch system resources.')}
        </span>
      </div>
    `;
    return;
  }

  const data = _state.resourcesData;
  if (!data) {
    container.innerHTML = html`
      <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-4) 0;">
        <span style="font-size: var(--font-size-sm); color: var(--text-muted);">No resource data available.</span>
      </div>
    `;
    return;
  }

  const cpu = data.cpu || {};
  const memory = data.memory || {};
  const disk = data.disk || {};

  const cpuPercent = typeof cpu.percent === 'number' ? cpu.percent : 0;
  const cpuCount = cpu.count || 0;
  const loadavg = Array.isArray(cpu.loadavg) ? cpu.loadavg : [];
  const memPercent = typeof memory.percent_used === 'number' ? memory.percent_used : 0;
  const memTotal = memory.total_gb || 0;
  const memUsed = memory.used_gb || 0;
  const diskPercent = typeof disk.percent_used === 'number' ? disk.percent_used : 0;
  const diskTotal = disk.total_gb || 0;
  const diskUsed = disk.used_gb || 0;

  container.innerHTML = html`
    <div style="display: flex; flex-direction: column; gap: var(--space-4);">
      <!-- CPU -->
      <div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2);">
          <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary);">
            CPU
          </span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted); font-family: var(--font-mono);">
            ${cpuPercent.toFixed(1)}%
          </span>
        </div>
        ${renderProgressBar(cpuPercent, 0, 100, cpuPercent > 80 ? 'var(--danger)' : cpuPercent > 50 ? 'var(--warning)' : 'var(--accent)')}
        <div style="display: flex; gap: var(--space-4); margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-muted);">
          <span>${cpuCount} core${cpuCount !== 1 ? 's' : ''}</span>
          ${loadavg.length > 0 ? html`
            <span>Load: ${loadavg.join(', ')}</span>
          ` : ''}
        </div>
      </div>

      <!-- Memory -->
      <div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2);">
          <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary);">
            Memory
          </span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted); font-family: var(--font-mono);">
            ${memUsed.toFixed(1)} GB / ${memTotal.toFixed(1)} GB (${memPercent.toFixed(1)}%)
          </span>
        </div>
        ${renderProgressBar(memPercent, 0, 100, memPercent > 80 ? 'var(--danger)' : memPercent > 50 ? 'var(--warning)' : 'var(--accent)')}
      </div>

      <!-- Disk -->
      <div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2);">
          <span style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary);">
            Disk
          </span>
          <span style="font-size: var(--font-size-sm); color: var(--text-muted); font-family: var(--font-mono);">
            ${diskUsed.toFixed(1)} GB / ${diskTotal.toFixed(1)} GB (${diskPercent.toFixed(1)}%)
          </span>
        </div>
        ${renderProgressBar(diskPercent, 0, 100, diskPercent > 80 ? 'var(--danger)' : diskPercent > 50 ? 'var(--warning)' : 'var(--accent)')}
      </div>
    </div>
  `;
}

function renderProgressBar(value, min, max, color) {
  const pct = max > min ? Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100)) : 0;
  return html`
    <div style="width: 100%; height: 8px; background: var(--bg-secondary); border-radius: 4px; overflow: hidden;">
      <div style="width: ${pct.toFixed(1)}%; height: 100%; background: ${color};
                  border-radius: 4px; transition: width 0.3s ease;"></div>
    </div>
  `;
}

/* ── Tab Management ─────────────────────────────────────────────────────── */

function switchTab(tabId) {
  if (_state.destroyed) return;
  _state.activeTab = tabId;

  // Update tab bar
  const tabsContainer = document.getElementById('desktop-tabs');
  if (tabsContainer) {
    tabsContainer.querySelectorAll('[data-desktop-tab]').forEach((tab) => {
      const isActive = tab.dataset.desktopTab === tabId;
      tab.classList.toggle('c-tab--active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
  }

  // Show/hide panels
  document.querySelectorAll('.desktop-panel').forEach((panel) => {
    panel.style.display = panel.dataset.desktopPanel === tabId ? 'block' : 'none';
  });

  // Load tab content on first activation
  switch (tabId) {
    case 'processes':
      if (!_state.processesData && !_state.processesLoading) {
        renderProcessesTabContent();
        loadProcesses();
      } else {
        renderProcessesTabContent();
      }
      break;
    case 'applications':
      if (!_state.applicationsData && !_state.applicationsLoading) {
        renderApplicationsTabContent();
        loadApplications();
      } else {
        renderApplicationsTabContent();
      }
      break;
    case 'workspaces':
      if (!_state.workspacesData && !_state.workspacesLoading) {
        renderWorkspacesTabContent();
        loadWorkspaces();
      } else {
        renderWorkspacesTabContent();
      }
      break;
    case 'resources':
      if (!_state.resourcesData && !_state.resourcesLoading) {
        renderResourcesTabContent();
        loadResources();
      } else {
        renderResourcesTabContent();
      }
      break;
  }
}

/* ── Component Mounting ─────────────────────────────────────────────────── */

function mountComponents(container) {
  // Tab switching
  container.querySelectorAll('[data-desktop-tab]').forEach((tab) => {
    tab.addEventListener('click', () => {
      switchTab(tab.dataset.desktopTab);
    });
  });

  // Active window refresh button (both normal and retry states use same id)
  container.querySelectorAll('#desktop-active-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadActiveWindow());
  });

  // Auto-refresh toggle
  const autoToggle = container.querySelector('#desktop-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', (e) => {
      _state.autoRefresh = e.target.checked;
      if (_state.autoRefresh) {
        startPolling();
      } else {
        stopPolling();
      }
    });
  }

  // Snapshot refresh button
  container.querySelectorAll('#desktop-snapshot-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadSnapshot());
  });
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadActiveWindow() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.activeError = true;
    _state.activeErrorMessage = 'API client not available.';
    _state.activeLoading = false;
    reRenderActiveColumn();
    return;
  }

  try {
    const result = await api.get('/api/v1/desktop/active');
    if (_state.destroyed) return;

    _state.activeData = result?.data || result;
    _state.activeError = false;
    _state.activeErrorMessage = '';
    _state.activeLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch active window:', err);
    _state.activeError = true;
    _state.activeErrorMessage = err.message || 'Failed to fetch active window.';
    _state.activeLoading = false;
  }

  if (!_state.destroyed) {
    reRenderActiveColumn();
  }
}

async function loadSnapshot() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.snapshotError = true;
    _state.snapshotErrorMessage = 'API client not available.';
    _state.snapshotLoading = false;
    reRenderSnapshotColumn();
    return;
  }

  try {
    const result = await api.get('/api/v1/desktop/snapshot');
    if (_state.destroyed) return;

    _state.snapshotData = result?.data || result;
    _state.snapshotError = false;
    _state.snapshotErrorMessage = '';
    _state.snapshotLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch snapshot:', err);
    _state.snapshotError = true;
    _state.snapshotErrorMessage = err.message || 'Failed to fetch desktop snapshot.';
    _state.snapshotLoading = false;
  }

  if (!_state.destroyed) {
    reRenderSnapshotColumn();
  }
}

async function loadProcesses() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.processesError = true;
    _state.processesErrorMessage = 'API client not available.';
    _state.processesLoading = false;
    renderProcessesTable();
    return;
  }

  _state.processesLoading = true;
  renderProcessesTable();

  try {
    const result = await api.get('/api/v1/desktop/processes');
    if (_state.destroyed) return;

    _state.processesData = result?.data || result;
    _state.processesError = false;
    _state.processesErrorMessage = '';
    _state.processesLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch processes:', err);
    _state.processesError = true;
    _state.processesErrorMessage = err.message || 'Failed to fetch processes.';
    _state.processesLoading = false;
  }

  if (!_state.destroyed) {
    renderProcessesTable();
  }
}

async function loadApplications() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.applicationsError = true;
    _state.applicationsErrorMessage = 'API client not available.';
    _state.applicationsLoading = false;
    renderApplicationsGrid();
    return;
  }

  _state.applicationsLoading = true;
  renderApplicationsGrid();

  try {
    const result = await api.get('/api/v1/desktop/applications');
    if (_state.destroyed) return;

    _state.applicationsData = result?.data || result;
    _state.applicationsError = false;
    _state.applicationsErrorMessage = '';
    _state.applicationsLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch applications:', err);
    _state.applicationsError = true;
    _state.applicationsErrorMessage = err.message || 'Failed to fetch applications.';
    _state.applicationsLoading = false;
  }

  if (!_state.destroyed) {
    renderApplicationsGrid();
  }
}

async function loadWorkspaces() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.workspacesError = true;
    _state.workspacesErrorMessage = 'API client not available.';
    _state.workspacesLoading = false;
    renderWorkspacesList();
    return;
  }

  _state.workspacesLoading = true;
  renderWorkspacesList();

  try {
    const result = await api.get('/api/v1/desktop/workspaces');
    if (_state.destroyed) return;

    _state.workspacesData = result?.data || result;
    _state.workspacesError = false;
    _state.workspacesErrorMessage = '';
    _state.workspacesLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch workspaces:', err);
    _state.workspacesError = true;
    _state.workspacesErrorMessage = err.message || 'Failed to fetch workspaces.';
    _state.workspacesLoading = false;
  }

  if (!_state.destroyed) {
    renderWorkspacesList();
  }
}

async function loadResources() {
  if (_state.destroyed) return;
  const api = getApi();
  if (!api) {
    _state.resourcesError = true;
    _state.resourcesErrorMessage = 'API client not available.';
    _state.resourcesLoading = false;
    renderResourcesContent();
    return;
  }

  _state.resourcesLoading = true;
  renderResourcesContent();

  try {
    const result = await api.get('/api/v1/desktop/system-resources');
    if (_state.destroyed) return;

    _state.resourcesData = result?.data || result;
    _state.resourcesError = false;
    _state.resourcesErrorMessage = '';
    _state.resourcesLoading = false;
  } catch (err) {
    console.error('[desktop] Failed to fetch system resources:', err);
    _state.resourcesError = true;
    _state.resourcesErrorMessage = err.message || 'Failed to fetch system resources.';
    _state.resourcesLoading = false;
  }

  if (!_state.destroyed) {
    renderResourcesContent();
  }
}

async function launchApp(execCmd) {
  if (!execCmd) return;
  const api = getApi();
  if (!api) return;

  try {
    await api.post('/api/v1/desktop/launch', { exec: execCmd });
  } catch (err) {
    console.error('[desktop] Failed to launch app:', err);
  }
}

/* ── Re-render helpers ──────────────────────────────────────────────────── */

function reRenderActiveColumn() {
  const col = _state.container?.querySelector('#desktop-active-column');
  if (!col) return;
  col.innerHTML = renderActiveWindowCard();
  // Re-bind active column events
  col.querySelectorAll('#desktop-active-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadActiveWindow());
  });
  const autoToggle = col.querySelector('#desktop-auto-refresh');
  if (autoToggle) {
    autoToggle.addEventListener('change', (e) => {
      _state.autoRefresh = e.target.checked;
      if (_state.autoRefresh) {
        startPolling();
      } else {
        stopPolling();
      }
    });
  }
}

function reRenderSnapshotColumn() {
  const col = _state.container?.querySelector('#desktop-snapshot-column');
  if (!col) return;
  col.innerHTML = renderSnapshotCard();
  // Re-bind snapshot refresh
  col.querySelectorAll('#desktop-snapshot-refresh-btn').forEach((btn) => {
    btn.addEventListener('click', () => loadSnapshot());
  });
}

/* ── Polling ─────────────────────────────────────────────────────────────── */

function startPolling() {
  stopPolling();
  _state.pollTimer = setInterval(silentActivePoll, ACTIVE_POLL_INTERVAL);
}

function stopPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
}

async function silentActivePoll() {
  if (_state.destroyed || !_state.autoRefresh) return;
  const api = getApi();
  if (!api) return;

  try {
    const result = await api.get('/api/v1/desktop/active');
    if (_state.destroyed || !_state.autoRefresh) return;

    _state.activeData = result?.data || result;
    _state.activeError = false;
    _state.activeErrorMessage = '';
    _state.activeLoading = false;

    reRenderActiveColumn();
  } catch (err) {
    // Silently fail on poll — don't show error state, keep last valid data
    if (!_state.activeData) {
      _state.activeError = true;
      _state.activeErrorMessage = err.message || 'Poll failed.';
      reRenderActiveColumn();
    }
  }
}

/* ── Processes Polling ──────────────────────────────────────────────────── */

function startProcessesPolling() {
  stopProcessesPolling();
  _state.processesPollTimer = setInterval(silentProcessesPoll, 5000);
}

function stopProcessesPolling() {
  if (_state.processesPollTimer) {
    clearInterval(_state.processesPollTimer);
    _state.processesPollTimer = null;
  }
}

async function silentProcessesPoll() {
  if (_state.destroyed || !_state.processesAutoRefresh) return;
  const api = getApi();
  if (!api) return;

  try {
    const result = await api.get('/api/v1/desktop/processes');
    if (_state.destroyed || !_state.processesAutoRefresh) return;

    _state.processesData = result?.data || result;
    _state.processesError = false;
    _state.processesErrorMessage = '';
    _state.processesLoading = false;

    renderProcessesTable();
  } catch (err) {
    // Silently fail on poll
    if (!_state.processesData) {
      _state.processesError = true;
      _state.processesErrorMessage = err.message || 'Poll failed.';
      renderProcessesTable();
    }
  }
}

/* ── Lifecycle ───────────────────────────────────────────────────────────── */

/**
 * Full render — called from outside the router or from mount().
 * @param {Element} container
 */
export async function render(container) {
  _state.destroyed = false;
  _state.activeLoading = true;
  _state.activeError = false;
  _state.activeErrorMessage = '';
  _state.snapshotLoading = true;
  _state.snapshotError = false;
  _state.snapshotErrorMessage = '';
  _state.activeTab = 'active-window';
  _state.processesLoading = false;
  _state.processesError = false;
  _state.processesErrorMessage = '';
  _state.processesData = null;
  _state.processesAutoRefresh = false;
  _state.processFilterValue = '';
  if (_state.processesTable) {
    _state.processesTable.destroy();
    _state.processesTable = null;
  }
  _state.applicationsLoading = false;
  _state.applicationsError = false;
  _state.applicationsErrorMessage = '';
  _state.applicationsData = null;
  _state.applicationsFilterValue = '';
  _state.workspacesLoading = false;
  _state.workspacesError = false;
  _state.workspacesErrorMessage = '';
  _state.workspacesData = null;
  _state.resourcesLoading = false;
  _state.resourcesError = false;
  _state.resourcesErrorMessage = '';
  _state.resourcesData = null;
  _state.container = container;

  // Render skeleton layout immediately
  const data = {
    activeColumnContent: renderActiveSkeleton(),
    snapshotColumnContent: renderSnapshotSkeleton(),
  };
  container.innerHTML = await loadTemplate('desktop', data);

  // Fetch both in parallel
  Promise.all([loadActiveWindow(), loadSnapshot()]);
}

/**
 * Re-mount (re-attach events) without full re-render.
 * Called by the router after the HTML is already in the DOM.
 * @param {Element} container
 */
export function mount(container) {
  _state.container = container;
  mountComponents(container);
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;
  stopPolling();
  stopProcessesPolling();
  if (_state.processesTable) {
    _state.processesTable.destroy();
    _state.processesTable = null;
  }
  _state.container = null;
  _state.activeData = null;
  _state.snapshotData = null;
  _state.processesData = null;
  _state.applicationsData = null;
  _state.workspacesData = null;
  _state.resourcesData = null;
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
      return '<div id="desktop-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#desktop-root') || container;
      await renderPage(root);
    },
    destroy,
  };
}
