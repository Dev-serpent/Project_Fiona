/* ==========================================================================
   BaseComponent.js — Base Class for Reusable UI Components
   ==========================================================================
   Provides a consistent lifecycle and API for all UI components in the
   Fiona frontend.  Components render HTML strings, mount into the DOM,
   handle delegated events, and clean up on destroy.
   
   Usage:
     import { BaseComponent, html } from './BaseComponent.js';
     
     class MyButton extends BaseComponent {
       render() {
         return html`<button class="c-btn" data-action="click">${this.props.label}</button>`;
       }
       mount() {
         this.on('click', '[data-action="click"]', () => this.emit('my:click'));
       }
     }
   ========================================================================== */

/* ── HTML Template Literal Tag ──────────────────────────────────────────── */

/**
 * A template literal tag that safely escapes HTML interpolation.
 * Prevents XSS by escaping special characters in embedded expressions.
 *
 * Usage:
 *   html`<div>${userInput}</div>`  — userInput is automatically escaped
 *   html`<div>${html.raw(safeHtml)}</div>` — skip escaping for trusted HTML
 *
 * @param {TemplateStringsArray} strings
 * @param {...*} values
 * @returns {{ __isRawHtml: boolean, html: string, toString(): string }} Safe HTML wrapper
 */
export function html(strings, ...values) {
  let result = '';
  for (let i = 0; i < strings.length; i++) {
    result += strings[i];
    if (i < values.length) {
      const value = values[i];
      if (value && typeof value === 'object' && value.__isRawHtml) {
        // Trusted raw HTML — insert directly
        result += value.html;
      } else if (Array.isArray(value)) {
        // Arrays may contain raw HTML wrappers or plain text.
        for (const item of value) {
          if (item && typeof item === 'object' && item.__isRawHtml) {
            result += item.html;
          } else if (item != null && item !== false) {
            result += _escapeHtml(String(item));
          }
        }
      } else if (value != null && value !== false) {
        result += _escapeHtml(String(value));
      }
    }
  }
  return _rawHtml(result);
}

/**
 * A helper attached to the `html` tag for marking strings as safe raw HTML.
 *
 * @param {string} rawHtml - Trusted HTML string
 * @returns {{ __isRawHtml: boolean, html: string }}
 */
html.raw = function (rawHtml) {
  return _rawHtml(rawHtml);
};

/**
 * Wrap trusted HTML so nested html templates can pass it through safely.
 * @param {string} rawHtml
 * @returns {{ __isRawHtml: boolean, html: string, toString(): string }}
 * @private
 */
function _rawHtml(rawHtml) {
  const value = String(rawHtml);
  return {
    __isRawHtml: true,
    html: value,
    toString() {
      return value;
    },
    valueOf() {
      return value;
    },
    [Symbol.toPrimitive]() {
      return value;
    },
  };
}

/**
 * Escape HTML special characters to prevent XSS injection.
 * @param {string} str
 * @returns {string}
 * @private
 */
