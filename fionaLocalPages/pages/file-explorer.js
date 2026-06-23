/* ==========================================================================
   file-explorer.js — File Explorer Page
   ==========================================================================
   A file browser for navigating the Fiona project filesystem with split
   panel (directory tree | file preview), breadcrumb navigation, toolbar
   actions, context menus, file search, grid/list view toggle, drag-and-
   drop upload, and syntax-highlighted file preview.

   Exports: { render(routeInfo), mount(container), destroy() }
   ========================================================================== */

import { html } from '../js/components/BaseComponent.js';
import { ICONS } from '../js/components/_icons.js';
import { contextMenu } from '../js/components/ContextMenu.js';
import { modal } from '../js/components/Modal.js';

/* ── API Helper ─────────────────────────────────────────────────────────── */

function getApi() {
  return window.fiona?.api || window.__fiona?.api;
}

/* ── Constants ──────────────────────────────────────────────────────────── */

const DEFAULT_ROOT = '/home/Dhruv/Documents/Projects/Fiona';
const TEXT_EXTENSIONS = new Set([
  'py', 'js', 'ts', 'jsx', 'tsx', 'css', 'scss', 'less', 'html', 'htm',
  'md', 'markdown', 'json', 'yaml', 'yml', 'toml', 'txt', 'cfg', 'conf',
  'ini', 'env', 'sh', 'bash', 'zsh', 'rb', 'go', 'rs', 'java', 'c', 'cpp',
  'h', 'hpp', 'sql', 'r', 'm', 'swift', 'kt', 'dockerfile', 'makefile',
  'xml', 'svg', 'vue', 'svelte', 'astro', 'php',
]);
const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico']);
const MAX_TEXT_PREVIEW = 50000; // max chars to preview

/* ─── Page State ──────────────────────────────────────────────────────────── */

let _container = null;
let _state = {
  currentPath: '',
  entries: [],
  selectedPath: null,
  selectedEntry: null,
  fileContent: null,
  fileInfo: null,
  isLoading: false,
  hasError: false,
  errorMessage: '',
  viewMode: 'list',        // 'list' | 'grid'
  searchQuery: '',
  expandedDirs: new Set(),
  breadcrumb: [],
  isDragging: false,
  previewType: null,        // 'text' | 'image' | 'metadata' | 'loading' | null
  rootPath: DEFAULT_ROOT,
};

let _unbindFns = [];
let _isDestroyed = false;

// Debounce timers
let _searchTimer = null;
let _resizeTimer = null;

/* ── Helper Functions ─────────────────────────────────────────────────────── */

function _escapeHtml(str) {
  if (str == null) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

function formatFileSize(bytes) {
  if (bytes == null) return '';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0);
  return `${size} ${units[i]}`;
}

