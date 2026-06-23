/* ==========================================================================
   SplitPanel.js — Resizable Split Panel
   ==========================================================================
   Creates a resizable split layout (horizontal or vertical) with a
   draggable splitter, configurable min/max pane sizes, collapse/expand
   buttons per pane, and optional size persistence via the store.

   Usage:
     import { createSplitPanel } from './SplitPanel.js';

     const panel = createSplitPanel('#container', 'horizontal', [300, null]);
     // The two panes are children of #container
     // null = fills remaining space

     panel.setSizes([200, 400]);
     panel.collapsePane(0);
     panel.destroy();
   ========================================================================== */

import { html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const HANDLE_SIZE = 6;

/**
 * @typedef {'horizontal'|'vertical'} SplitDirection
 */

/**
 * Create a resizable split panel.
 *
 * @param {string|Element} container - Parent container element. It should
 *        have exactly two child elements (the panes).
 * @param {SplitDirection} direction - 'horizontal' or 'vertical'
 * @param {Array<number|null>} [initialSizes] - Array of two sizes (px or null for flex).
 *        e.g. [300, null] means first pane is 300px, second fills the rest.
 * @param {Object} [options]
 * @param {number} [options.minSize=100] - Minimum pane size in px
 * @param {number} [options.maxSize] - Maximum pane size in px
 * @param {boolean} [options.collapsible=true] - Show collapse buttons
 * @param {Object} [options.store] - Store instance for persisting sizes
 * @param {string} [options.persistKey] - Store key for persisting sizes
 * @returns {SplitPanelAPI}
 */
export function createSplitPanel(container, direction, initialSizes, options = {}) {
  /** @type {Element} */
  let _container = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (!_container) {
    console.error('[SplitPanel] Container not found:', container);
    return null;
  }

  const _dir = direction || 'horizontal';
  const _minSize = options.minSize != null ? options.minSize : 100;
  const _maxSize = options.maxSize || Infinity;
  const _collapsible = options.collapsible !== false;
  const _store = options.store || null;
  const _persistKey = options.persistKey || null;

  /** @type {Array<number|null>} */
  let _sizes = initialSizes || [null, null];

  /** @type {Array<boolean>} */
  let _collapsed = [false, false];

  /** @type {Element|null} The splitter handle element */
  let _handleEl = null;

  /** @type {boolean} Whether the component is destroyed */
  let _destroyed = false;

  /* ── Persistence ─────────────────────────────────────────────────────── */

  /**
   * Persist current sizes to the store.
   * @private
   */
  function _persist() {
    if (_store && _persistKey) {
      _store.set(_persistKey, { sizes: _sizes, collapsed: _collapsed });
    }
  }

  /**
   * Load persisted sizes from the store.
   * @private
   */
  function _loadPersisted() {
    if (_store && _persistKey) {
      const saved = _store.get(_persistKey);
      if (saved) {
        _sizes = saved.sizes || _sizes;
        _collapsed = saved.collapsed || _collapsed;
      }
    }
  }

  /* ── Render ──────────────────────────────────────────────────────────── */

  /**
   * Set up the split panel layout.
   * @private
   */
  function _render() {
    if (_destroyed) return;

    const children = Array.from(_container.children);
    if (children.length < 2) {
      console.error('[SplitPanel] Container must have at least two children');
      return;
    }

    const pane0 = children[0];
    const pane1 = children[1];

    // Style the container
    _container.style.display = 'flex';
    _container.style.flexDirection = _dir === 'horizontal' ? 'row' : 'column';
    _container.style.overflow = 'hidden';
    _container.style.position = 'relative';

    // Style panes
    _applyPaneStyle(pane0, 0);
    _applyPaneStyle(pane1, 1);

    // Create or update splitter handle
    _ensureHandle(pane0, pane1);

    // Add collapse buttons
    if (_collapsible) {
      _ensureCollapseButtons(pane0, 0);
      _ensureCollapseButtons(pane1, 1);
    }
  }

  /**
   * Apply size/flex styling to a pane.
   * @param {Element} pane
   * @param {number} index
   * @private
   */
  function _applyPaneStyle(pane, index) {
    const isHorizontal = _dir === 'horizontal';
    const collapsed = _collapsed[index];
    const size = _sizes[index];

    pane.style.flex = 'none';
    pane.style.overflow = 'auto';
    pane.style.position = 'relative';

    if (collapsed) {
      pane.style[isHorizontal ? 'width' : 'height'] = '0px';
      pane.style.overflow = 'hidden';
      pane.style.minWidth = '0';
      pane.style.minHeight = '0';
    } else if (size != null) {
      pane.style[isHorizontal ? 'width' : 'height'] = `${size}px`;
      pane.style.flexShrink = '0';
      pane.style.minWidth = '0';
      pane.style.minHeight = '0';
    } else {
      // Flexible pane
      pane.style[isHorizontal ? 'width' : 'height'] = '';
      pane.style.flex = '1 1 0%';
      pane.style.minWidth = '0';
      pane.style.minHeight = '0';
    }

    pane.dataset.paneIndex = String(index);
  }

  /**
   * Create or update the splitter handle between two panes.
   * @param {Element} pane0
   * @param {Element} pane1
   * @private
   */
  function _ensureHandle(pane0, pane1) {
    // Remove old handle if exists
    if (_handleEl) {
      _handleEl.remove();
    }

    const isHorizontal = _dir === 'horizontal';
    const handle = document.createElement('div');
    handle.className = 'split-panel__handle';

    const handleStyle = {
      flexShrink: '0',
      position: 'relative',
      zIndex: '10',
      cursor: isHorizontal ? 'col-resize' : 'row-resize',
      background: 'var(--border-subtle)',
      transition: 'background var(--transition-fast)',
    };

    if (isHorizontal) {
      handle.style.width = `${HANDLE_SIZE}px`;
      handle.style.minWidth = `${HANDLE_SIZE}px`;
      handle.style.cursor = 'col-resize';
    } else {
      handle.style.height = `${HANDLE_SIZE}px`;
      handle.style.minHeight = `${HANDLE_SIZE}px`;
      handle.style.cursor = 'row-resize';
    }

    Object.assign(handle.style, handleStyle);

    // Hover effect
    handle.addEventListener('mouseenter', () => {
      handle.style.background = 'var(--accent)';
    });
    handle.addEventListener('mouseleave', () => {
      if (!handle.classList.contains('split-panel__handle--dragging')) {
        handle.style.background = 'var(--border-subtle)';
      }
    });

    // Drag handling
    _setupDrag(handle, pane0, pane1);

    // Insert handle after pane0
    pane0.after(handle);
    _handleEl = handle;
  }

  /**
   * Set up drag-to-resize on the handle.
   * @param {Element} handle
   * @param {Element} pane0
   * @param {Element} pane1
   * @private
   */
  function _setupDrag(handle, pane0, pane1) {
    let startPos = 0;
    let startSize0 = 0;
    let startSize1 = 0;

    const isHorizontal = _dir === 'horizontal';

    const onDragStart = (e) => {
      if (_collapsed[0] || _collapsed[1]) return;
      e.preventDefault();
      const pos = isHorizontal ? e.clientX : e.clientY;
      startPos = pos;
      startSize0 = isHorizontal ? pane0.offsetWidth : pane0.offsetHeight;
      startSize1 = isHorizontal ? pane1.offsetWidth : pane1.offsetHeight;
      handle.classList.add('split-panel__handle--dragging');
      handle.style.background = 'var(--accent)';

      document.addEventListener('mousemove', onDragMove);
      document.addEventListener('mouseup', onDragEnd);
      document.body.style.cursor = handle.style.cursor;
      document.body.style.userSelect = 'none';
    };

    const onDragMove = (e) => {
      const pos = isHorizontal ? e.clientX : e.clientY;
      const delta = pos - startPos;
      let newSize0 = startSize0 + delta;
      let newSize1 = startSize1 - delta;

      // Clamp min/max
      const totalSize = isHorizontal
        ? _container.offsetWidth - HANDLE_SIZE
        : _container.offsetHeight - HANDLE_SIZE;

      newSize0 = Math.max(_minSize, Math.min(_maxSize, newSize0));
      newSize1 = Math.max(_minSize, Math.min(_maxSize, newSize1));

      // Don't exceed total
      if (newSize0 + newSize1 > totalSize) {
        const excess = newSize0 + newSize1 - totalSize;
        newSize0 -= excess / 2;
        newSize1 -= excess / 2;
      }

      _sizes[0] = Math.round(newSize0);
      _sizes[1] = Math.round(newSize1);
      _applyPaneStyle(pane0, 0);
      _applyPaneStyle(pane1, 1);
    };

    const onDragEnd = () => {
      handle.classList.remove('split-panel__handle--dragging');
      handle.style.background = 'var(--border-subtle)';
      document.removeEventListener('mousemove', onDragMove);
      document.removeEventListener('mouseup', onDragEnd);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      _persist();
    };

    handle.addEventListener('mousedown', onDragStart);
  }

  /**
   * Add collapse/expand buttons to a pane.
   * @param {Element} pane
   * @param {number} index
   * @private
   */
  function _ensureCollapseButtons(pane, index) {
    const btn = document.createElement('button');
    btn.className = 'split-panel__collapse-btn';
    btn.setAttribute('data-collapse-pane', String(index));
    btn.title = _collapsed[index] ? 'Expand pane' : 'Collapse pane';

    const style = {
      position: 'absolute',
      top: '8px',
      [index === 0 ? 'right' : 'left']: '8px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '24px',
      height: '24px',
      borderRadius: 'var(--radius-sm)',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      color: 'var(--text-muted)',
      cursor: 'pointer',
      zIndex: '5',
      transition: 'all var(--transition-fast)',
      opacity: '0.6',
    };
    Object.assign(btn.style, style);

    btn.innerHTML = index === 0
      ? (_dir === 'horizontal' ? ICONS.chevronLeft : ICONS.chevronUp)
      : (_dir === 'horizontal' ? ICONS.chevronRight : ICONS.chevronDown);

    btn.addEventListener('mouseenter', () => {
      btn.style.opacity = '1';
      btn.style.background = 'var(--surface-hover)';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.opacity = '0.6';
      btn.style.background = 'var(--surface)';
    });

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleCollapse(index);
    });

    // Only add if not already present
    if (!pane.querySelector('[data-collapse-pane]')) {
      pane.style.position = 'relative';
      pane.appendChild(btn);
    }
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Collapse or expand a pane.
   * @param {number} index - 0 or 1
   * @param {boolean} [collapsed] - If not provided, toggle
   */
  function toggleCollapse(index, collapsed) {
    if (_destroyed) return;
    const newState = collapsed !== undefined ? collapsed : !_collapsed[index];
    _collapsed[index] = newState;
    _render();
    _persist();
  }

  /**
   * Get the current pane sizes.
   * @returns {Array<number|null>}
   */
  function getSizes() {
    return [..._sizes];
  }

  /**
   * Set pane sizes.
   * @param {Array<number|null>} sizes
   */
  function setSizes(sizes) {
    if (_destroyed) return;
    _sizes = [...sizes];
    _render();
    _persist();
  }

  /**
   * Check if a pane is collapsed.
   * @param {number} index
   * @returns {boolean}
   */
  function isCollapsed(index) {
    return _collapsed[index] === true;
  }

  /**
   * Update the split direction.
   * @param {SplitDirection} newDirection
   */
  function setDirection(newDirection) {
    if (_destroyed) return;
    _dir = newDirection;
    _render();
  }

  /**
   * Remove the split panel, resetting child styles.
   */
  function destroy() {
    _destroyed = true;
    const children = Array.from(_container.children);
    children.forEach((child) => {
      child.style.cssText = '';
    });
    if (_handleEl) {
      _handleEl.remove();
      _handleEl = null;
    }
  }

  // Load persisted state and render
  _loadPersisted();
  _render();

  return {
    toggleCollapse,
    getSizes,
    setSizes,
    isCollapsed,
    setDirection,
    destroy,
  };
}

/**
 * @typedef {Object} SplitPanelAPI
 * @property {(index: number, collapsed?: boolean) => void} toggleCollapse
 * @property {() => Array<number|null>} getSizes
 * @property {(sizes: Array<number|null>) => void} setSizes
 * @property {(index: number) => boolean} isCollapsed
 * @property {(direction: SplitDirection) => void} setDirection
 * @property {() => void} destroy
 */

export default createSplitPanel;
