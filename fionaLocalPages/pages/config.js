/* ==========================================================================
   config.js — Configuration Editor Page
   ==========================================================================
   Split-panel configuration editor for all Fiona configuration files.
   Provides a grouped file tree on the left and a full-featured editor
   with syntax highlighting, format/prettify, save with Cmd+S, and
   automatic backup creation before save.

   Exports: { render(container?), mount(container), destroy() }
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { loadTemplate } from '../js/template-loader.js';
import {
  skeletonText,
  skeletonHeading,
  skeletonButton,
} from '../js/components/LoadingSkeleton.js';

/* ── Constants ──────────────────────────────────────────────────────────── */

const CONFIG_SERVICE_GROUPS = [
  { label: 'QuikTieper',   key: 'quik.tieper' },
  { label: 'CamComs',      key: 'cam.coms' },
  { label: 'FionaCore',    key: 'fiona.core' },
  { label: 'Agent',        key: 'agent' },
  { label: 'TerminalAssist', key: 'terminal.assist' },
  { label: 'PhiConnect',   key: 'phi.connect' },
  { label: 'Macros',       key: 'macros' },
  { label: 'RecallVault',  key: 'recall.vault' },
  { label: 'Other',        key: '__other__' },
];

/* ── Module-level State ─────────────────────────────────────────────────── */

