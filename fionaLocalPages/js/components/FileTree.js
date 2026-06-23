/* ==========================================================================
   FileTree.js — File System Tree Browser
   ==========================================================================
   Displays a hierarchical file/folder tree with expand/collapse animation,
   file icons by extension, context menu, lazy loading children via a
   fetch callback, drag-and-drop reorder, and current file highlighting.

   Usage:
     import { createFileTree } from './FileTree.js';

     const tree = createFileTree('#file-tree', '/home/user/project', {
       fetchChildren: async (path) => {
         const res = await api.get('/api/files?path=' + encodeURIComponent(path));
         return res.items;
       },
       onSelect: (path, entry) => console.log('Selected:', path),
     });

     tree.navigateTo('/home/user/project/src');
     tree.destroy();
   ========================================================================== */

import { html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  tree: 'c-list',
  item: 'c-list__item',
  itemActive: 'c-list__item--active',
  disabled: 'c-list__item--disabled',
};

/**
 * @typedef {Object} FileEntry
 * @property {string} name - File or directory name
 * @property {string} path - Full path
 * @property {'file'|'directory'} type - Entry type
 * @property {number} [size] - File size in bytes
 * @property {string} [modified] - Last modified date
 * @property {FileEntry[]} [children] - Preloaded children (optional)
 * @property {boolean} [hasChildren] - Whether dir has children (for lazy loading)
 */

/**
 * Create a file tree browser.
 *
 * @param {string|Element} container - Container element
 * @param {string} rootPath - Root directory path
 * @param {Object} callbacks
 * @param {Function} callbacks.fetchChildren - async (path: string) => FileEntry[]
 * @param {Function} [callbacks.onSelect] - (path: string, entry: FileEntry) => void
 * @param {Function} [callbacks.onDrop] - (path: string, targetPath: string) => void
 * @param {Function} [callbacks.getContextMenuItems] - (entry: FileEntry) => Array
 * @param {Object} [options]
 * @param {boolean} [options.showSearch=true] - Show search/filter input
 * @returns {FileTreeAPI}
 */
