/* ==========================================================================
   Modal.js — Modal Dialog System
   ==========================================================================
   Stackable modal dialog system with multiple sizes, focus trapping,
   backdrop click-to-close, Escape key support, and promise-based API.

   Usage:
     import { modal } from './Modal.js';

     const result = await modal.showModal({
       title: 'Confirm',
       content: '<p>Are you sure?</p>',
       size: 'sm',
       buttons: [
         { label: 'Cancel', value: 'cancel', variant: 'ghost' },
         { label: 'Delete', value: 'delete', variant: 'danger' },
       ],
     });
     console.log('User clicked:', result);
   ========================================================================== */

import { BaseComponent, html } from './BaseComponent.js';
import { ICONS } from './_icons.js';

/* ── CSS class constants ───────────────────────────────────────────────── */

const CSS = {
  backdrop: 'c-modal-backdrop',
  backdropExiting: 'c-modal-backdrop--exiting',
  modal: 'c-modal',
  header: 'c-modal__header',
  title: 'c-modal__title',
  close: 'c-modal__close',
  body: 'c-modal__body',
  footer: 'c-modal__footer',
};

/* ── Focus trap ────────────────────────────────────────────────────────── */

/**
 * Trap focus within a given element.
 * @param {Element} element
 * @returns {Function} Cleanup function
 */