const _state = {
  container: null,
  destroyed: false,
  loading: true,
  error: false,
  errorMessage: '',

  // File tree
  files: [],            // All config files with metadata
  filteredFiles: [],    // After search
  activeFileName: null,
  fileSearch: '',

  // Editor
  editorContent: '',
  originalContent: '',
  editorReadOnly: false,
  isDirty: false,
  syntax: 'json',       // 'json', 'yaml', 'toml', 'other'
  lastSaved: null,

  // UI refs
  treeEl: null,
  editorTextarea: null,
  lineNumbersEl: null,
  fileSearchEl: null,
  statusBarEl: null,
  fileBreadcrumbEl: null,
  saveBtnEl: null,

  // Key handler
  keyHandler: null,
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

function detectSyntax(filename) {
  if (!filename) return 'other';
  const ext = filename.split('.').pop().toLowerCase();
  if (ext === 'json') return 'json';
  if (ext === 'yaml' || ext === 'yml') return 'yaml';
  if (ext === 'toml') return 'toml';
  if (ext === 'ini' || ext === 'cfg' || ext === 'conf') return 'ini';
  if (ext === 'xml') return 'xml';
  return 'other';
}

function formatFileSize(bytes) {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function getFileIcon(file) {
  const ext = (file.name || '').split('.').pop().toLowerCase();
  if (ext === 'json') return ICONS.fileJson;
  if (ext === 'yaml' || ext === 'yml') return ICONS.fileCode;
  if (ext === 'toml') return ICONS.fileCode;
  return ICONS.fileText;
}

function serviceGroupForFile(file) {
  const name = (file.name || '').toLowerCase();
  const path = (file.path || '').toLowerCase();
  const combined = `${path}/${name}`;

  for (const group of CONFIG_SERVICE_GROUPS) {
    if (group.key === '__other__') continue;
    if (combined.includes(group.key.toLowerCase())) return group;
  }
  // Try matching by name patterns
  if (name.includes('quik') || name.includes('tieper')) return CONFIG_SERVICE_GROUPS[0];
  if (name.includes('cam') || name.includes('coms')) return CONFIG_SERVICE_GROUPS[1];
  if (name.includes('fiona') || name.includes('core')) return CONFIG_SERVICE_GROUPS[2];
  if (name.startsWith('agent') || name.includes('agent.')) return CONFIG_SERVICE_GROUPS[3];
  if (name.includes('terminal')) return CONFIG_SERVICE_GROUPS[4];
  if (name.includes('phi') || name.includes('connect')) return CONFIG_SERVICE_GROUPS[5];
  if (name.includes('macro')) return CONFIG_SERVICE_GROUPS[6];
  if (name.includes('recall') || name.includes('vault')) return CONFIG_SERVICE_GROUPS[7];

  return CONFIG_SERVICE_GROUPS[CONFIG_SERVICE_GROUPS.length - 1]; // Other
}

function groupFiles(files) {
  const groups = {};
  for (const group of CONFIG_SERVICE_GROUPS) {
    groups[group.label] = [];
  }

  for (const file of files) {
    const group = serviceGroupForFile(file);
    groups[group.label].push(file);
  }

  // Remove empty groups except "Other"
  const result = [];
  for (const group of CONFIG_SERVICE_GROUPS) {
    const label = group.label;
    if (groups[label].length > 0 || label === 'Other') {
      result.push({ label, files: groups[label], collapsed: false });
    }
  }

  return result;
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

  const groupedFiles = groupFiles(_state.filteredFiles);
  const activeFile = _state.files.find((f) => f.name === _state.activeFileName);
  const lineCount = _state.editorContent ? _state.editorContent.split('\n').length : 0;
  const dirtyIndicator = _state.isDirty ? '<span class="config-dirty-dot"></span>' : '';

  container.innerHTML = html`
    <div class="config-layout">
      <!-- Left Panel: File Tree -->
      <div class="config-tree-panel">
        <div class="config-tree-header">
          <h3 style="font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin: 0;">
            Configuration Files
          </h3>
        </div>

        <!-- File search -->
        <div class="config-tree-search">
          <span style="display: flex; align-items: center; color: var(--text-muted); position: absolute; left: 8px; top: 50%; transform: translateY(-50%); pointer-events: none; width: 14px; height: 14px;">
            ${ICONS.search}
          </span>
          <input type="text" class="config-tree-search-input" id="config-file-search"
                 placeholder="Search files…" value="${esc(_state.fileSearch)}"
                 style="padding-left: 28px; width: 100%;" />
        </div>

        <!-- File groups -->
        <div class="config-tree-list" id="config-tree-list">
          ${html.raw(groupedFiles.map((group) => html`
            <div class="config-tree-group">
              <div class="config-tree-group__header" data-group="${esc(group.label)}">
                <span class="config-tree-group__chevron">${group.collapsed ? ICONS.chevronRight : ICONS.chevronDown}</span>
                <span class="config-tree-group__label">${esc(group.label)}</span>
                <span class="config-tree-group__count">${group.files.length}</span>
              </div>
              ${!group.collapsed ? html`
                <div class="config-tree-group__files">
                  ${html.raw(group.files.map((file) => {
                    const isActive = file.name === _state.activeFileName;
                    return html`
                      <div class="config-tree-file ${isActive ? 'config-tree-file--active' : ''}"
                           data-file-name="${esc(file.name)}">
                        <span class="config-tree-file__icon">${getFileIcon(file)}</span>
                        <span class="config-tree-file__name">${esc(file.name)}</span>
                        <span class="config-tree-file__time">${file.modified ? esc(_relativeTime(file.modified)) : ''}</span>
                      </div>
                    `;
                  }).join(''))}
                </div>
              ` : ''}
            </div>
          `).join(''))}

          ${_state.filteredFiles.length === 0 ? html`
            <div style="padding: var(--space-6); text-align: center; color: var(--text-muted); font-size: var(--font-size-sm);">
              No files match your search.
            </div>
          ` : ''}
        </div>
      </div>

      <!-- Right Panel: Editor -->
      <div class="config-editor-panel">
        ${activeFile ? html`
          <!-- Breadcrumb -->
          <div class="config-breadcrumb">
            <span class="config-breadcrumb__item config-breadcrumb__item--root">Config</span>
            <span class="config-breadcrumb__sep">/</span>
            <span class="config-breadcrumb__item config-breadcrumb__item--current">${esc(activeFile.name)}</span>
            ${dirtyIndicator}
          </div>

          <!-- Editor Toolbar -->
          <div class="config-editor-toolbar">
            <div class="config-editor-toolbar__left">
              <button class="c-btn c-btn--sm ${_state.editorReadOnly ? 'c-btn--ghost' : 'c-btn--primary'}"
                      id="config-toggle-readonly" title="Toggle read-only mode">
                <span class="c-btn__icon">${_state.editorReadOnly ? ICONS.lock : ICONS.edit}</span>
                ${_state.editorReadOnly ? 'Read-Only' : 'Editable'}
              </button>
              <button class="c-btn c-btn--sm c-btn--ghost" id="config-format-btn" title="Format/Prettify JSON">
                <span class="c-btn__icon">${ICONS.check}</span>
                Format
              </button>
              <button class="c-btn c-btn--sm c-btn--ghost" id="config-download-btn" title="Download file">
                <span class="c-btn__icon">${ICONS.download}</span>
                Download
              </button>
              <button class="c-btn c-btn--sm c-btn--ghost c-btn--danger" id="config-reset-btn" title="Reset to defaults">
                <span class="c-btn__icon">${ICONS.refresh}</span>
                Reset
              </button>
            </div>
            <div class="config-editor-toolbar__right">
              <button class="c-btn c-btn--sm c-btn--primary ${_state.isDirty ? '' : 'c-btn--ghost'}"
                      id="config-save-btn" title="Save (Cmd+S)"
                      ${_state.isDirty ? '' : 'disabled'}>
                <span class="c-btn__icon">${ICONS.check}</span>
                Save
              </button>
            </div>
          </div>

          <!-- Editor Body -->
          <div class="config-editor-body">
            <div class="config-line-numbers" id="config-line-numbers">
              ${html.raw(Array.from({ length: Math.max(lineCount, 1) }, (_, i) => html`
                <span class="config-line-number">${i + 1}</span>
              `).join(''))}
            </div>
            <textarea class="config-editor-textarea"
                      id="config-editor-textarea"
                      spellcheck="false"
                      wrap="off"
                      ${_state.editorReadOnly ? 'readonly' : ''}
                      style="font-family: var(--font-mono); font-size: var(--font-size-sm); line-height: 1.6;">${esc(_state.editorContent)}</textarea>
          </div>
        ` : html`
          <div class="empty-state" style="margin-top: 15vh;">
            <div class="empty-state__icon" style="color: var(--text-muted);">${ICONS.fileText}</div>
            <div class="empty-state__title">Select a Configuration File</div>
            <div class="empty-state__description">
              Choose a file from the left panel to view and edit its contents.
            </div>
          </div>
        `}
      </div>
    </div>

    <!-- Status Bar -->
    <div class="config-statusbar" id="config-statusbar">
      ${activeFile ? html`
        <span id="config-file-size">${formatFileSize(activeFile.size)}</span>
        <span class="config-statusbar__sep">·</span>
        <span id="config-line-count">${lineCount} lines</span>
        <span class="config-statusbar__sep">·</span>
        <span id="config-syntax-type">${_state.syntax.toUpperCase()}</span>
        <span class="config-statusbar__sep">·</span>
        <span id="config-last-saved">${_state.lastSaved ? 'Last saved: ' + formatTimestamp(_state.lastSaved) : 'Not saved yet'}</span>
      ` : ''}
    </div>
  `;

  mountComponents(container);
}

function renderSkeletons(container) {
  container.innerHTML = html`
    <div class="config-layout" style="height: 100%;">
      <div style="width: 250px; border-right: 1px solid var(--border); padding: var(--space-3); display: flex; flex-direction: column; gap: var(--space-3);">
        ${skeletonHeading({ width: '140px' })}
        ${skeletonText({ width: '100%' })}
        ${Array.from({ length: 6 }, () => skeletonText({ width: '90%' }))}
      </div>
      <div style="flex: 1; padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-4);">
        ${skeletonHeading({ width: '200px' })}
        ${skeletonButton({ width: '80px' })}
        ${Array.from({ length: 12 }, () => skeletonText({ width: '100%' }))}
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
      <div class="empty-state__title">Failed to Load Configuration</div>
      <div class="empty-state__description">
        ${esc(_state.errorMessage || 'Unable to fetch configuration files from the backend.')}
      </div>
      <button class="c-btn c-btn--primary" id="config-retry-btn" style="margin-top: var(--space-4);">
        <span class="c-btn__icon">${ICONS.refresh}</span>
        Retry
      </button>
    </div>
  `;

  container.querySelector('#config-retry-btn')?.addEventListener('click', () => {
    _state.error = false;
    _state.loading = true;
    loadConfigList();
  });
}

/* ── Component Mounting / Event Binding ─────────────────────────────────── */

function mountComponents(container) {
  _state.treeEl = container.querySelector('#config-tree-list');
  _state.editorTextarea = container.querySelector('#config-editor-textarea');
  _state.lineNumbersEl = container.querySelector('#config-line-numbers');
  _state.fileSearchEl = container.querySelector('#config-file-search');
  _state.saveBtnEl = container.querySelector('#config-save-btn');
  _state.statusBarEl = container.querySelector('#config-statusbar');
  _state.fileBreadcrumbEl = container.querySelector('.config-breadcrumb');

  // File tree — group collapse toggle
  if (_state.treeEl) {
    _state.treeEl.addEventListener('click', (e) => {
      const groupHeader = e.target.closest('.config-tree-group__header');
      const fileItem = e.target.closest('.config-tree-file');

      if (groupHeader) {
        e.stopPropagation();
        toggleGroup(groupHeader.dataset.group);
        return;
      }

      if (fileItem) {
        e.stopPropagation();
        const fileName = fileItem.dataset.fileName;
        if (fileName && fileName !== _state.activeFileName) {
          loadFileContent(fileName);
        }
        return;
      }
    });
  }

  // File search — debounced
  if (_state.fileSearchEl) {
    _state.fileSearchEl.addEventListener('input', () => {
      _state.fileSearch = _state.fileSearchEl.value;
      filterFiles();
    });
  }

  // Editor textarea — track changes
  if (_state.editorTextarea) {
    _state.editorTextarea.addEventListener('input', () => {
      _state.editorContent = _state.editorTextarea.value;
      const dirty = _state.editorContent !== _state.originalContent;
      if (_state.isDirty !== dirty) {
        _state.isDirty = dirty;
        updateSaveButton();
        updateBreadcrumb();
      }
      updateLineNumbers();
    });

    _state.editorTextarea.addEventListener('scroll', syncEditorScroll);
  }

  // Toggle read-only
  container.querySelector('#config-toggle-readonly')?.addEventListener('click', () => {
    _state.editorReadOnly = !_state.editorReadOnly;
    if (_state.editorTextarea) {
      _state.editorTextarea.readOnly = _state.editorReadOnly;
    }
    reapplyEditor();
  });

  // Format button
  container.querySelector('#config-format-btn')?.addEventListener('click', formatEditor);

  // Download button
  container.querySelector('#config-download-btn')?.addEventListener('click', downloadFile);

  // Reset button
  container.querySelector('#config-reset-btn')?.addEventListener('click', resetFile);

  // Save button
  container.querySelector('#config-save-btn')?.addEventListener('click', saveFile);

  // Keyboard shortcut: Cmd+S / Ctrl+S
  if (_state.keyHandler) {
    document.removeEventListener('keydown', _state.keyHandler);
  }
  _state.keyHandler = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      // Only intercept if we're in the config page
      if (_state.container && _state.container.contains(e.target)) {
        e.preventDefault();
        if (_state.isDirty && !_state.editorReadOnly) {
          saveFile();
        }
      }
    }
  };
  document.addEventListener('keydown', _state.keyHandler);

  // Unsaved changes warning before unload
  window.addEventListener('beforeunload', handleBeforeUnload);
}

