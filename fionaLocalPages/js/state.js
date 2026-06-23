/* ==========================================================================
   state.js — Reactive State Management with Pub/Sub
   ==========================================================================
   Provides a namespaced reactive store with dot-notation path access,
   immutable updates, batch operations, history/undo, and localStorage
   persistence.  Designed as the single source of truth for the entire app.
   
   Usage:
     import { createStore } from './state.js';
     const store = createStore({ app: { theme: 'dark' } });
     store.subscribe('app.theme', (val) => console.log('theme:', val));
     store.set('app.theme', 'light');
   ========================================================================== */

/**
 * @typedef {Object} Store
 * @property {function(string=): *} get - Retrieve state at a dot-path (or full state)
 * @property {function(string, *, Object=): void} set - Set value at a dot-path
 * @property {function(string, Function): void} update - Update value via updater function
 * @property {function(string, Function): Function} subscribe - Subscribe to path changes
 * @property {function(Function): Function} subscribeAll - Subscribe to all changes
 * @property {function(): void} reset - Reset to initial state
 * @property {function(): Object} getState - Get the entire current state
 * @property {function(string[]): void} persist - Persist paths to localStorage
 * @property {function(Function): void} batch - Batch multiple mutations into one notification
 * @property {function(): boolean} undo - Undo last state change
 * @property {function(): boolean} redo - Redo last undone change
 */

/** @type {string} Prefix for all localStorage keys managed by the store */
const STORAGE_PREFIX = 'fiona_store_';

/**
 * Safely parse a dot-notation path into an array of segments.
 * Handles escaped dots (\.) for keys that contain dots.
 * @param {string} path
 * @returns {string[]}
 */