export function createFileTree(container, rootPath, callbacks, options = {}) {
  /** @type {Element} */
  let _container = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (!_container) {
    console.error('[FileTree] Container not found:', container);
    return null;
  }

  /** @type {string} */
  let _rootPath = rootPath || '';

  /** @type {Function} */
  const _fetchChildren = callbacks.fetchChildren || (async () => []);

  /** @type {Function|null} */
  const _onSelect = callbacks.onSelect || null;

  /** @type {Function|null} */
  const _onDrop = callbacks.onDrop || null;

  /** @type {Function|null} */
  const _getContextMenuItems = callbacks.getContextMenuItems || null;

  /** @type {boolean} */
  const _showSearch = options.showSearch !== false;

  /** @type {Map<string, FileEntry[]>} Cached children per directory path */
  const _cache = new Map();

  /** @type {Set<string>} Expanded directory paths */
  const _expanded = new Set();

  /** @type {string|null} Currently selected (highlighted) path */
  let _selectedPath = null;

  /** @type {string} Search/filter text */
  let _searchText = '';

  /** @type {boolean} */
  let _loading = false;

  /** @type {boolean} */
  let _destroyed = false;

  /**
   * Conditionally build a className string.
   * @param {...*} args
   * @returns {string}
   */
  function classNames(...args) {
    const classes = [];
    for (const arg of args) {
      if (!arg) continue;
      if (typeof arg === 'string') {
        classes.push(arg);
      } else if (Array.isArray(arg)) {
        classes.push(classNames(...arg));
      } else if (typeof arg === 'object') {
        for (const [key, value] of Object.entries(arg)) {
          if (value) classes.push(key);
        }
      }
    }
    return classes.join(' ');
  }

  /* ── Data Loading ────────────────────────────────────────────────────── */

  /**
   * Load children for a directory, using cache if available.
   * @param {string} dirPath
   * @returns {Promise<FileEntry[]>}
   * @private
   */
  async function _loadChildren(dirPath) {
    if (_cache.has(dirPath)) {
      return _cache.get(dirPath);
    }
    try {
      const children = await _fetchChildren(dirPath);
      _cache.set(dirPath, children || []);
      return _cache.get(dirPath);
    } catch (err) {
      console.error(`[FileTree] Failed to load ${dirPath}:`, err);
      return [];
    }
  }

  /* ── Render ──────────────────────────────────────────────────────────── */

  async function _render() {
    if (_destroyed) return;

    _loading = true;

    // Load root if not cached
    if (!_cache.has(_rootPath)) {
      await _loadChildren(_rootPath);
    }

    _loading = false;

    const rootChildren = _cache.get(_rootPath) || [];

    _container.innerHTML = html`
      ${_showSearch ? html`
        <div style="padding: 8px 12px; border-bottom: 1px solid var(--border-subtle);">
          <div class="c-input-wrapper">
            <span class="c-input-wrapper__icon c-input-wrapper__icon--left">${ICONS.search}</span>
            <input type="text" class="c-input c-input--sm c-input--icon-left"
                   id="file-tree-search"
                   placeholder="Search files…"
                   value="${_searchText}"
                   style="height: 28px; font-size: 12px;" />
          </div>
        </div>
      ` : ''}

      <div class="${CSS.tree}" id="file-tree-items">
        ${_loading ? html`
          <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 12px;">
            Loading…
          </div>
        ` : _renderEntries(rootChildren, 0)}
      </div>
    `;

    _bindEvents();
  }

  /**
   * Render a list of file entries at a given depth.
   * @param {FileEntry[]} entries
   * @param {number} depth
   * @param {string} [parentPath]
   * @returns {string}
   * @private
   */
  function _renderEntries(entries, depth, parentPath) {
    const filtered = _searchText
      ? entries.filter((e) => e.name.toLowerCase().includes(_searchText.toLowerCase()))
      : entries;

    return filtered.map((entry) => {
      const isDir = entry.type === 'directory';
      const isExpanded = _expanded.has(entry.path);
      const isSelected = entry.path === _selectedPath;
      const icon = isDir
        ? (isExpanded ? ICONS.folderOpen : ICONS.folder)
        : _getFileIcon(entry.name);

      return html`
        <div data-path="${entry.path}"
             data-type="${entry.type}"
             class="${CSS.item} ${classNames(isSelected ? CSS.itemActive : '',
                                                  entry.disabled ? CSS.disabled : '')}"
             style="padding-left: ${12 + depth * 20}px;"
             draggable="true">
          <span class="nav-item__icon" style="width: 16px; height: 16px;">
            ${icon}
          </span>
          <span class="nav-item__label">${entry.name}</span>
          ${isDir ? html`
            <span class="c-list__item-chevron" style="margin-left: auto;
                 transition: transform var(--transition-fast); font-size: 12px;">
              ${isExpanded ? ICONS.chevronDown : ICONS.chevronRight}
            </span>
          ` : ''}
        </div>
        ${isDir && isExpanded && _cache.has(entry.path)
          ? _renderEntries(_cache.get(entry.path) || [], depth + 1, entry.path)
          : ''}
      `;
    }).join('');
  }

  /* ── Events ──────────────────────────────────────────────────────────── */

  function _bindEvents() {
    // Item click: select or expand/collapse
    _container.querySelectorAll(`.${CSS.item}`).forEach((el) => {
      el.addEventListener('click', async (e) => {
        const path = el.dataset.path;
        const type = el.dataset.type;
        if (!path) return;

        // Select
        _selectedPath = path;
        _highlightActive();
        if (_onSelect) _onSelect(path, { name: path.split('/').pop(), path, type });

        // Expand/collapse directories
        if (type === 'directory') {
          if (_expanded.has(path)) {
            _expanded.delete(path);
          } else {
            _expanded.add(path);
            if (!_cache.has(path)) {
              await _loadChildren(path);
            }
          }
          _reRenderTree();
        }
      });
    });

    // Context menu
    _container.querySelectorAll(`.${CSS.item}`).forEach((el) => {
      el.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const path = el.dataset.path;
        const type = el.dataset.type;
        const entry = _findEntry(path);

        if (_getContextMenuItems) {
          const items = _getContextMenuItems(entry || { name: path, path, type });
          if (items && items.length > 0) {
            import('./ContextMenu.js').then(({ contextMenu }) => {
              contextMenu.showContextMenu(e.clientX, e.clientY, items);
            });
          }
        }
      });
    });

    // Drag and drop
    if (_onDrop) {
      let dragPath = null;

      _container.querySelectorAll(`.${CSS.item}`).forEach((el) => {
        el.addEventListener('dragstart', (e) => {
          dragPath = el.dataset.path;
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', dragPath);
          el.style.opacity = '0.5';
        });

        el.addEventListener('dragend', () => {
          el.style.opacity = '';
          dragPath = null;
        });

        el.addEventListener('dragover', (e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = 'move';
          el.style.background = 'var(--accent-muted)';
        });

        el.addEventListener('dragleave', () => {
          el.style.background = '';
        });

        el.addEventListener('drop', async (e) => {
          e.preventDefault();
          el.style.background = '';
          const targetPath = el.dataset.path;
          if (dragPath && targetPath && dragPath !== targetPath) {
            await _onDrop(dragPath, targetPath);
            // Refresh the tree
            _cache.clear();
            _render();
          }
        });
      });
    }

    // Search input
    const searchInput = _container.querySelector('#file-tree-search');
    if (searchInput) {
      let timer;
      searchInput.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          _searchText = searchInput.value;
          _reRenderTree();
        }, 200);
      });
    }
  }

  /**
   * Highlight the active item and remove highlights from others.
   * @private
   */
  function _highlightActive() {
    _container.querySelectorAll(`.${CSS.item}`).forEach((el) => {
      el.classList.toggle(CSS.itemActive, el.dataset.path === _selectedPath);
    });
  }

  /**
   * Re-render just the tree body without destroying and recreating events.
   * @private
   */
  function _reRenderTree() {
    const itemsEl = _container.querySelector('#file-tree-items');
    if (!itemsEl) return;

    const rootChildren = _cache.get(_rootPath) || [];
    itemsEl.innerHTML = _renderEntries(rootChildren, 0);
    _bindEvents();
  }

  /**
   * Get the appropriate file icon by extension.
   * @param {string} filename
   * @returns {string}
   * @private
   */
  function _getFileIcon(filename) {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'js':
      case 'ts':
      case 'jsx':
      case 'tsx':
        return ICONS.fileCode;
      case 'json':
        return ICONS.fileJson;
      case 'md':
      case 'txt':
        return ICONS.fileText;
      default:
        return ICONS.file;
    }
  }

  /**
   * Find an entry by path in the cache.
   * @param {string} path
   * @returns {FileEntry|null}
   * @private
   */
  function _findEntry(path) {
    for (const [, children] of _cache) {
      const found = children.find((c) => c.path === path);
      if (found) return found;
    }
    return null;
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Navigate to (expand) a given path in the tree.
   * @param {string} path
   */
  async function navigateTo(path) {
    if (_destroyed) return;

    // Expand all parent directories
    const parts = path.replace(_rootPath, '').split('/').filter(Boolean);
    let currentPath = _rootPath;

    for (const part of parts) {
      currentPath += '/' + part;
      _expanded.add(currentPath);
      if (!_cache.has(currentPath)) {
        await _loadChildren(currentPath);
      }
    }

    _selectedPath = path;
    await _render();
    if (_onSelect) _onSelect(path, _findEntry(path) || { name: path.split('/').pop(), path, type: 'file' });
  }

  /**
   * Refresh the tree (clear cache and reload from root).
   */
  async function refresh() {
    if (_destroyed) return;
    _cache.clear();
    await _render();
  }

  /**
   * Set the search/filter text.
   * @param {string} text
   */
  function setSearch(text) {
    _searchText = text || '';
    _reRenderTree();
  }

  /**
   * Expand all directories recursively.
   */
  async function expandAll() {
    if (_destroyed) return;
    await _expandRecursive(_rootPath);
    await _render();
  }

  /**
   * Recursively expand directories.
   * @param {string} dirPath
   * @private
   */
  async function _expandRecursive(dirPath) {
    _expanded.add(dirPath);
    const children = await _loadChildren(dirPath);
    for (const child of children) {
      if (child.type === 'directory') {
        await _expandRecursive(child.path);
      }
    }
  }

  /**
   * Collapse all directories.
   */
  function collapseAll() {
    if (_destroyed) return;
    _expanded.clear();
    _reRenderTree();
  }

  /**
   * Get the currently selected path.
   * @returns {string|null}
   */
  function getSelectedPath() {
    return _selectedPath;
  }

  /**
   * Manually set children for a path in the cache.
   * @param {string} dirPath
   * @param {FileEntry[]} children
   */
  function setChildren(dirPath, children) {
    _cache.set(dirPath, children);
    _reRenderTree();
  }

  /**
   * Remove the tree from the DOM.
   */
  function destroy() {
    _destroyed = true;
    _container.innerHTML = '';
    _cache.clear();
    _expanded.clear();
  }

  // Initial render
  _render();

  return {
    navigateTo,
    refresh,
    setSearch,
    expandAll,
    collapseAll,
    getSelectedPath,
    setChildren,
    destroy,
  };
}

/**
 * @typedef {Object} FileTreeAPI
 * @property {(path: string) => Promise<void>} navigateTo
 * @property {() => Promise<void>} refresh
 * @property {(text: string) => void} setSearch
 * @property {() => Promise<void>} expandAll
 * @property {() => void} collapseAll
 * @property {() => string|null} getSelectedPath
 * @property {(dirPath: string, children: FileEntry[]) => void} setChildren
 * @property {() => void} destroy
 */

export default createFileTree;