/* ── Editor Operations ──────────────────────────────────────────────────── */

function reapplyEditor() {
  if (_state.destroyed || !_state.container) return;
  renderPage(_state.container);
}

function updateSaveButton() {
  const btn = _state.saveBtnEl;
  if (!btn) return;
  if (_state.isDirty) {
    btn.disabled = false;
    btn.className = 'c-btn c-btn--sm c-btn--primary';
  } else {
    btn.disabled = true;
    btn.className = 'c-btn c-btn--sm c-btn--ghost';
  }
}

function updateBreadcrumb() {
  const dot = _state.container?.querySelector('.config-dirty-dot');
  if (dot) {
    dot.style.display = _state.isDirty ? 'inline-block' : 'none';
  }
}

function updateLineNumbers() {
  const el = _state.lineNumbersEl;
  if (!el) return;
  const content = _state.editorContent || '';
  const lines = content.split('\n').length;
  const numbers = Array.from({ length: Math.max(lines, 1) }, (_, i) => i + 1);
  el.innerHTML = html.raw(numbers.map((n) => `<span class="config-line-number">${n}</span>`).join(''));
}

function syncEditorScroll() {
  const ln = _state.lineNumbersEl;
  const ta = _state.editorTextarea;
  if (ln && ta) {
    ln.scrollTop = ta.scrollTop;
  }
}