function parsePath(path) {
  if (!path || path === '') return [];
  // Split on dots not preceded by backslash
  const segments = [];
  let current = '';
  for (let i = 0; i < path.length; i++) {
    const ch = path[i];
    if (ch === '\\' && i + 1 < path.length && path[i + 1] === '.') {
      current += '.';
      i++;
    } else if (ch === '.') {
      segments.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  if (current !== '') segments.push(current);
  return segments;
}

/**
 * Retrieve a deeply nested value by path segments.
 * @param {Object} obj
 * @param {string[]} segments
 * @param {boolean} [createMissing=false] - Create missing intermediate objects
 * @returns {*} The value at path, or undefined
 */
function getBySegments(obj, segments, createMissing = false) {
  let current = obj;
  for (let i = 0; i < segments.length; i++) {
    const key = segments[i];
    if (current == null || typeof current !== 'object') return undefined;
    if (createMissing && !(key in current)) {
      current[key] = {};
    }
    current = current[key];
  }
  return current;
}

/**
 * Set a deeply nested value by path segments (immutable).
 * Returns a new object with the value set at the path.
 * @param {Object} obj - The source object (not mutated)
 * @param {string[]} segments
 * @param {*} value - The new value
 * @returns {Object} A new object with the value applied
 */
function setBySegments(obj, segments, value) {
  if (segments.length === 0) return value;

  const key = segments[0];
  const rest = segments.slice(1);

  // Create a shallow copy of the current level
  const copy = Array.isArray(obj) ? [...obj] : { ...obj };

  if (rest.length === 0) {
    copy[key] = value;
  } else {
    copy[key] = setBySegments(
      obj && typeof obj === 'object' && key in obj ? obj[key] : {},
      rest,
      value
    );
  }
  return copy;
}

/**
 * Deep merge two objects.  Similar to Object.assign but recursive.
 * Arrays are replaced, not merged.
 * @param {Object} target
 * @param {Object} source
 * @returns {Object} New merged object
 */
function deepMerge(target, source) {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    const targetVal = target[key];
    const sourceVal = source[key];
    if (
      targetVal && sourceVal &&
      typeof targetVal === 'object' && typeof sourceVal === 'object' &&
      !Array.isArray(targetVal) && !Array.isArray(sourceVal)
    ) {
      result[key] = deepMerge(targetVal, sourceVal);
    } else {
      result[key] = sourceVal;
    }
  }
  return result;
}

/**
 * Check if two values are deeply equal (simple JSON comparison).
 * @param {*} a
 * @param {*} b
 * @returns {boolean}
 */
function isEqual(a, b) {
  if (a === b) return true;
  if (a == null || b == null) return false;
  if (typeof a !== typeof b) return false;
  if (typeof a === 'object') {
    try {
      return JSON.stringify(a) === JSON.stringify(b);
    } catch {
      return false;
    }
  }
  return false;
}

/**
 * Create a namespaced reactive store.
 *
 * @param {Object} initialState - Initial state tree
 * @param {Object} [options]
 * @param {boolean} [options.logger=false] - Enable console.log on every mutation
 * @returns {Store}
 */
export function createStore(initialState = {}, options = {}) {
  /** Deep clone initial state to avoid reference sharing */
  const _initial = deepClone(initialState);
  
  /** @type {Object} Current state */
  let _state = deepClone(_initial);

  /** @type {Map<string, Set<Function>>} Path → subscriber callbacks */
  const _subscribers = new Map();

  /** @type {Set<Function>} Global subscriber callbacks */
  const _globalSubscribers = new Set();

  /** @type {number} Batch nesting counter (> 0 means inside batch) */
  let _batchDepth = 0;

  /** @type {Array<{ path: string, newValue: *, oldValue: * }>} Pending notifications */
  let _pendingNotifications = [];

  /** @type {Array<Object>} Undo stack (previous states) */
  const _undoStack = [];

  /** @type {Array<Object>} Redo stack */
  const _redoStack = [];

  /** @type {number} Max history entries */
  const MAX_HISTORY = 50;

  /** @type {boolean} Whether we are currently restoring from history */
  let _isHistoryRestore = false;

  /** @type {string[]} Paths to persist to localStorage */
  let _persistedPaths = [];

  /** @type {number} Debounce timer for persistence writes */
  let _persistTimer = null;

  /** @type {boolean} Enable logging */
  const _logger = options.logger === true;

  /**
   * Deep clone a value using structuredClone (fallback to JSON).
   * @param {*} value
   * @returns {*}
   */
  function deepClone(value) {
    if (typeof structuredClone === 'function') {
      try {
        return structuredClone(value);
      } catch {
        // fall through to JSON method
      }
    }
    try {
      return JSON.parse(JSON.stringify(value));
    } catch {
      return value;
    }
  }

  /**
   * Get the value at a dot-notation path, or the entire state if no path.
   * @param {string} [path] - Dot-notation path (e.g. 'chat.messages')
   * @returns {*}
   */
  function get(path) {
    if (path == null || path === '') return deepClone(_state);
    const segments = parsePath(path);
    return deepClone(getBySegments(_state, segments));
  }

  /**
   * Get the raw (non-cloned) value at a path — for internal use.
   * @param {string} path
   * @returns {*}
   */
  function _getRaw(path) {
    if (path == null || path === '') return _state;
    const segments = parsePath(path);
    return getBySegments(_state, segments);
  }

  /**
   * Get the entire current state (cloned).
   * @returns {Object}
   */
  function getState() {
    return deepClone(_state);
  }

  /**
   * Set a value at a dot-notation path.
   * Does nothing if the value is unchanged (deep equality check).
   *
   * @param {string} path - Dot-notation path
   * @param {*} value - New value
   * @param {Object} [opts]
   * @param {boolean} [opts.silent=false] - Skip notifications
   */
  function set(path, value, opts = {}) {
    if (path == null || path === '') {
      _state = deepClone(value);
      _notify('', _state, null, opts);
      return;
    }

    const oldValue = _getRaw(path);
    if (isEqual(oldValue, value)) return;

    // Save state for undo (before mutation)
    _pushHistory();

    const segments = parsePath(path);
    _state = setBySegments(_state, segments, deepClone(value));
    
    if (_logger) {
      console.log(`[store] set ${path}`, value);
    }

    _notify(path, _getRaw(path), oldValue, opts);
  }

  /**
   * Update a value at a path using an updater function.
   * The updater receives the current value and should return the new value.
   *
   * @param {string} path - Dot-notation path
   * @param {Function} updaterFn - (currentValue) => newValue
   * @param {Object} [opts]
   */
  function update(path, updaterFn, opts = {}) {
    const current = get(path);
    const newValue = updaterFn(current);
    set(path, newValue, opts);
  }

  /**
   * Deep merge a partial object into the state at a given path.
   * Unlike set() which replaces, this merges nested objects.
   *
   * @param {string} path - Dot-notation path
   * @param {Object} partial - Partial object to merge
   * @param {Object} [opts]
   */
  function merge(path, partial, opts = {}) {
    const current = get(path);
    if (typeof current !== 'object' || current == null) {
      set(path, partial, opts);
      return;
    }
    const merged = deepMerge(current, partial);
    set(path, merged, opts);
  }

  /**
   * Subscribe to changes at a specific path.
   * The callback receives (newValue, oldValue).
   *
   * Supports wildcard: 'agent.*' subscribes to all changes under 'agent'.
   *
   * @param {string} path - Dot-notation path or wildcard pattern
   * @param {Function} callback - (newValue, oldValue) => void
   * @returns {Function} Unsubscribe function
   */
  function subscribe(path, callback) {
    if (typeof callback !== 'function') {
      throw new TypeError('subscribe() requires a function callback');
    }
    if (!_subscribers.has(path)) {
      _subscribers.set(path, new Set());
    }
    _subscribers.get(path).add(callback);
    return () => {
      const subs = _subscribers.get(path);
      if (subs) subs.delete(callback);
    };
  }

  /**
   * Subscribe to all state changes.
   * The callback receives (path, newValue, oldValue).
   *
   * @param {Function} callback - (path, newValue, oldValue) => void
   * @returns {Function} Unsubscribe function
   */
  function subscribeAll(callback) {
    if (typeof callback !== 'function') {
      throw new TypeError('subscribeAll() requires a function callback');
    }
    _globalSubscribers.add(callback);
    return () => _globalSubscribers.delete(callback);
  }

  /**
   * Reset the store to its initial state.
   * Optionally reset only a specific path.
   *
   * @param {string} [path] - Optional path to reset
   */
  function reset(path) {
    _pushHistory();
    if (path) {
      const initialValue = getBySegments(_initial, parsePath(path));
      set(path, initialValue !== undefined ? deepClone(initialValue) : undefined);
    } else {
      const oldState = _state;
      _state = deepClone(_initial);
      _notify('', _state, oldState, {});
    }
  }

  /**
   * Persist specific paths to localStorage whenever they change.
   * Each path is stored under a separate localStorage key.
   *
   * @param {string|string[]} paths - Path(s) to persist
   */
  function persist(paths) {
    const pathArray = Array.isArray(paths) ? paths : [paths];
    for (const p of pathArray) {
      if (!_persistedPaths.includes(p)) {
        _persistedPaths.push(p);
      }
      // Hydrate from localStorage if available
      _hydratePath(p);
    }
  }

  /**
   * Read a persisted path from localStorage and apply it.
   * @param {string} path
   */
  function _hydratePath(path) {
    try {
      const key = STORAGE_PREFIX + path;
      const stored = localStorage.getItem(key);
      if (stored) {
        const value = JSON.parse(stored);
        // Use silent set to avoid re-persisting on hydrate
        const segments = parsePath(path);
        _state = setBySegments(_state, segments, value);
      }
    } catch (e) {
      // Silently fail on localStorage errors (quota, privacy mode, etc.)
      if (_logger) console.warn('[store] hydrate error:', path, e);
    }
  }

  /**
   * Debounced write to localStorage for all persisted paths.
   */
  function _flushPersist() {
    if (_persistTimer) {
      clearTimeout(_persistTimer);
      _persistTimer = null;
    }
    _persistTimer = setTimeout(() => {
      for (const path of _persistedPaths) {
        try {
          const value = _getRaw(path);
          const key = STORAGE_PREFIX + path;
          if (value === undefined) {
            localStorage.removeItem(key);
          } else {
            localStorage.setItem(key, JSON.stringify(value));
          }
        } catch (e) {
          if (_logger) console.warn('[store] persist error:', path, e);
        }
      }
      _persistTimer = null;
    }, 300);
  }

  /**
   * Push current state onto undo stack (before mutation).
   */
  function _pushHistory() {
    if (_isHistoryRestore) return;
    _undoStack.push(deepClone(_state));
    if (_undoStack.length > MAX_HISTORY) {
      _undoStack.shift();
    }
    // Clear redo on new mutation
    _redoStack.length = 0;
  }

  /**
   * Undo the last state change.
   * @returns {boolean} True if undo was performed
   */
  function undo() {
    if (_undoStack.length === 0) return false;
    _redoStack.push(deepClone(_state));
    _isHistoryRestore = true;
    const prevState = _undoStack.pop();
    const oldState = _state;
    _state = prevState;
    _notify('', _state, oldState, {});
    _isHistoryRestore = false;
    return true;
  }

  /**
   * Redo the last undone change.
   * @returns {boolean} True if redo was performed
   */
  function redo() {
    if (_redoStack.length === 0) return false;
    _undoStack.push(deepClone(_state));
    _isHistoryRestore = true;
    const nextState = _redoStack.pop();
    const oldState = _state;
    _state = nextState;
    _notify('', _state, oldState, {});
    _isHistoryRestore = false;
    return true;
  }

  /**
   * Execute multiple mutations in a single batch.
   * Subscribers are notified only once after all mutations complete.
   *
   * @param {Function} fn - () => void, contains multiple set/update calls
   */
  function batch(fn) {
    _batchDepth++;
    try {
      fn();
    } catch (e) {
      console.error('[store] batch error:', e);
    } finally {
      _batchDepth--;
      if (_batchDepth === 0) {
        _flushPendingNotifications();
      }
    }
  }

  /**
   * Notify subscribers of a change.
   * If inside a batch, the notification is queued.
   *
   * @param {string} path
   * @param {*} newValue
   * @param {*} oldValue
   * @param {Object} opts
   */
  function _notify(path, newValue, oldValue, opts = {}) {
    if (opts.silent) return;
    if (_batchDepth > 0) {
      _pendingNotifications.push({ path, newValue, oldValue });
      return;
    }
    _deliverNotification(path, newValue, oldValue);
    _flushPersist();
  }

  /**
   * Deliver a single notification to matching subscribers.
   * @param {string} path
   * @param {*} newValue
   * @param {*} oldValue
   */
  function _deliverNotification(path, newValue, oldValue) {
    // Global subscribers
    for (const cb of _globalSubscribers) {
      try {
        cb(path, newValue, oldValue);
      } catch (e) {
        console.error('[store] subscriber error:', e);
      }
    }

    // Exact path subscribers
    const exactSubs = _subscribers.get(path);
    if (exactSubs) {
      for (const cb of exactSubs) {
        try {
          cb(newValue, oldValue);
        } catch (e) {
          console.error('[store] subscriber error:', e);
        }
      }
    }

    // Wildcard parent subscribers (e.g. 'agent' gets notified for 'agent.messages')
    const segments = parsePath(path);
    for (let i = segments.length - 1; i >= 0; i--) {
      const parentPath = segments.slice(0, i).join('.');
      const wildcardPath = parentPath ? `${parentPath}.*` : '*';
      const wildcardSubs = _subscribers.get(wildcardPath);
      if (wildcardSubs) {
        const parentValue = parentPath ? _getRaw(parentPath) : _state;
        for (const cb of wildcardSubs) {
          try {
            cb(parentValue, deepClone(parentValue));
          } catch (e) {
            console.error('[store] subscriber error:', e);
          }
        }
      }
    }
  }

  /**
   * Flush all queued notifications from a batch.
   */
  function _flushPendingNotifications() {
    const notifications = _pendingNotifications;
    _pendingNotifications = [];
    for (const { path, newValue, oldValue } of notifications) {
      _deliverNotification(path, newValue, oldValue);
    }
    _flushPersist();
  }

  // ── Hydrate persisted paths on creation ──
  // (persist() is called later by the app, but we keep this for auto-hydrate)

  // ── Public API ──

  return {
    get,
    set,
    update,
    merge,
    subscribe,
    subscribeAll,
    reset,
    getState,
    persist,
    batch,
    undo,
    redo,
  };
}