function formatDate(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  const now = new Date();
  const diff = now - date;
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function getFileExtension(filename) {
  const dot = filename.lastIndexOf('.');
  if (dot === -1) return '';
  return filename.slice(dot + 1).toLowerCase();
}

function isTextFile(filename) {
  const ext = getFileExtension(filename);
  return TEXT_EXTENSIONS.has(ext);
}

function isImageFile(filename) {
  const ext = getFileExtension(filename);
  return IMAGE_EXTENSIONS.has(ext);
}

function getFileTypeIcon(entry) {
  if (entry.type === 'directory') {
    return ICONS.folder;
  }
  const ext = getFileExtension(entry.name);
  if (['js', 'ts', 'jsx', 'tsx', 'py', 'go', 'rs', 'java', 'c', 'cpp'].includes(ext)) {
    return ICONS.fileCode;
  }
  if (['json', 'yaml', 'yml', 'toml', 'xml'].includes(ext)) {
    return ICONS.fileJson;
  }
  if (['md', 'txt', 'cfg', 'conf', 'ini', 'env'].includes(ext)) {
    return ICONS.fileText;
  }
  if (IMAGE_EXTENSIONS.has(ext)) {
    return ICONS.file;
  }
  return ICONS.file;
}

/* ── Breadcrumb ──────────────────────────────────────────────────────────── */

function buildBreadcrumb(path) {
  if (!path) return [];
  const parts = path.split('/').filter(Boolean);
  const crumbs = [];
  let accumulated = '';
  for (const part of parts) {
    accumulated += '/' + part;
    crumbs.push({ label: part, path: accumulated });
  }
  return crumbs;
}

/* ── API Calls ────────────────────────────────────────────────────────────── */

async function fetchDirList(path) {
  const api = getApi();
  if (!api) throw new Error('API not available');
  return api.get('/api/v1/files/list', { path });
}

async function fetchFileContent(path) {
  const api = getApi();
  if (!api) throw new Error('API not available');
  return api.get('/api/v1/files/read', { path });
}

async function fetchFileInfo(path) {
  const api = getApi();
  if (!api) throw new Error('API not available');
  return api.get('/api/v1/files/info', { path });
}

async function writeFile(path, content) {
  const api = getApi();
  if (!api) throw new Error('API not available');
  return api.post('/api/v1/files/write', { path, content });
}

/* ── Navigation ──────────────────────────────────────────────────────────── */

async function navigateTo(path) {
  if (_isDestroyed) return;
  _state.isLoading = true;
  _state.hasError = false;
  _state.errorMessage = '';
  _state.selectedPath = null;
  _state.selectedEntry = null;
  _state.fileContent = null;
  _state.fileInfo = null;
  _state.previewType = null;
  _state.searchQuery = '';

  renderContent();

  try {
    const entries = await fetchDirList(path);
    _state.currentPath = path;
    _state.breadcrumb = buildBreadcrumb(path);
    _state.entries = entries || [];
    _state.isLoading = false;
  } catch (err) {
    _state.isLoading = false;
    _state.hasError = true;
    _state.errorMessage = err.message || 'Failed to load directory';
    console.error('[FileExplorer] navigate error:', err);
  }

  renderContent();
  renderBreadcrumb();
  renderToolbar();
}

/* ── File Selection ───────────────────────────────────────────────────────── */

async function selectFile(path, entry) {
  if (_isDestroyed) return;
  _state.selectedPath = path;
  _state.selectedEntry = entry;

  // Update tree highlight
  _highlightTreeNode(path);

  if (entry.type === 'directory') {
    navigateTo(path);
    return;
  }

  // Show loading preview
  _state.previewType = 'loading';
  renderPreview();

  try {
    if (isImageFile(entry.name)) {
      // Images: just show metadata + img tag
      _state.fileContent = null;
      _state.fileInfo = await fetchFileInfo(path);
      _state.previewType = 'image';
    } else if (isTextFile(entry.name)) {
      // Text files: read content
      const result = await fetchFileContent(path);
      _state.fileContent = result?.content || '';
      _state.fileInfo = await fetchFileInfo(path);
      _state.previewType = 'text';
    } else {
      // Other files: just metadata
      _state.fileContent = null;
      _state.fileInfo = await fetchFileInfo(path);
      _state.previewType = 'metadata';
    }
  } catch (err) {
    console.error('[FileExplorer] selectFile error:', err);
    _state.previewType = 'metadata';
    _state.fileInfo = _state.fileInfo || { name: entry.name, size: entry.size, modified: entry.modified, type: 'file' };
  }

  renderPreview();
}

/* ── Render Functions ──────────────────────────────────────────────────────── */

function renderLoadingSkeleton() {
  return html`
    <div class="fe-skeleton">
      <div class="fe-skeleton__toolbar">
        <div class="c-skeleton c-skeleton--button" style="width: 80px;"></div>
        <div class="c-skeleton c-skeleton--button" style="width: 80px;"></div>
        <div class="c-skeleton c-skeleton--button" style="width: 80px;"></div>
      </div>
      <div class="fe-skeleton__body">
        <div class="fe-skeleton__tree">
          <div class="c-skeleton c-skeleton--text" style="width: 60%;"></div>
          <div class="c-skeleton c-skeleton--text" style="width: 80%;"></div>
          <div class="c-skeleton c-skeleton--text" style="width: 45%;"></div>
          <div class="c-skeleton c-skeleton--text" style="width: 70%;"></div>
          <div class="c-skeleton c-skeleton--text" style="width: 55%;"></div>
        </div>
        <div class="fe-skeleton__preview">
          <div class="c-skeleton c-skeleton--heading" style="width: 30%;"></div>
          <div class="c-skeleton c-skeleton--text"></div>
          <div class="c-skeleton c-skeleton--text"></div>
          <div class="c-skeleton c-skeleton--text" style="width: 60%;"></div>
          <div class="c-skeleton c-skeleton--rect" style="height: 200px; margin-top: 12px;"></div>
        </div>
      </div>
    </div>
  `;
}

function renderErrorState() {
  return html`
    <div class="fe-error">
      <div class="fe-error__icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.5" width="48" height="48"
             stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
      </div>
      <div class="fe-error__title">Failed to Load Directory</div>
      <div class="fe-error__desc">${_escapeHtml(_state.errorMessage)}</div>
      <button class="c-btn c-btn--primary" data-action="fe-retry" style="margin-top: 16px;">
        Retry
      </button>
    </div>
  `;
}

/**
 * Render the main page content.
 */
function renderContent() {
  if (!_container) return;
  const contentEl = _container.querySelector('.fe-content-panel');
  if (!contentEl) return;

  if (_state.isLoading) {
    contentEl.innerHTML = renderLoadingSkeleton();
    return;
  }

  if (_state.hasError) {
    contentEl.innerHTML = renderErrorState();
    return;
  }

  const filtered = _state.searchQuery
    ? _state.entries.filter((e) =>
        e.name.toLowerCase().includes(_state.searchQuery.toLowerCase())
      )
    : _state.entries;

  const viewClass = _state.viewMode === 'grid' ? 'fe-file-grid' : 'fe-file-list';

  contentEl.innerHTML = html`
    <div class="fe-file-toolbar">
      <div class="fe-file-search">
        <span class="fe-file-search__icon">${ICONS.search}</span>
        <input type="text" class="fe-file-search__input"
               id="fe-search-input"
               placeholder="Search in this directory…"
               value="${_escapeHtml(_state.searchQuery)}"
               autocomplete="off" />
      </div>
      <div class="fe-file-actions">
        <button class="c-btn c-btn--icon c-btn--sm ${_state.viewMode === 'list' ? 'c-btn--primary' : ''}"
                data-action="fe-view-list" title="List view">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" width="14" height="14"
               stroke-linecap="round" stroke-linejoin="round">
            <line x1="8" y1="6" x2="21" y2="6"/>
            <line x1="8" y1="12" x2="21" y2="12"/>
            <line x1="8" y1="18" x2="21" y2="18"/>
            <line x1="3" y1="6" x2="3.01" y2="6"/>
            <line x1="3" y1="12" x2="3.01" y2="12"/>
            <line x1="3" y1="18" x2="3.01" y2="18"/>
          </svg>
        </button>
        <button class="c-btn c-btn--icon c-btn--sm ${_state.viewMode === 'grid' ? 'c-btn--primary' : ''}"
                data-action="fe-view-grid" title="Grid view">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" width="14" height="14"
               stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="7" height="7"/>
            <rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/>
            <rect x="3" y="14" width="7" height="7"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="${viewClass}" id="fe-file-container">
      ${filtered.length === 0
        ? html`
            <div class="fe-empty">
              <div class="fe-empty__icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.5" width="36" height="36"
                     stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <div class="fe-empty__text">
                ${_state.searchQuery ? 'No files match your search.' : 'This directory is empty.'}
              </div>
            </div>
          `
        : html.raw(filtered.map((entry) => _renderFileEntry(entry)).join(''))
      }
    </div>
  `;
}

/**
 * Render a single file/directory entry.
 */
function _renderFileEntry(entry) {
  const isDir = entry.type === 'directory';
  const icon = getFileTypeIcon(entry);
  const isSelected = entry.path === _state.selectedPath;

  if (_state.viewMode === 'grid') {
    return html`
      <div class="fe-file-item fe-file-item--grid ${isSelected ? 'fe-file-item--selected' : ''}"
           data-path="${_escapeHtml(entry.path)}"
           data-type="${entry.type}"
           data-name="${_escapeHtml(entry.name)}"
           draggable="true">
        <div class="fe-file-item__icon fe-file-item__icon--grid">
          ${isDir
            ? html`<span style="width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">${icon}</span>`
            : html`<span style="width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">${icon}</span>`
          }
        </div>
        <div class="fe-file-item__name fe-file-item__name--grid">${_escapeHtml(entry.name)}</div>
        <div class="fe-file-item__meta">${isDir ? '' : formatFileSize(entry.size)}</div>
      </div>
    `;
  }

  return html`
    <div class="fe-file-item fe-file-item--list ${isSelected ? 'fe-file-item--selected' : ''}"
         data-path="${_escapeHtml(entry.path)}"
         data-type="${entry.type}"
         data-name="${_escapeHtml(entry.name)}"
         draggable="true">
      <span class="fe-file-item__icon">${icon}</span>
      <span class="fe-file-item__name">${_escapeHtml(entry.name)}</span>
      <span class="fe-file-item__meta fe-file-item__size">${isDir ? '—' : formatFileSize(entry.size)}</span>
      <span class="fe-file-item__meta fe-file-item__date">${formatDate(entry.modified)}</span>
    </div>
  `;
}

/**
 * Render the preview pane.
 */
function renderPreview() {
  const previewEl = _container?.querySelector('.fe-preview');
  if (!previewEl) return;

  if (!_state.selectedEntry) {
    previewEl.innerHTML = html`
      <div class="fe-preview__empty">
        <div class="fe-preview__empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.5" width="36" height="36"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div class="fe-preview__empty-text">Select a file to preview</div>
      </div>
    `;
    return;
  }

  if (_state.previewType === 'loading') {
    previewEl.innerHTML = html`
      <div style="padding: 24px;">
        <div class="c-skeleton c-skeleton--heading" style="width: 40%;"></div>
        <div class="c-skeleton c-skeleton--text" style="margin-top: 12px;"></div>
        <div class="c-skeleton c-skeleton--text"></div>
        <div class="c-skeleton c-skeleton--text" style="width: 70%;"></div>
        <div class="c-skeleton c-skeleton--rect" style="height: 200px; margin-top: 16px;"></div>
      </div>
    `;
    return;
  }

  if (_state.previewType === 'text' && _state.fileContent != null) {
    const ext = getFileExtension(_state.selectedEntry.name);
    const content = _state.fileContent.length > MAX_TEXT_PREVIEW
      ? _state.fileContent.slice(0, MAX_TEXT_PREVIEW) + '\n\n… [truncated]'
      : _state.fileContent;
    const highlighted = highlightCode(content, ext);

    previewEl.innerHTML = html`
      <div class="fe-preview__header">
        <span class="fe-preview__filename">${_escapeHtml(_state.selectedEntry.name)}</span>
        <span class="fe-preview__filemeta">
          ${formatFileSize(_state.selectedEntry.size)} · ${(_state.fileContent.length / 1024).toFixed(1)} KB
        </span>
      </div>
      <div class="fe-preview__code">
        <pre><code>${html.raw(highlighted)}</code></pre>
      </div>
    `;
    return;
  }

  if (_state.previewType === 'image') {
    // Image files: show preview via API endpoint
    const imgPath = _state.selectedEntry.path;
    previewEl.innerHTML = html`
      <div class="fe-preview__header">
        <span class="fe-preview__filename">${_escapeHtml(_state.selectedEntry.name)}</span>
        <span class="fe-preview__filemeta">${formatFileSize(_state.selectedEntry.size)}</span>
      </div>
      <div class="fe-preview__image">
        <img src="/api/v1/files/read?path=${encodeURIComponent(imgPath)}"
             alt="${_escapeHtml(_state.selectedEntry.name)}"
             style="max-width: 100%; max-height: 60vh; object-fit: contain;"
             onerror="this.parentElement.innerHTML='<div class=\\'fe-preview__error\\'>Image preview unavailable</div>'" />
      </div>
    `;
    return;
  }

  // Default: metadata view
  const info = _state.fileInfo || _state.selectedEntry;
  previewEl.innerHTML = html`
    <div class="fe-preview__header">
      <span class="fe-preview__filename">${_escapeHtml(_state.selectedEntry.name)}</span>
    </div>
    <div class="fe-preview__metadata">
      <div class="fe-preview__meta-row">
        <span class="fe-preview__meta-label">Type</span>
        <span class="fe-preview__meta-value">
          ${info.type || _state.selectedEntry.type}
          ${info.type === 'directory' ? '' : `.${getFileExtension(_state.selectedEntry.name)}`}
        </span>
      </div>
      <div class="fe-preview__meta-row">
        <span class="fe-preview__meta-label">Size</span>
        <span class="fe-preview__meta-value">${formatFileSize(info.size ?? _state.selectedEntry.size)}</span>
      </div>
      <div class="fe-preview__meta-row">
        <span class="fe-preview__meta-label">Modified</span>
        <span class="fe-preview__meta-value">${formatDate(info.modified ?? _state.selectedEntry.modified)}</span>
      </div>
      ${info.permissions ? html`
      <div class="fe-preview__meta-row">
        <span class="fe-preview__meta-label">Permissions</span>
        <span class="fe-preview__meta-value">${_escapeHtml(info.permissions)}</span>
      </div>
      ` : ''}
      ${info.path ? html`
      <div class="fe-preview__meta-row">
        <span class="fe-preview__meta-label">Path</span>
        <span class="fe-preview__meta-value fe-preview__meta-value--path">${_escapeHtml(info.path)}</span>
      </div>
      ` : ''}
    </div>
  `;
}

/**
 * Render the breadcrumb navigation.
 */
function renderBreadcrumb() {
  const el = _container?.querySelector('.fe-breadcrumb');
  if (!el) return;

  el.innerHTML = html.raw(_state.breadcrumb.map((crumb, i) => html`
    ${i > 0 ? html`<span class="fe-breadcrumb__sep">${ICONS.chevronRight}</span>` : ''}
    <span class="fe-breadcrumb__item ${i === _state.breadcrumb.length - 1 ? 'fe-breadcrumb__item--active' : ''}"
          data-breadcrumb-path="${_escapeHtml(crumb.path)}">
      ${_escapeHtml(crumb.label)}
    </span>
  `).join(''));
}

/**
 * Render the toolbar actions.
 */
function renderToolbar() {
  const el = _container?.querySelector('.fe-toolbar-actions');
  if (!el) return;

  // Toolbar is already in the HTML, just update the refresh visibility etc.
}

/**
 * Highlight a tree node by path.
 */
function _highlightTreeNode(path) {
  const tree = _container?.querySelector('.fe-tree');
  if (!tree) return;
  tree.querySelectorAll('.fe-tree-item').forEach((el) => {
    el.classList.toggle('fe-tree-item--selected', el.dataset.path === path);
  });
}

/* ── Syntax Highlighting ──────────────────────────────────────────────────── */

/**
 * Basic syntax highlighting for common file types.
 * Returns HTML with <span class="hl-*"> tags.
 */
function highlightCode(code, ext) {
  if (!code) return '';

  const escaped = _escapeHtml(code);

  // Simple line-by-line highlighting for common patterns
  const lines = escaped.split('\n');
  const highlighted = lines.map((line) => {
    let result = line;

    // Comments (single line)
    if (['py', 'rb', 'sh', 'bash', 'yaml', 'yml', 'toml', 'r', 'makefile'].includes(ext)) {
      result = result.replace(/(#.*)$/g, '<span class="hl-comment">$1</span>');
    } else if (['js', 'ts', 'jsx', 'tsx', 'go', 'rs', 'java', 'c', 'cpp', 'h', 'hpp', 'css', 'scss', 'less', 'php', 'swift', 'kt'].includes(ext)) {
      result = result.replace(/(\/\/.*)$/g, '<span class="hl-comment">$1</span>');
      result = result.replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="hl-comment">$1</span>');
    } else if (['html', 'htm', 'xml', 'svg', 'vue', 'svelte', 'astro'].includes(ext)) {
      result = result.replace(/(&lt;!--[\s\S]*?--&gt;)/g, '<span class="hl-comment">$1</span>');
    }

    // Strings (double quotes)
    result = result.replace(/(&quot;[^&quot;]*&quot;)/g, '<span class="hl-string">$1</span>');
    // Strings (single quotes)
    result = result.replace(/(&#39;[^&#39;]*&#39;)/g, '<span class="hl-string">$1</span>');
    // Template literals
    result = result.replace(/(`[^`]*`)/g, '<span class="hl-string">$1</span>');

    // Keywords
    const keywords = [
      '\\b(import|export|from|default|as|const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|delete|typeof|instanceof|class|extends|super|this|async|await|yield|try|catch|finally|throw|in|of|with|void|null|undefined|true|false|static|get|set|private|protected|public|readonly|enum|interface|type|implements|abstract|namespace|module|declare)\\b',
      '\\b(def|class|return|if|elif|else|for|while|import|from|as|try|except|finally|raise|with|pass|break|continue|lambda|yield|and|or|not|is|in|True|False|None|self|async|await|global|nonlocal|assert|del|print|len|range|map|filter|zip|enumerate|sorted|reversed|open|with|if|else|elif)\\b',
      '\\b(func|var|if|else|for|range|return|import|package|nil|true|false|defer|go|chan|select|switch|case|break|continue|fallthrough|default|map|struct|interface|type|const)\\b',
    ];

    for (const kwPattern of keywords) {
      try {
        result = result.replace(new RegExp(kwPattern, 'g'), '<span class="hl-keyword">$1</span>');
      } catch { /* skip bad patterns */ }
    }

    // Numbers
    result = result.replace(/\b(\d+\.?\d*)\b/g, '<span class="hl-number">$1</span>');

    // Function calls
    result = result.replace(/\b([a-zA-Z_$][\w$]*)\s*(\()/g, '<span class="hl-function">$1</span>$2');

    return result;
  });

  return highlighted.join('\n');
}

/* ── Tree Rendering ────────────────────────────────────────────────────────── */

async function renderTree() {
  const treeEl = _container?.querySelector('.fe-tree');
  if (!treeEl) return;

  const path = _state.rootPath;

  try {
    const entries = await fetchDirList(path);

    treeEl.innerHTML = html`
      <div class="fe-tree-item fe-tree-item--root"
           data-path="${_escapeHtml(path)}"
           data-type="directory">
        <span class="fe-tree-item__icon">${ICONS.folder}</span>
        <span class="fe-tree-item__label">Project Root</span>
        <span class="fe-tree-item__chevron ${_state.expandedDirs.has(path) ? 'fe-tree-item__chevron--open' : ''}">
          ${ICONS.chevronDown}
        </span>
      </div>
      ${_state.expandedDirs.has(path)
        ? html.raw(renderTreeChildren(entries || [], path, 1))
        : ''
      }
    `;

    bindTreeEvents();
  } catch (err) {
    console.error('[FileExplorer] Failed to load tree root:', err);
    treeEl.innerHTML = html`
      <div class="fe-tree__error">Failed to load file tree</div>
    `;
  }
}

function renderTreeChildren(entries, parentPath, depth) {
  const sorted = [...entries].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return sorted.map((entry) => {
    const isDir = entry.type === 'directory';
    const isExpanded = _state.expandedDirs.has(entry.path);
    const icon = isDir ? ICONS.folder : getFileTypeIcon(entry);

    return html`
      <div class="fe-tree-item ${_state.selectedPath === entry.path ? 'fe-tree-item--selected' : ''}"
           data-path="${_escapeHtml(entry.path)}"
           data-type="${entry.type}"
           data-name="${_escapeHtml(entry.name)}"
           style="padding-left: ${12 + depth * 16}px;">
        <span class="fe-tree-item__icon">${icon}</span>
        <span class="fe-tree-item__label">${_escapeHtml(entry.name)}</span>
        ${isDir ? html`
          <span class="fe-tree-item__chevron ${isExpanded ? 'fe-tree-item__chevron--open' : ''}">
            ${ICONS.chevronDown}
          </span>
        ` : ''}
      </div>
      ${isDir && isExpanded
        ? html`<div class="fe-tree-children" data-dir="${_escapeHtml(entry.path)}">${renderTreeChildrenPlaceholder(entry.path, depth + 1)}</div>`
        : ''
      }
    `;
  }).join(''));
}

function renderTreeChildrenPlaceholder(dirPath, depth) {
  // Will be lazily loaded
  return html`
    <div style="padding: 8px ${12 + depth * 16}px; color: #484f58; font-size: 11px;">
      Loading…
    </div>
  `;
}

async function expandTreeNode(dirPath) {
  if (_state.expandedDirs.has(dirPath)) {
    _state.expandedDirs.delete(dirPath);
    renderTree();
    return;
  }

  _state.expandedDirs.add(dirPath);

  try {
    const entries = await fetchDirList(dirPath);
    // After loading, re-render the tree
    renderTree();
  } catch (err) {
    console.error('[FileExplorer] expand error:', err);
    _state.expandedDirs.delete(dirPath);
  }
}

/* ── Tree Events ──────────────────────────────────────────────────────────── */

function bindTreeEvents() {
  const treeEl = _container?.querySelector('.fe-tree');
  if (!treeEl) return;

  treeEl.querySelectorAll('.fe-tree-item').forEach((item) => {
    // Click: select / expand
    item.addEventListener('click', async (e) => {
      const path = item.dataset.path;
      const type = item.dataset.type;

      if (!path) return;

      if (type === 'directory') {
        // Don't navigate to root if already there, just expand
        if (path === _state.rootPath) {
          // Toggle root expansion
          _state.expandedDirs.has(path)
            ? _state.expandedDirs.delete(path)
            : _state.expandedDirs.add(path);
          renderTree();
          return;
        }
        navigateTo(path);
      } else {
        // Find the entry and select it
        const name = item.dataset.name;
        selectFile(path, { name, path, type, size: 0 });
        renderTree(); // to update selection highlighting
      }
    });

    // Context menu
    item.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const path = item.dataset.path;
      const type = item.dataset.type;
      const name = item.dataset.name;

      showFileContextMenu(e.clientX, e.clientY, { name, path, type });
    });
  });
}

/* ── Context Menu ──────────────────────────────────────────────────────────── */

function showFileContextMenu(x, y, entry) {
  const items = [
    {
      label: 'Copy Path',
      icon: 'copy',
      handler: () => {
        navigator.clipboard.writeText(entry.path).catch(() => {});
      },
    },
    {
      label: 'Download',
      icon: 'download',
      disabled: entry.type === 'directory',
      handler: () => {
        downloadFile(entry.path, entry.name);
      },
    },
    { divider: true },
    {
      label: 'Rename',
      icon: 'edit',
      handler: () => {
        showRenameDialog(entry);
      },
    },
    {
      label: 'Delete',
      icon: 'trash',
      danger: true,
      handler: () => {
        showDeleteDialog(entry);
      },
    },
  ];

  contextMenu.showContextMenu(x, y, items);
}

function downloadFile(path, name) {
  // Trigger download via API
  const api = getApi();
  if (!api) return;
  // Since we can't easily download through the API client, open in new tab
  const baseUrl = api._getBaseURL ? api._getBaseURL() : 'http://localhost:8765';
  window.open(`${baseUrl}/api/v1/files/read?path=${encodeURIComponent(path)}`, '_blank');
}

async function showRenameDialog(entry) {
  const oldName = entry.name;
  const result = await modal.showModal({
    title: 'Rename',
    content: html`
      <div class="c-form-group">
        <label class="c-form-group__label">New name</label>
        <input type="text" class="c-input" id="fe-rename-input"
               value="${_escapeHtml(oldName)}"
               style="margin-top: 8px;" />
      </div>
    `,
    size: 'sm',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Rename', value: 'rename', variant: 'primary' },
    ],
  });

  if (result !== 'rename') return;

  const renameInput = document.getElementById('fe-rename-input');
  if (!renameInput) return;

  const newName = renameInput.value.trim();
  if (!newName || newName === oldName) return;

  // TODO: API doesn't have a rename endpoint yet; we'll do a copy + delete
  try {
    const api = getApi();
    const content = await fetchFileContent(entry.path);
    const dir = entry.path.split('/').slice(0, -1).join('/');
    const newPath = dir + '/' + newName;
    await writeFile(newPath, content);
    // Refresh current directory
    navigateTo(_state.currentPath);
  } catch (err) {
    console.error('[FileExplorer] rename failed:', err);
  }
}

async function showDeleteDialog(entry) {
  const result = await modal.showModal({
    title: 'Delete',
    content: html`
      <p>Are you sure you want to delete <strong>${_escapeHtml(entry.name)}</strong>?</p>
      ${entry.type === 'directory' ? '<p style="margin-top: 8px; color: var(--danger);">This directory and all its contents will be permanently deleted.</p>' : ''}
    `,
    size: 'sm',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Delete', value: 'delete', variant: 'danger-solid' },
    ],
  });

  if (result !== 'delete') return;

  // TODO: API doesn't have a delete endpoint yet
  console.log('[FileExplorer] Delete requested:', entry.path);
  // navigateTo(_state.currentPath);
}

/* ── New File / Folder ────────────────────────────────────────────────────── */

async function showNewFileDialog() {
  const result = await modal.showModal({
    title: 'New File',
    content: html`
      <div class="c-form-group">
        <label class="c-form-group__label">File name</label>
        <input type="text" class="c-input" id="fe-newfile-input"
               placeholder="e.g. example.txt"
               style="margin-top: 8px;" />
      </div>
    `,
    size: 'sm',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Create', value: 'create', variant: 'primary' },
    ],
  });

  if (result !== 'create') return;

  const input = document.getElementById('fe-newfile-input');
  if (!input) return;

  const name = input.value.trim();
  if (!name) return;

  const path = (_state.currentPath || _state.rootPath) + '/' + name;

  try {
    await writeFile(path, '');
    navigateTo(_state.currentPath || _state.rootPath);
  } catch (err) {
    console.error('[FileExplorer] create file failed:', err);
  }
}

async function showNewFolderDialog() {
  const result = await modal.showModal({
    title: 'New Folder',
    content: html`
      <div class="c-form-group">
        <label class="c-form-group__label">Folder name</label>
        <input type="text" class="c-input" id="fe-newfolder-input"
               placeholder="e.g. new-folder"
               style="margin-top: 8px;" />
      </div>
    `,
    size: 'sm',
    buttons: [
      { label: 'Cancel', value: 'cancel', variant: 'ghost' },
      { label: 'Create', value: 'create', variant: 'primary' },
    ],
  });

  if (result !== 'create') return;

  const input = document.getElementById('fe-newfolder-input');
  if (!input) return;

  const name = input.value.trim();
  if (!name) return;

  const path = (_state.currentPath || _state.rootPath) + '/' + name;
  // For directories, write a .gitkeep equivalent
  try {
    await writeFile(path + '/.gitkeep', '');
    navigateTo(_state.currentPath || _state.rootPath);
  } catch (err) {
    console.error('[FileExplorer] create folder failed:', err);
  }
}

/* ── Event Bindings ────────────────────────────────────────────────────────── */

function bindEvents() {
  if (!_container) return;

  const cleanups = [];

  // ── Breadcrumb clicks ──
  const breadcrumb = _container.querySelector('.fe-breadcrumb');
  if (breadcrumb) {
    const handler = (e) => {
      const item = e.target.closest('[data-breadcrumb-path]');
      if (item) {
        navigateTo(item.dataset.breadcrumbPath);
      }
    };
    breadcrumb.addEventListener('click', handler);
    cleanups.push(() => breadcrumb.removeEventListener('click', handler));
  }

  // ── File container clicks (delegated) ──
  const fileContainer = _container.querySelector('#fe-file-container');
  if (fileContainer) {
    const handler = (e) => {
      const item = e.target.closest('.fe-file-item');
      if (!item) return;
      const path = item.dataset.path;
      const type = item.dataset.type;
      const name = item.dataset.name;
      if (!path) return;

      selectFile(path, { name, path, type, size: 0 });
      renderContent(); // re-render to show selection
    };
    fileContainer.addEventListener('click', handler);
    cleanups.push(() => fileContainer.removeEventListener('click', handler));

    // Context menu on files
    const ctxHandler = (e) => {
      const item = e.target.closest('.fe-file-item');
      if (!item) return;
      e.preventDefault();
      showFileContextMenu(e.clientX, e.clientY, {
        name: item.dataset.name,
        path: item.dataset.path,
        type: item.dataset.type,
      });
    };
    fileContainer.addEventListener('contextmenu', ctxHandler);
    cleanups.push(() => fileContainer.removeEventListener('contextmenu', ctxHandler));

    // Drag and drop file upload
    const dragHandler = _setupDragAndDrop(fileContainer);
    cleanups.push(dragHandler);
  }

  // ── Search input ──
  const searchInput = _container.querySelector('#fe-search-input');
  if (searchInput) {
    const handler = (e) => {
      clearTimeout(_searchTimer);
      _searchTimer = setTimeout(() => {
        _state.searchQuery = e.target.value;
        renderContent();
      }, 200);
    };
    searchInput.addEventListener('input', handler);
    cleanups.push(() => searchInput.removeEventListener('input', handler));
  }

  // ── Toolbar actions ──
  const toolbar = _container.querySelector('.fe-toolbar');
  if (toolbar) {
    const handler = (e) => {
      const action = e.target.closest('[data-action]');
      if (!action) return;
      const actionName = action.dataset.action;

      switch (actionName) {
        case 'fe-refresh':
          navigateTo(_state.currentPath || _state.rootPath);
          break;
        case 'fe-new-file':
          showNewFileDialog();
          break;
        case 'fe-new-folder':
          showNewFolderDialog();
          break;
        case 'fe-view-list':
          _state.viewMode = 'list';
          renderContent();
          _updateViewToggleButtons();
          break;
        case 'fe-view-grid':
          _state.viewMode = 'grid';
          renderContent();
          _updateViewToggleButtons();
          break;
        case 'fe-retry':
          navigateTo(_state.rootPath);
          break;
      }
    };
    toolbar.addEventListener('click', handler);
    cleanups.push(() => toolbar.removeEventListener('click', handler));
  }

  // ── Resize handler ──
  const resizeHandler = () => {
    clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(() => {
      // Just keep references alive
    }, 150);
  };
  window.addEventListener('resize', resizeHandler);
  cleanups.push(() => window.removeEventListener('resize', resizeHandler));

  _unbindFns = cleanups;
}

function _updateViewToggleButtons() {
  if (!_container) return;
  const listBtn = _container.querySelector('[data-action="fe-view-list"]');
  const gridBtn = _container.querySelector('[data-action="fe-view-grid"]');
  if (listBtn) listBtn.classList.toggle('c-btn--primary', _state.viewMode === 'list');
  if (gridBtn) gridBtn.classList.toggle('c-btn--primary', _state.viewMode === 'grid');
}

function _setupDragAndDrop(container) {
  // Simple drag-over highlight
  let dragCounter = 0;

  const dragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter++;
    container.classList.add('fe-file-container--drag-over');
  };

  const dragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter--;
    if (dragCounter === 0) {
      container.classList.remove('fe-file-container--drag-over');
    }
  };

  const dragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
  };

  const drop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter = 0;
    container.classList.remove('fe-file-container--drag-over');

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    // Upload files to current directory
    for (const file of files) {
      try {
        const text = await file.text();
        const targetPath = (_state.currentPath || _state.rootPath) + '/' + file.name;
        await writeFile(targetPath, text);
      } catch (err) {
        console.error('[FileExplorer] upload failed:', file.name, err);
      }
    }

    // Refresh
    navigateTo(_state.currentPath || _state.rootPath);
  };

  container.addEventListener('dragenter', dragEnter);
  container.addEventListener('dragleave', dragLeave);
  container.addEventListener('dragover', dragOver);
  container.addEventListener('drop', drop);

  return () => {
    container.removeEventListener('dragenter', dragEnter);
    container.removeEventListener('dragleave', dragLeave);
    container.removeEventListener('dragover', dragOver);
    container.removeEventListener('drop', drop);
  };
}

/* ── Global Keybindings ────────────────────────────────────────────────────── */

function bindGlobalKeys() {
  const handler = (e) => {
    // F5 or Ctrl+R = refresh
    if (e.key === 'F5' || (e.key === 'r' && e.ctrlKey)) {
      e.preventDefault();
      navigateTo(_state.currentPath || _state.rootPath);
    }
  };
  document.addEventListener('keydown', handler);
  return () => document.removeEventListener('keydown', handler);
}

/* ── Page Lifecycle ────────────────────────────────────────────────────────── */

/**
 * Render the file explorer page HTML.
 * @param {Object} routeInfo - Route info from router
 * @returns {string} HTML string
 */
function render(routeInfo) {
  // Initialize state
  _state.rootPath = DEFAULT_ROOT;
  _state.currentPath = DEFAULT_ROOT;
  _state.breadcrumb = buildBreadcrumb(DEFAULT_ROOT);
  _state.expandedDirs = new Set();
  _state.isLoading = false;
  _state.hasError = false;
  _state.viewMode = 'list';

  return html`
    <div class="file-explorer">
      <style>
        /* ══════════════════════════════════════════════════════════════════
           File Explorer Styles
           ══════════════════════════════════════════════════════════════════ */

        .file-explorer {
          display: flex;
          flex-direction: column;
          height: 100%;
          background: var(--bg-secondary, #14161f);
          overflow: hidden;
        }

        /* ── Toolbar ────────────────────────────────────────────────────── */
        .fe-toolbar {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          border-bottom: 1px solid var(--border-subtle, #232635);
          background: var(--surface, #1e202b);
          flex-shrink: 0;
          flex-wrap: wrap;
        }

        .fe-toolbar__group {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .fe-toolbar__sep {
          width: 1px;
          height: 24px;
          background: var(--border, #2e3140);
          margin: 0 4px;
        }

        .fe-toolbar__path {
          flex: 1;
          font-size: 12px;
          color: var(--text-muted, #64748b);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          padding: 0 8px;
          font-family: var(--font-mono, 'JetBrains Mono', monospace);
          direction: rtl;
          text-align: right;
        }

        /* ── Breadcrumb ─────────────────────────────────────────────────── */
        .fe-breadcrumb {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 6px 12px;
          border-bottom: 1px solid var(--border-subtle, #232635);
          background: var(--bg-tertiary, #1a1c25);
          flex-shrink: 0;
          overflow-x: auto;
          scrollbar-width: thin;
        }

        .fe-breadcrumb::-webkit-scrollbar {
          height: 3px;
        }
        .fe-breadcrumb::-webkit-scrollbar-thumb {
          background: var(--border, #2e3140);
          border-radius: 2px;
        }

        .fe-breadcrumb__item {
          font-size: 12px;
          color: var(--text-secondary, #94a3b8);
          cursor: pointer;
          white-space: nowrap;
          padding: 2px 4px;
          border-radius: 3px;
          transition: all 120ms ease;
        }

        .fe-breadcrumb__item:hover {
          color: var(--text-primary, #e2e8f0);
          background: var(--surface-hover, #262836);
        }

        .fe-breadcrumb__item--active {
          color: var(--accent, #00f0ff);
          font-weight: 500;
          cursor: default;
        }

        .fe-breadcrumb__item--active:hover {
          background: transparent;
        }

        .fe-breadcrumb__sep {
          display: flex;
          align-items: center;
          color: var(--text-muted, #64748b);
          width: 14px;
          height: 14px;
          flex-shrink: 0;
        }

        .fe-breadcrumb__sep svg {
          width: 14px;
          height: 14px;
        }

        /* ── Body (split panel) ─────────────────────────────────────────── */
        .fe-body {
          display: grid;
          grid-template-columns: 260px 1fr;
          flex: 1;
          overflow: hidden;
        }

        /* ── Tree Panel ─────────────────────────────────────────────────── */
        .fe-tree-panel {
          display: flex;
          flex-direction: column;
          border-right: 1px solid var(--border, #2e3140);
          background: var(--bg-tertiary, #1a1c25);
          overflow: hidden;
        }

        .fe-tree-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 12px;
          border-bottom: 1px solid var(--border-subtle, #232635);
          font-size: 11px;
          font-weight: 600;
          color: var(--text-muted, #64748b);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          flex-shrink: 0;
        }

        .fe-tree {
          flex: 1;
          overflow-y: auto;
          padding: 4px 0;
          scrollbar-width: thin;
          scrollbar-color: var(--border, #2e3140) transparent;
        }

        .fe-tree::-webkit-scrollbar {
          width: 5px;
        }
        .fe-tree::-webkit-scrollbar-thumb {
          background: var(--border, #2e3140);
          border-radius: 3px;
        }

        .fe-tree-item {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 4px 12px;
          font-size: 12px;
          color: var(--text-secondary, #94a3b8);
          cursor: pointer;
          transition: all 80ms ease;
          user-select: none;
          position: relative;
        }

        .fe-tree-item:hover {
          background: var(--surface, #1e202b);
          color: var(--text-primary, #e2e8f0);
        }

        .fe-tree-item--selected {
          background: var(--accent-muted, rgba(0, 240, 255, 0.12));
          color: var(--accent, #00f0ff);
        }

        .fe-tree-item__icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 16px;
          height: 16px;
          flex-shrink: 0;
          color: currentColor;
          opacity: 0.7;
        }

        .fe-tree-item__icon svg {
          width: 16px;
          height: 16px;
        }

        .fe-tree-item__label {
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .fe-tree-item__chevron {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 14px;
          height: 14px;
          flex-shrink: 0;
          transition: transform 120ms ease;
          opacity: 0.5;
        }

        .fe-tree-item__chevron svg {
          width: 12px;
          height: 12px;
        }

        .fe-tree-item__chevron--open {
          transform: rotate(0deg);
        }

        .fe-tree-item__chevron:not(.fe-tree-item__chevron--open) {
          transform: rotate(-90deg);
        }

        .fe-tree-item--root {
          font-weight: 600;
          color: var(--text-primary, #e2e8f0);
          border-bottom: 1px solid var(--border-subtle, #232635);
          padding-bottom: 6px;
          margin-bottom: 2px;
        }

        .fe-tree__error {
          padding: 16px;
          text-align: center;
          color: var(--danger, #ef4444);
          font-size: 12px;
        }

        /* ── Content Panel ──────────────────────────────────────────────── */
        .fe-content-panel {
          display: flex;
          flex-direction: column;
          overflow: hidden;
          background: var(--bg-secondary, #14161f);
        }

        /* ── File Toolbar ───────────────────────────────────────────────── */
        .fe-file-toolbar {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 12px;
          border-bottom: 1px solid var(--border-subtle, #232635);
          flex-shrink: 0;
        }

        .fe-file-search {
          position: relative;
          flex: 1;
          max-width: 280px;
        }

        .fe-file-search__icon {
          position: absolute;
          left: 8px;
          top: 50%;
          transform: translateY(-50%);
          display: flex;
          align-items: center;
          color: var(--text-muted, #64748b);
          width: 14px;
          height: 14px;
          pointer-events: none;
        }

        .fe-file-search__icon svg {
          width: 14px;
          height: 14px;
        }

        .fe-file-search__input {
          width: 100%;
          height: 28px;
          padding: 0 8px 0 28px;
          font-size: 12px;
          color: var(--text-primary, #e2e8f0);
          background: var(--surface, #1e202b);
          border: 1px solid var(--border, #2e3140);
          border-radius: 4px;
          outline: none;
          transition: border-color 120ms ease;
        }

        .fe-file-search__input:focus {
          border-color: var(--accent, #00f0ff);
          box-shadow: 0 0 0 1px var(--accent, #00f0ff);
        }

        .fe-file-search__input::placeholder {
          color: var(--text-muted, #64748b);
        }

        .fe-file-actions {
          display: flex;
          gap: 2px;
          flex-shrink: 0;
        }

        /* ── File List (list view) ──────────────────────────────────────── */
        .fe-file-list {
          flex: 1;
          overflow-y: auto;
          scrollbar-width: thin;
          scrollbar-color: var(--border, #2e3140) transparent;
        }

        .fe-file-list::-webkit-scrollbar {
          width: 5px;
        }
        .fe-file-list::-webkit-scrollbar-thumb {
          background: var(--border, #2e3140);
          border-radius: 3px;
        }

        .fe-file-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 12px;
          cursor: pointer;
          transition: all 80ms ease;
          user-select: none;
        }

        .fe-file-item:hover {
          background: var(--surface, #1e202b);
        }

        .fe-file-item--selected {
          background: var(--accent-muted, rgba(0, 240, 255, 0.12));
        }

        .fe-file-item--list {
          border-bottom: 1px solid var(--border-subtle, #232635);
        }

        .fe-file-item__icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 18px;
          height: 18px;
          flex-shrink: 0;
          color: var(--text-muted, #64748b);
        }

        .fe-file-item__icon svg {
          width: 18px;
          height: 18px;
        }

        .fe-file-item__name {
          flex: 1;
          font-size: 13px;
          color: var(--text-primary, #e2e8f0);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .fe-file-item__meta {
          font-size: 11px;
          color: var(--text-muted, #64748b);
          white-space: nowrap;
          flex-shrink: 0;
        }

        .fe-file-item__size {
          width: 80px;
          text-align: right;
        }

        .fe-file-item__date {
          width: 80px;
          text-align: right;
        }

        /* ── Grid View ──────────────────────────────────────────────────── */
        .fe-file-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
          gap: 8px;
          padding: 12px;
          flex: 1;
          overflow-y: auto;
          align-content: start;
          scrollbar-width: thin;
          scrollbar-color: var(--border, #2e3140) transparent;
        }

        .fe-file-grid::-webkit-scrollbar {
          width: 5px;
        }
        .fe-file-grid::-webkit-scrollbar-thumb {
          background: var(--border, #2e3140);
          border-radius: 3px;
        }

        .fe-file-item--grid {
          flex-direction: column;
          align-items: center;
          text-align: center;
          padding: 12px 8px;
          border-radius: 6px;
          border: 1px solid transparent;
          gap: 6px;
        }

        .fe-file-item--grid:hover {
          background: var(--surface, #1e202b);
          border-color: var(--border, #2e3140);
        }

        .fe-file-item--grid.fe-file-item--selected {
          background: var(--accent-muted, rgba(0, 240, 255, 0.12));
          border-color: var(--accent, #00f0ff);
        }

        .fe-file-item__icon--grid {
          width: 32px;
          height: 32px;
        }

        .fe-file-item__icon--grid svg {
          width: 28px;
          height: 28px;
        }

        .fe-file-item__name--grid {
          font-size: 11px;
          line-height: 1.3;
          max-height: 2.6em;
          overflow: hidden;
          word-break: break-all;
        }

        /* ── Empty State ────────────────────────────────────────────────── */
        .fe-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 48px 24px;
          text-align: center;
          color: var(--text-muted, #64748b);
        }

        .fe-empty__icon {
          opacity: 0.4;
          margin-bottom: 12px;
        }

        .fe-empty__text {
          font-size: 13px;
        }

        /* ── Preview Panel ──────────────────────────────────────────────── */
        .fe-preview {
          border-top: 1px solid var(--border, #2e3140);
          flex: 1;
          overflow-y: auto;
          background: var(--bg-primary, #0f111a);
          scrollbar-width: thin;
          scrollbar-color: var(--border, #2e3140) transparent;
        }

        .fe-preview::-webkit-scrollbar {
          width: 5px;
        }
        .fe-preview::-webkit-scrollbar-thumb {
          background: var(--border, #2e3140);
          border-radius: 3px;
        }

        .fe-preview__empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          padding: 32px;
          color: var(--text-muted, #64748b);
          gap: 8px;
        }

        .fe-preview__empty-icon {
          opacity: 0.3;
        }

        .fe-preview__empty-text {
          font-size: 12px;
        }

        .fe-preview__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 16px;
          border-bottom: 1px solid var(--border-subtle, #232635);
          background: var(--surface, #1e202b);
          flex-shrink: 0;
        }

        .fe-preview__filename {
          font-size: 13px;
          font-weight: 500;
          color: var(--text-primary, #e2e8f0);
          font-family: var(--font-mono, 'JetBrains Mono', monospace);
        }

        .fe-preview__filemeta {
          font-size: 11px;
          color: var(--text-muted, #64748b);
        }

        .fe-preview__code {
          padding: 0;
        }

        .fe-preview__code pre {
          margin: 0;
          padding: 16px;
          background: transparent;
          border: none;
          border-radius: 0;
          font-size: 12px;
          line-height: 1.6;
          overflow-x: auto;
          color: var(--text-primary, #e2e8f0);
        }

        .fe-preview__code code {
          background: transparent;
          border: none;
          padding: 0;
          color: inherit;
          font-size: inherit;
        }

        /* Syntax highlighting colors */
        .hl-keyword  { color: #ff7b72; }  /* Reddish */
        .hl-string   { color: #a5d6ff; }  /* Light blue */
        .hl-number   { color: #79c0ff; }  /* Blue */
        .hl-comment  { color: #8b949e; font-style: italic; }  /* Gray */
        .hl-function { color: #d2a8ff; }  /* Purple */

        .fe-preview__image {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          min-height: 200px;
        }

        .fe-preview__image img {
          border-radius: 4px;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        }

        .fe-preview__error {
          color: var(--danger, #ef4444);
          font-size: 13px;
        }

        .fe-preview__metadata {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .fe-preview__meta-row {
          display: flex;
          align-items: center;
          gap: 12px;
          font-size: 12px;
        }

        .fe-preview__meta-label {
          color: var(--text-muted, #64748b);
          width: 100px;
          flex-shrink: 0;
        }

        .fe-preview__meta-value {
          color: var(--text-secondary, #94a3b8);
        }

        .fe-preview__meta-value--path {
          font-family: var(--font-mono, 'JetBrains Mono', monospace);
          font-size: 11px;
          word-break: break-all;
        }

        /* ── Drag Over State ────────────────────────────────────────────── */
        .fe-file-container--drag-over {
          background: var(--accent-muted, rgba(0, 240, 255, 0.06));
          outline: 2px dashed var(--accent, #00f0ff);
          outline-offset: -2px;
        }

        /* ── Loading / Error States ─────────────────────────────────────── */
        .fe-skeleton {
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding: 24px;
        }

        .fe-skeleton__toolbar {
          display: flex;
          gap: 8px;
        }

        .fe-skeleton__body {
          display: grid;
          grid-template-columns: 220px 1fr;
          gap: 16px;
        }

        .fe-skeleton__tree {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .fe-skeleton__preview {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .fe-error {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 48px;
          text-align: center;
          gap: 12px;
        }

        .fe-error__icon {
          color: var(--danger, #ef4444);
          opacity: 0.6;
        }

        .fe-error__title {
          font-size: 16px;
          font-weight: 600;
          color: var(--text-primary, #e2e8f0);
        }

        .fe-error__desc {
          font-size: 13px;
          color: var(--text-secondary, #94a3b8);
          max-width: 400px;
          line-height: 1.6;
        }

        /* ── Responsive ─────────────────────────────────────────────────── */
        @media (max-width: 768px) {
          .fe-body {
            grid-template-columns: 1fr;
          }
          .fe-tree-panel {
            display: none;
          }
          .fe-file-grid {
            grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
          }
        }
      </style>

      <!-- Toolbar -->
      <div class="fe-toolbar">
        <div class="fe-toolbar__group">
          <button class="c-btn c-btn--icon c-btn--sm" data-action="fe-new-file"
                  title="New File" aria-label="New File">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" width="14" height="14"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="12" y1="12" x2="12" y2="18"/>
              <line x1="9" y1="15" x2="15" y2="15"/>
            </svg>
          </button>
          <button class="c-btn c-btn--icon c-btn--sm" data-action="fe-new-folder"
                  title="New Folder" aria-label="New Folder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" width="14" height="14"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              <line x1="12" y1="11" x2="12" y2="17"/>
              <line x1="9" y1="14" x2="15" y2="14"/>
            </svg>
          </button>
          <button class="c-btn c-btn--icon c-btn--sm" data-action="fe-refresh"
                  title="Refresh" aria-label="Refresh">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" width="14" height="14"
                 stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
        </div>

        <div class="fe-toolbar__path" id="fe-current-path">${_escapeHtml(DEFAULT_ROOT)}</div>
      </div>

      <!-- Breadcrumb -->
      <div class="fe-breadcrumb" id="fe-breadcrumb">
        <span class="fe-breadcrumb__item fe-breadcrumb__item--active"
              data-breadcrumb-path="${_escapeHtml(DEFAULT_ROOT)}">
          Project Root
        </span>
      </div>

      <!-- Body -->
      <div class="fe-body">
        <!-- Tree Panel -->
        <div class="fe-tree-panel">
          <div class="fe-tree-header">
            <span>Files</span>
            <button class="c-btn c-btn--icon c-btn--sm" data-action="fe-refresh"
                    title="Refresh" aria-label="Refresh">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" width="12" height="12"
                   stroke-linecap="round" stroke-linejoin="round">
                <polyline points="23 4 23 10 17 10"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
          </div>
          <div class="fe-tree" id="fe-tree">
            <div style="padding: 16px; color: var(--text-muted, #64748b); font-size: 12px; text-align: center;">
              Loading file tree…
            </div>
          </div>
        </div>

        <!-- Content Panel -->
        <div class="fe-content-panel" id="fe-content-panel">
          <!-- File list rendered dynamically -->
        </div>
      </div>

      <!-- Preview Panel -->
      <div class="fe-preview" id="fe-preview">
        <div class="fe-preview__empty">
          <div class="fe-preview__empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.5" width="36" height="36"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <div class="fe-preview__empty-text">Select a file to preview</div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Mount the file explorer page.
 * Initializes state, renders tree and content, binds events.
 * @param {Element} container - The page container
 */
async function mount(container) {
  _container = container;
  _isDestroyed = false;

  // Initialize rendering
  renderBreadcrumb();
  renderContent();
  renderPreview();

  // Load tree
  await renderTree();

  // Navigate to root for content
  await navigateTo(_state.rootPath);

  // Bind events
  bindEvents();

  // Bind global keys
  const keyCleanup = bindGlobalKeys();
  _unbindFns.push(keyCleanup);
}

/**
 * Destroy the file explorer page.
 * Cleans up all state, event listeners, and DOM references.
 */
function destroy() {
  _isDestroyed = true;

  // Run cleanup functions
  for (const fn of _unbindFns) {
    try { fn(); } catch (e) { /* ignore */ }
  }
  _unbindFns = [];

  // Clear timers
  if (_searchTimer) clearTimeout(_searchTimer);
  if (_resizeTimer) clearTimeout(_resizeTimer);

  // Reset state
  _state = {
    currentPath: '',
    entries: [],
    selectedPath: null,
    selectedEntry: null,
    fileContent: null,
    fileInfo: null,
    isLoading: false,
    hasError: false,
    errorMessage: '',
    viewMode: 'list',
    searchQuery: '',
    expandedDirs: new Set(),
    breadcrumb: [],
    isDragging: false,
    previewType: null,
    rootPath: DEFAULT_ROOT,
  };

  _container = null;
}

/* ── Exports ─────────────────────────────────────────────────────────────── */

export default {
  render,
  mount,
  destroy,
};