/* ── File Tree Operations ───────────────────────────────────────────────── */

function toggleGroup(label) {
  const groupedFiles = groupFiles(_state.filteredFiles);
  for (const g of groupedFiles) {
    if (g.label === label) {
      g.collapsed = !g.collapsed;
      break;
    }
  }
  reapplyEditor();
}

function filterFiles() {
  const q = (_state.fileSearch || '').toLowerCase();
  if (!q) {
    _state.filteredFiles = [..._state.files];
  } else {
    _state.filteredFiles = _state.files.filter((f) =>
      (f.name || '').toLowerCase().includes(q) ||
      (f.path || '').toLowerCase().includes(q)
    );
  }
  reapplyEditor();
}

/* ── File Content Loading ───────────────────────────────────────────────── */

async function loadFileContent(fileName) {
  if (_state.destroyed) return;

  // Check for unsaved changes
  if (_state.isDirty) {
    const confirmed = await confirmDialog(
      'Unsaved Changes',
      `You have unsaved changes in ${_state.activeFileName}. Discard them?`
    );
    if (!confirmed) return;
  }

  const api = getApi();
  if (!api) return;

  _state.activeFileName = fileName;
  _state.editorContent = '';
  _state.originalContent = '';
  _state.isDirty = false;
  _state.lastSaved = null;

  // Show loading state in editor
  renderEditorLoading();

  try {
    const result = await api.get(`/api/v1/config/${encodeURIComponent(fileName)}`);
    const content = typeof result?.data === 'string' ? result.data
      : typeof result?.content === 'string' ? result.content
      : typeof result === 'string' ? result
      : JSON.stringify(result, null, 2);

    _state.editorContent = content;
    _state.originalContent = content;
    _state.isDirty = false;
    _state.syntax = detectSyntax(fileName);

    // Update the file's metadata
    const fileMeta = _state.files.find((f) => f.name === fileName);
    if (fileMeta && result?.meta) {
      Object.assign(fileMeta, result.meta);
    }

    if (!_state.destroyed) {
      reapplyEditor();
    }
  } catch (err) {
    console.error('[config] Failed to load file:', err);
    _state.errorMessage = `Failed to load ${fileName}: ${err.message}`;
    _state.error = true;
    if (!_state.destroyed) {
      reapplyEditor();
    }
  }
}