function _trapFocus(element) {
  const focusableSel = 'a[href], button:not([disabled]), textarea:not([disabled]), '
    + 'input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

  /** @param {KeyboardEvent} e */
  const handler = (e) => {
    if (e.key !== 'Tab') return;
    const focusables = element.querySelectorAll(focusableSel);
    if (focusables.length === 0) {
      e.preventDefault();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  document.addEventListener('keydown', handler);
  // Focus the first focusable element
  requestAnimationFrame(() => {
    const first = element.querySelector(focusableSel);
    if (first) first.focus();
  });

  return () => document.removeEventListener('keydown', handler);
}

/**
 * Create a modal dialog system.
 *
 * @param {string|Element} [container] - Container element. If not
 *        provided, uses or creates '#modal-container'.
 * @returns {ModalSystem}
 */
export function createModalSystem(container) {
  /** @type {Element} */
  let _container;

  /** @type {Array<Object>} Modal stack */
  const _stack = [];

  /** @type {Function|null} Current focus trap cleanup */
  let _focusCleanup = null;

  /** @type {Function|null} Current escape handler */
  let _escapeCleanup = null;

  /**
   * Resolve the container element.
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
      _container = document.getElementById('modal-container');
    }

    if (!_container) {
      _container = document.createElement('div');
      _container.id = 'modal-container';
      document.body.appendChild(_container);
    }

    return _container;
  }

  /**
   * Render the current top modal.
   * @private
   */
  function _render() {
    const el = _resolveContainer();

    if (_stack.length === 0) {
      el.innerHTML = '';
      el.style.display = 'none';
      document.body.style.overflow = '';
      if (_focusCleanup) { _focusCleanup(); _focusCleanup = null; }
      if (_escapeCleanup) { _escapeCleanup(); _escapeCleanup = null; }
      return;
    }

    const modal = _stack[_stack.length - 1];
    const sizeClass = modal.size ? `c-modal--${modal.size}` : '';

    // Build buttons
    const buttonsHtml = (modal.buttons || []).map((btn) => html`
      <button class="c-btn c-btn--${btn.variant || 'primary'} ${btn.class || ''}"
              data-modal-action="${html.raw('')}"
              data-value="${btn.value || ''}"
              ${btn.disabled ? 'disabled' : ''}>
        ${btn.icon ? html`<span class="c-btn__icon">${ICONS[btn.icon] || btn.icon}</span>` : ''}
        <span class="c-btn__text">${btn.label}</span>
      </button>
    `).join('');

    el.innerHTML = html`
      <div class="${CSS.backdrop}" data-backdrop>
        <div class="${CSS.modal} ${sizeClass}">
          <div class="${CSS.header}">
            <h3 class="${CSS.title}">${modal.title || ''}</h3>
            ${modal.closeable !== false ? html`
              <button class="${CSS.close}" data-action="close-modal" aria-label="Close">
                ${ICONS.close}
              </button>
            ` : ''}
          </div>
          <div class="${CSS.body}">${html.raw(modal.content || '')}</div>
          ${buttonsHtml ? html`
            <div class="${CSS.footer}">
              ${html.raw(buttonsHtml)}
            </div>
          ` : ''}
        </div>
      </div>
    `;

    el.style.display = 'flex';

    // Prevent body scroll
    document.body.style.overflow = 'hidden';

    // Focus trap
    const modalEl = el.querySelector(`.${CSS.modal}`);
    if (_focusCleanup) _focusCleanup();
    _focusCleanup = _trapFocus(modalEl);

    // Escape key
    if (_escapeCleanup) _escapeCleanup();
    const escapeHandler = (e) => {
      if (e.key === 'Escape' && modal.closeOnEscape !== false) {
        closeTopModal(undefined);
      }
    };
    document.addEventListener('keydown', escapeHandler);
    _escapeCleanup = () => document.removeEventListener('keydown', escapeHandler);

    // Backdrop click
    const backdrop = el.querySelector('[data-backdrop]');
    if (backdrop) {
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop && modal.closeOnBackdrop !== false) {
          closeTopModal(undefined);
        }
      });
    }

    // Button clicks
    el.querySelectorAll('[data-modal-action]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const value = btn.dataset.value !== undefined ? btn.dataset.value : btn.textContent.trim();
        closeTopModal(value);
      });
    });

    // Close button
    const closeBtn = el.querySelector('[data-action="close-modal"]');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        closeTopModal(undefined);
      });
    }
  }

  /**
   * Close the topmost modal, resolving its promise.
   * @param {*} value
   * @private
   */
  function closeTopModal(value) {
    const modal = _stack.pop();
    if (modal && modal._resolve) {
      modal._resolve(value !== undefined ? value : null);
    }
    _render();
  }

  /* ── Public API ──────────────────────────────────────────────────────── */

  /**
   * Show a modal dialog.
   *
   * @param {Object} options
   * @param {string} options.title - Modal title
   * @param {string} options.content - HTML body content
   * @param {'sm'|'md'|'lg'|'xl'|'full'} [options.size='md'] - Modal size
   * @param {Array<{label: string, value: *, variant?: string, icon?: string, disabled?: boolean, class?: string}>} [options.buttons]
   * @param {boolean} [options.closeOnBackdrop=true] - Close on backdrop click
   * @param {boolean} [options.closeOnEscape=true] - Close on Escape key
   * @param {boolean} [options.closeable=true] - Show close button
   * @returns {Promise<*>} Resolves with the button value, or null on dismiss
   */
  function showModal(options = {}) {
    return new Promise((resolve) => {
      const modal = {
        title: options.title || '',
        content: options.content || '',
        size: options.size || 'md',
        buttons: options.buttons || [],
        closeOnBackdrop: options.closeOnBackdrop !== false,
        closeOnEscape: options.closeOnEscape !== false,
        closeable: options.closeable !== false,
        _resolve: resolve,
      };
      _stack.push(modal);
      _render();
    });
  }

  /**
   * Close the topmost modal (returns null).
   * @param {*} [value] - Resolve value
   */
  function closeModal(value) {
    closeTopModal(value !== undefined ? value : null);
  }

  /**
   * Close all modals immediately.
   */
  function closeAllModals() {
    while (_stack.length > 0) {
      const modal = _stack.pop();
      if (modal && modal._resolve) {
        modal._resolve(null);
      }
    }
    _render();
  }

  /**
   * Check if any modal is currently open.
   * @returns {boolean}
   */
  function isOpen() {
    return _stack.length > 0;
  }

  /**
   * Get the number of open modals.
   * @returns {number}
   */
  function stackSize() {
    return _stack.length;
  }

  // Initialize (render empty)
  _resolveContainer();
  _render();

  return {
    showModal,
    closeModal,
    closeAllModals,
    isOpen,
    stackSize,
  };
}

/**
 * @typedef {Object} ModalSystem
 * @property {(options: Object) => Promise<*>} showModal
 * @property {(value?: *) => void} closeModal
 * @property {() => void} closeAllModals
 * @property {() => boolean} isOpen
 * @property {() => number} stackSize
 */

/**
 * Singleton modal system instance.
 *
 * Import and use directly:
 *   import { modal } from './Modal.js';
 *   const answer = await modal.showModal({ title: 'Confirm', ... });
 *
 * @type {ModalSystem}
 */
export const modal = createModalSystem();

export default modal;
