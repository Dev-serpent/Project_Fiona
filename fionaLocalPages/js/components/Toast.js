/* ==========================================================================
   Toast.js — Notification Toast System
   ==========================================================================
   Singleton notification toast system that stacks from the top-right
   corner.  Supports info, success, warning, and danger types with
   auto-dismiss (default 5s), manual dismiss, queue management (max 5
   visible), and slide-in/slide-out animation.

   Usage:
     import { toast } from './Toast.js';

     toast.showToast('success', 'Saved!', 'Your changes were saved.', 4000);
     toast.showToast('error', 'Error', 'Something went wrong.');
     toast.dismissAll();
   ========================================================================== */

import { html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  container: 'c-toast-container',
  toast: 'c-toast',
  exiting: 'c-toast--exiting',
  icon: 'c-toast__icon',
  content: 'c-toast__content',
  title: 'c-toast__title',
  message: 'c-toast__message',
  dismiss: 'c-toast__dismiss',
  progress: 'c-toast__progress',
};

/** Maximum number of visible toasts at once */
const MAX_VISIBLE = 5;

/** Default auto-dismiss duration in ms */
const DEFAULT_DURATION = 5000;

/**
 * @typedef {'info'|'success'|'warning'|'danger'} ToastType
 */

/**
 * @typedef {Object} ToastOptions
 * @property {string} [title]
 * @property {string} message
 * @property {ToastType} [type='info']
 * @property {number} [duration=5000] - Auto-dismiss duration (0 = no dismiss)
 */

let _idCounter = 0;

/**
 * Generate a unique toast ID.
 * @returns {string}
 */
function _uid() {
  return `toast-${++_idCounter}-${Date.now().toString(36)}`;
}

/**
 * Create a toast notification system.
 *
 * @param {string|Element} container - CSS selector or element for the
 *        toast container.  If not provided, one is created in the body.
 * @returns {ToastSystem}
 */
export function createToastSystem(container) {
  /** @type {Element} */
  let _container;

  /** @type {Array<Object>} Active toast entries */
  let _toasts = [];

  /** @type {Map<string, number>} Timeout IDs for auto-dismiss */
  const _timeouts = new Map();

  /**
   * Resolve the container element, creating one if needed.
   * @returns {Element}
   */
  function _resolveContainer() {
    if (_container) return _container;

    if (container) {
      _container = typeof container === 'string'
        ? document.querySelector(container)
        : container;
    }

    if (!_container) {
      _container = document.createElement('div');
      _container.className = CSS.container;
      document.body.appendChild(_container);
    }

    return _container;
  }

  /**
   * Render all active toasts into the container.
   * @private
   */
  function _render() {
    const el = _resolveContainer();
    // Only show up to MAX_VISIBLE
    const visible = _toasts.slice(0, MAX_VISIBLE);

    el.innerHTML = visible.map((t) => html`
      <div class="${CSS.toast} ${CSS.toast}--${t.type}" data-toast-id="${t.id}">
        <div class="${CSS.icon}">${_getIcon(t.type)}</div>
        <div class="${CSS.content}">
          ${t.title ? html`<div class="${CSS.title}">${t.title}</div>` : ''}
          <div class="${CSS.message}">${t.message}</div>
        </div>
        <button class="${CSS.dismiss}" data-dismiss="${t.id}" aria-label="Dismiss">
          ${ICONS.close}
        </button>
        ${t.duration > 0 ? html`<div class="${CSS.progress}" style="animation-duration: ${t.duration}ms;"></div>` : ''}
      </div>
    `).join('');

    // Bind dismiss handlers
    el.querySelectorAll('[data-dismiss]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.dataset.dismiss;
        _dismiss(id);
      });
    });
  }

  /**
   * Set up auto-dismiss for a toast.
   * @param {string} id
   * @param {number} duration
   * @private
   */
  function _scheduleDismiss(id, duration) {
    if (duration <= 0) return;
    const timeoutId = setTimeout(() => {
      _dismiss(id);
    }, duration);
    _timeouts.set(id, timeoutId);
  }

  /**
   * Dismiss a toast by ID with exit animation.
   * @param {string} id
   * @private
   */
  function _dismiss(id) {
    // Clear timeout
    if (_timeouts.has(id)) {
      clearTimeout(_timeouts.get(id));
      _timeouts.delete(id);
    }

    // Start exit animation
    const el = _resolveContainer();
    const toastEl = el.querySelector(`[data-toast-id="${id}"]`);
    if (toastEl) {
      toastEl.classList.add(CSS.exiting);
      // Remove after animation
      setTimeout(() => {
        _toasts = _toasts.filter((t) => t.id !== id);
        _render();
      }, 250);
    } else {
      _toasts = _toasts.filter((t) => t.id !== id);
      _render();
    }
  }

  /**
   * Get the SVG icon for a toast type.
   * @param {ToastType} type
   * @returns {string}
   * @private
   */
  function _getIcon(type) {
    switch (type) {
      case 'success': return ICONS.success;
      case 'warning': return ICONS.warning;
      case 'danger':  return ICONS.error;
      default:        return ICONS.info;
    }
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Show a toast notification.
   *
   * @param {ToastType} type - 'info' | 'success' | 'warning' | 'danger'
   * @param {string} title - Toast title
   * @param {string} message - Toast body text
   * @param {number} [duration=5000] - Auto-dismiss ms (0 to disable)
   * @returns {string} Toast ID (for manual dismissal)
   */
  function showToast(type, title, message, duration) {
    const id = _uid();
    const t = duration !== 0 ? (duration || DEFAULT_DURATION) : 0;

    const entry = {
      id,
      type: type || 'info',
      title: title || '',
      message: message || '',
      duration: t,
    };

    _toasts = [entry, ..._toasts];
    _render();

    if (t > 0) {
      _scheduleDismiss(id, t);
    }

    return id;
  }

  /**
   * Dismiss a toast by its ID.
   * @param {string} id
   */
  function dismiss(id) {
    _dismiss(id);
  }

  /**
   * Dismiss all visible toasts immediately.
   */
  function dismissAll() {
    // Clear all timeouts
    for (const [id, timeoutId] of _timeouts) {
      clearTimeout(timeoutId);
    }
    _timeouts.clear();
    _toasts = [];
    _render();
  }

  /**
   * Get the current toast count.
   * @returns {number}
   */
  function count() {
    return _toasts.length;
  }

  // Render initial state (empty)
  _resolveContainer();
  _render();

  return {
    showToast,
    dismiss,
    dismissAll,
    count,
  };
}

/**
 * @typedef {Object} ToastSystem
 * @property {(type: ToastType, title: string, message: string, duration?: number) => string} showToast
 * @property {(id: string) => void} dismiss
 * @property {() => void} dismissAll
 * @property {() => number} count
 */

/**
 * Singleton toast system instance.
 * Import this and use directly:
 *   import { toast } from './Toast.js';
 *   toast.showToast('success', 'Done', 'Operation completed.');
 *
 * The container is auto-created as a child of document.body if one
 * does not already exist with class "c-toast-container".
 *
 * @type {ToastSystem}
 */
export const toast = createToastSystem();

export default toast;