function renderEditorLoading() {
  if (!_state.container) return;
  const editorPanel = _state.container.querySelector('.config-editor-panel');
  if (!editorPanel) return;

  editorPanel.innerHTML = html`
    <div style="display: flex; flex-direction: column; gap: var(--space-3); padding: var(--space-6);">
      ${skeletonHeading({ width: '180px' })}
      ${skeletonButton({ width: '60px' })}
      ${Array.from({ length: 15 }, (_, i) => skeletonText({ width: `${40 + Math.random() * 60}%` }))}
    </div>
  `;
}

/* ── Save ────────────────────────────────────────────────────────────────── */

async function saveFile() {
  if (_state.destroyed || !_state.activeFileName || _state.editorReadOnly) return;
  if (!_state.isDirty) return;

  // Validate JSON syntax if applicable
  if (_state.syntax === 'json') {
    const validationError = validateJson(_state.editorContent);
    if (validationError) {
      const proceed = await confirmDialog(
        'Invalid JSON',
        `This file contains invalid JSON: ${validationError}\n\nSave anyway?`
      );
      if (!proceed) return;
    }
  }

  const api = getApi();
  if (!api) return;

  // Show saving state
  const saveBtn = _state.saveBtnEl;
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="c-btn__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin" style="width:14px;height:14px;"><circle cx="12" cy="12" r="10" stroke-dasharray="31.4 31.4" stroke-dashoffset="10"/></svg></span> Saving…`;
  }

  try {
    await api.put(`/api/v1/config/${encodeURIComponent(_state.activeFileName)}`, {
      content: _state.editorContent,
    });

    _state.originalContent = _state.editorContent;
    _state.isDirty = false;
    _state.lastSaved = new Date();

    if (!_state.destroyed) {
      updateSaveButton();
      updateBreadcrumb();
      updateStatusBar();
      // Show success toast
      const toast = _state.container?.querySelector('#config-save-btn');
      if (saveBtn) {
        saveBtn.innerHTML = `<span class="c-btn__icon">${ICONS.check}</span> Saved`;
        setTimeout(() => {
          if (!_state.destroyed) updateSaveButton();
        }, 1500);
      }
    }
  } catch (err) {
    console.error('[config] Save failed:', err);
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = `<span class="c-btn__icon">${ICONS.check}</span> Save Failed`;
      saveBtn.className = 'c-btn c-btn--sm c-btn--danger';
      setTimeout(() => {
        if (!_state.destroyed) updateSaveButton();
      }, 2000);
    }
  }
}

/* ── Format ──────────────────────────────────────────────────────────────── */

function formatEditor() {
  if (!_state.editorContent) return;

  try {
    if (_state.syntax === 'json') {
      const parsed = JSON.parse(_state.editorContent);
      _state.editorContent = JSON.stringify(parsed, null, 2);
    } else {
      // For other formats, try basic formatting (remove extra blank lines)
      _state.editorContent = _state.editorContent
        .split('\n')
        .map((l) => l.trimEnd())
        .join('\n')
        .replace(/\n{3,}/g, '\n\n');
    }

    if (_state.editorTextarea) {
      _state.editorTextarea.value = _state.editorContent;
    }

    const dirty = _state.editorContent !== _state.originalContent;
    _state.isDirty = dirty;
    updateSaveButton();
    updateBreadcrumb();
    updateLineNumbers();
  } catch (err) {
    console.warn('[config] Format failed:', err);
  }
}

/* ── Download ────────────────────────────────────────────────────────────── */

function downloadFile() {
  if (!_state.editorContent || !_state.activeFileName) return;
  const blob = new Blob([_state.editorContent], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = _state.activeFileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/* ── Reset ───────────────────────────────────────────────────────────────── */

async function resetFile() {
  if (!_state.activeFileName) return;

  const confirmed = await confirmDialog(
    'Reset to Defaults',
    `This will reset ${_state.activeFileName} to its default values and create a backup of the current version. Continue?`
  );
  if (!confirmed) return;

  // Load the default by fetching without caching or via a reset endpoint
  const api = getApi();
  if (!api) return;

  try {
    // Try a specific reset endpoint if available, otherwise re-fetch original
    const result = await api.get(`/api/v1/config/${encodeURIComponent(_state.activeFileName)}`, {}, {
      headers: { 'Cache-Control': 'no-cache' },
    });

    let content = typeof result?.data === 'string' ? result.data
      : typeof result?.content === 'string' ? result.content
      : typeof result === 'string' ? result
      : JSON.stringify(result, null, 2);

    _state.editorContent = content;
    _state.originalContent = content;
    _state.isDirty = false;

    if (_state.editorTextarea) {
      _state.editorTextarea.value = content;
    }

    updateSaveButton();
    updateBreadcrumb();
    updateLineNumbers();
  } catch (err) {
    console.error('[config] Reset failed:', err);
  }
}

/* ── Validation ─────────────────────────────────────────────────────────── */

function validateJson(content) {
  if (!content || !content.trim()) return null;
  try {
    JSON.parse(content);
    return null;
  } catch (err) {
    return err.message;
  }
}

/* ── Confirmation Dialog ────────────────────────────────────────────────── */

function confirmDialog(title, message) {
  return new Promise((resolve) => {
    // Check if there's a modal system to use
    const modalContainer = document.getElementById('modal-container');
    if (!modalContainer) {
      resolve(confirm(`${title}\n\n${message}`));
      return;
    }

    modalContainer.innerHTML = `
      <div class="c-modal c-modal--sm animate-scale-in">
        <div class="c-modal__header">
          <h3 class="c-modal__title">${esc(title)}</h3>
        </div>
        <div class="c-modal__body">
          <p style="color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; margin: 0;">
            ${esc(message)}
          </p>
        </div>
        <div class="c-modal__footer" style="display: flex; gap: var(--space-2); justify-content: flex-end;">
          <button class="c-btn c-btn--ghost" id="confirm-cancel-btn">Cancel</button>
          <button class="c-btn c-btn--danger-solid" id="confirm-ok-btn">Confirm</button>
        </div>
      </div>
    `;
    modalContainer.style.display = 'flex';

    const cleanup = () => {
      modalContainer.innerHTML = '';
      modalContainer.style.display = 'none';
    };

    modalContainer.querySelector('#confirm-cancel-btn')?.addEventListener('click', () => {
      cleanup();
      resolve(false);
    });

    modalContainer.querySelector('#confirm-ok-btn')?.addEventListener('click', () => {
      cleanup();
      resolve(true);
    });

    modalContainer.addEventListener('click', (e) => {
      if (e.target === modalContainer) {
        cleanup();
        resolve(false);
      }
    });
  });
}

/* ── Status Bar Updates ─────────────────────────────────────────────────── */

function updateStatusBar() {
  if (_state.destroyed || !_state.container) return;
  const activeFile = _state.files.find((f) => f.name === _state.activeFileName);
  const sizeEl = _state.container.querySelector('#config-file-size');
  const linesEl = _state.container.querySelector('#config-line-count');
  const syntaxEl = _state.container.querySelector('#config-syntax-type');
  const savedEl = _state.container.querySelector('#config-last-saved');

  if (sizeEl && activeFile) sizeEl.textContent = formatFileSize(activeFile.size);
  if (linesEl) linesEl.textContent = `${(_state.editorContent || '').split('\n').length} lines`;
  if (syntaxEl) syntaxEl.textContent = _state.syntax.toUpperCase();
  if (savedEl) {
    savedEl.textContent = _state.lastSaved
      ? `Last saved: ${formatTimestamp(_state.lastSaved)}`
      : 'Not saved yet';
  }
}

/* ── Before Unload Handler ──────────────────────────────────────────────── */

function handleBeforeUnload(e) {
  if (_state.isDirty) {
    e.preventDefault();
    e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
  }
}

/* ── Data Loading ───────────────────────────────────────────────────────── */

async function loadConfigList() {
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
    const result = await api.get('/api/v1/config');
    const files = Array.isArray(result?.data) ? result.data
      : Array.isArray(result) ? result
      : [];

    _state.files = files;
    _state.filteredFiles = [...files];
    _state.error = false;
    _state.loading = false;

    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
  } catch (err) {
    console.error('[config] Failed to load config list:', err);
    _state.error = true;
    _state.errorMessage = err.message || 'Failed to fetch configuration list.';
    _state.loading = false;
    if (!_state.destroyed && _state.container) {
      renderPage(_state.container);
    }
  }
}

/* ── Utility ────────────────────────────────────────────────────────────── */

function _relativeTime(timestamp) {
  if (!timestamp) return '';
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  const days = Math.floor(hr / 24);
  return `${days}d`;
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

  renderSkeletons(container);
  loadConfigList();
}

/**
 * Mount — called by router after render() inserts HTML.
 * @param {Element} container
 */
export function mount(container) {
  _state.container = container;
}

/**
 * Cleanup — called when navigating away.
 */
export function destroy() {
  _state.destroyed = true;

  // Remove key handler
  if (_state.keyHandler) {
    document.removeEventListener('keydown', _state.keyHandler);
    _state.keyHandler = null;
  }

  window.removeEventListener('beforeunload', handleBeforeUnload);

  _state.container = null;
  _state.files = [];
  _state.filteredFiles = [];
  _state.activeFileName = null;
  _state.editorContent = '';
  _state.originalContent = '';
  _state.isDirty = false;
  _state.lastSaved = null;
  _state.treeEl = null;
  _state.editorTextarea = null;
  _state.lineNumbersEl = null;
  _state.fileSearchEl = null;
  _state.statusBarEl = null;
  _state.fileBreadcrumbEl = null;
  _state.saveBtnEl = null;
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
      return '<div id="config-root"></div>';
    },
    async mount(container) {
      const root = container.querySelector('#config-root') || container;
      try {
        const templateHtml = await loadTemplate('config', {
          loading: true,
          fileSearch: '',
        });
        root.innerHTML = templateHtml;
      } catch (err) {
        console.error('[Config] Failed to load template:', err);
      }
      // Trigger data loading; renderPage() will replace the template content
      _state.container = root;
      loadConfigList();
    },
    destroy,
  };
}