function _escapeHtml(str) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return str.replace(/[&<>"']/g, (ch) => map[ch]);
}

/**
 * Escape a string for use as a CSS class name or selector.
 * Replaces non-alphanumeric characters with hyphens.
 * @param {string} str
 * @returns {string}
 */
export function escapeSelector(str) {
  return String(str).replace(/[^a-zA-Z0-9_-]/g, '-').replace(/^-+|-+$/g, '');
}

/**
 * Generate a unique component instance ID.
 * @returns {string}
 */
let _instanceCounter = 0;
function _uid() {
  return `fi-${++_instanceCounter}`;
}

/* ── BaseComponent Class ────────────────────────────────────────────────── */

/**
 * Base class for all UI components.
 *
 * @abstract
 */
export class BaseComponent {
  /**
   * @param {Object} [options]
   * @param {string|Element} [options.container] - DOM element or selector to mount into
   * @param {Object} [options.state={}] - Internal component state
   * @param {Object} [options.props={}] - External properties passed to component
   * @param {Object} [options.store] - Reference to the global state store
   * @param {Object} [options.api] - Reference to the API client
   * @param {Object} [options.router] - Reference to the router
   */
  constructor(options = {}) {
    /** @type {string} Unique instance identifier */
    this.uid = _uid();

    /** @type {Element|null} The root DOM element of this component */
    this.element = null;

    /** @type {Element|null} The container this component is mounted into */
    this.container = null;

    /** @type {Object} Internal component state (not the global store) */
    this._state = { ...(options.state || {}) };

    /** @type {Object} External props passed to the component */
    this._props = { ...(options.props || {}) };

    /** @type {Object|undefined} Reference to the global store */
    this._store = options.store || null;

    /** @type {Object|undefined} Reference to the API client */
    this._api = options.api || null;

    /** @type {Object|undefined} Reference to the router */
    this._router = options.router || null;

    /** @type {Array<Function>} Cleanup functions to run on destroy */
    this._cleanups = [];

    /** @type {Map<string, Array<Function>>} Event listener registrations */
    this._boundEvents = new Map();

    /** @type {boolean} Whether the component is mounted */
    this._isMounted = false;

    // Resolve container if provided
    if (options.container) {
      if (typeof options.container === 'string') {
        this.container = document.querySelector(options.container);
      } else {
        this.container = options.container;
      }
    }
  }

  /* ── Abstract Method: render ──────────────────────────────────────────── */

  /**
   * Render the component's HTML.
   * Must be overridden by subclasses.
   *
   * @abstract
   * @returns {string} HTML string
   */
  render() {
    throw new Error('BaseComponent subclass must implement render()');
  }

  /* ── Lifecycle Methods ────────────────────────────────────────────────── */

  /**
   * Called after the component's HTML is inserted into the DOM.
   * Override to set up event listeners, subscriptions, etc.
   */
  mount() {
    // Override in subclass
  }

  /**
   * Update the component with new props.
   * Re-renders the component in-place if mounted.
   *
   * @param {Object} newProps
   */
  update(newProps = {}) {
    const prevProps = this._props;
    this._props = { ...this._props, ...newProps };
    this._onUpdate(prevProps);
  }

  /**
   * Called when props are updated.  Override to handle prop changes.
   * Default implementation re-renders if mounted.
   *
   * @param {Object} prevProps
   * @protected
   */
  _onUpdate(prevProps) {
    // Re-render by default
    if (this._isMounted) {
      this._reRender();
    }
  }

  /**
   * Destroy the component: remove from DOM, clean up event listeners
   * and subscriptions.
   */
  destroy() {
    // Run all cleanup functions
    for (const cleanup of this._cleanups) {
      try {
        cleanup();
      } catch (e) {
        console.error(`[BaseComponent] cleanup error (${this.uid}):`, e);
      }
    }
    this._cleanups = [];

    // Remove bound events
    this._boundEvents.clear();

    // Remove element from DOM
    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }

    this.element = null;
    this.container = null;
    this._isMounted = false;
  }

  /* ── DOM Integration ──────────────────────────────────────────────────── */

  /**
   * Mount the component into the DOM.
   * Renders HTML, inserts it, then calls mount().
   *
   * @param {string|Element} [container] - Override the container
   * @returns {this}
   */
  attach(container) {
    if (container) {
      if (typeof container === 'string') {
        this.container = document.querySelector(container);
      } else {
        this.container = container;
      }
    }

    if (!this.container) {
      console.error('[BaseComponent] No container to attach to');
      return this;
    }

    // Render HTML
    const htmlString = this.render();
    this.container.innerHTML = htmlString;

    // Store reference to the first child as the element
    this.element = this.container.firstElementChild;

    this._isMounted = true;
    this.mount();

    return this;
  }

  /**
   * Re-render the component in-place.
   * @protected
   */
  _reRender() {
    if (!this.container) return;

    // Save scroll position
    const scrollTop = this.container.scrollTop;

    // Destroy old listeners (but keep the element reference for cleanup)
    for (const cleanup of this._cleanups) {
      try { cleanup(); } catch (e) { /* ignore */ }
    }
    this._cleanups = [];
    this._boundEvents.clear();

    // Re-render
    const htmlString = this.render();
    this.container.innerHTML = htmlString;
    this.element = this.container.firstElementChild;

    // Restore scroll
    this.container.scrollTop = scrollTop;

    // Re-mount
    this.mount();
  }

  /* ── Event Delegation ─────────────────────────────────────────────────── */

  /**
   * Set up a delegated event listener on the component's container.
   * Automatically cleaned up on destroy.
   *
   * @param {string} event - Event name (e.g. 'click', 'input')
   * @param {string} selector - CSS selector for target elements
   * @param {Function} handler - Event handler function
   * @param {Object} [options] - addEventListener options
   * @returns {Function} Remove listener function
   */
  on(event, selector, handler, options) {
    if (!this.container) {
      console.warn('[BaseComponent] Cannot bind event — no container');
      return () => {};
    }

    const delegatedHandler = (e) => {
      // Walk up from target to find matching element
      let target = e.target;
      while (target && target !== this.container) {
        if (target.matches(selector)) {
          // Bind the matched element as `this` context alternative
          handler.call(target, e, target);
          return;
        }
        target = target.parentElement;
      }
    };

    this.container.addEventListener(event, delegatedHandler, options);

    // Track for cleanup
    if (!this._boundEvents.has(event)) {
      this._boundEvents.set(event, []);
    }
    this._boundEvents.get(event).push(delegatedHandler);

    const removeFn = () => {
      if (this.container) {
        this.container.removeEventListener(event, delegatedHandler, options);
      }
    };
    this._cleanups.push(removeFn);
    return removeFn;
  }

  /**
   * Dispatch a custom event from the component's element.
   *
   * @param {string} eventName - Custom event name
   * @param {*} [detail] - Event detail payload
   */
  emit(eventName, detail) {
    if (!this.element) return;
    const event = new CustomEvent(eventName, {
      bubbles: true,
      composed: true,
      detail,
    });
    this.element.dispatchEvent(event);
  }

  /* ── DOM Query Helpers ────────────────────────────────────────────────── */

  /**
   * Query a single element within the component's container.
   * @param {string} selector - CSS selector
   * @returns {Element|null}
   */
  query(selector) {
    if (!this.container) return null;
    return this.container.querySelector(selector);
  }

  /**
   * Query all elements matching a selector within the component's container.
   * @param {string} selector - CSS selector
   * @returns {NodeList|Element[]}
   */
  queryAll(selector) {
    if (!this.container) return [];
    return this.container.querySelectorAll(selector);
  }

  /* ── Internal State Management ────────────────────────────────────────── */

  /**
   * Get the current internal state.
   * @returns {Object}
   */
  getState() {
    return { ...this._state };
  }

  /**
   * Get a specific state value by key.
   * @param {string} key
   * @returns {*}
   */
  getStateValue(key) {
    return this._state[key];
  }

  /**
   * Update internal component state and re-render.
   *
   * @param {Object} partial - Partial state to merge
   * @param {boolean} [silent=false] - Skip re-render if true
   */
  setState(partial, silent = false) {
    const prev = { ...this._state };
    this._state = { ...this._state, ...partial };
    if (!silent && this._isMounted) {
      this._reRender();
    }
  }

  /* ── Props Accessors ──────────────────────────────────────────────────── */

  /**
   * Get the current props.
   * @returns {Object}
   */
  get props() {
    return this._props;
  }

  /**
   * Get a specific prop value.
   * @param {string} key
   * @returns {*}
   */
  getProp(key) {
    return this._props[key];
  }

  /* ── Store Integration ────────────────────────────────────────────────── */

  /**
   * Subscribe to a store path and auto-cleanup on destroy.
   *
   * @param {string} path - Dot-notation store path
   * @param {Function} callback - (newValue, oldValue) => void
   * @returns {Function} Additional unsubscribe (for manual cleanup)
   */
  subscribe(path, callback) {
    if (!this._store) {
      console.warn('[BaseComponent] No store available for subscription');
      return () => {};
    }
    const unsubscribe = this._store.subscribe(path, callback);
    this._cleanups.push(unsubscribe);
    return unsubscribe;
  }

  /**
   * Subscribe to all store changes with auto-cleanup.
   *
   * @param {Function} callback - (path, newValue, oldValue) => void
   * @returns {Function}
   */
  subscribeAll(callback) {
    if (!this._store) {
      console.warn('[BaseComponent] No store available for subscription');
      return () => {};
    }
    const unsubscribe = this._store.subscribeAll(callback);
    this._cleanups.push(unsubscribe);
    return unsubscribe;
  }

  /**
   * Register a cleanup function to be called on destroy.
   * Useful for third-party resources, timers, etc.
   *
   * @param {Function} fn
   */
  addCleanup(fn) {
    if (typeof fn === 'function') {
      this._cleanups.push(fn);
    }
  }

  /* ── CSS Classes Helper ───────────────────────────────────────────────── */

  /**
   * Conditionally build a className string.
   * Accepts strings, arrays, and objects with boolean values.
   *
   * @param {...*} args
   * @returns {string}
   */
  classNames(...args) {
    const classes = [];
    for (const arg of args) {
      if (!arg) continue;
      if (typeof arg === 'string') {
        classes.push(arg);
      } else if (Array.isArray(arg)) {
        classes.push(this.classNames(...arg));
      } else if (typeof arg === 'object') {
        for (const [key, value] of Object.entries(arg)) {
          if (value) classes.push(key);
        }
      }
    }
    return classes.join(' ');
  }
}
