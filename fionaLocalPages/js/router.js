/* ==========================================================================
   router.js — Hash-Based SPA Router
   ==========================================================================
   A hash-based single-page application router with parameterized routes,
   lifecycle hooks, navigation guards, lazy loading via dynamic import(),
   and a history stack for back/forward support.
   
   Usage:
     import { createRouter } from './router.js';
     const router = createRouter({
       routes: [
         { path: '/', name: 'dashboard', component: () => import('../pages/dashboard.js'), title: 'Dashboard' },
         { path: '/agents/:id', name: 'agent-detail', component: () => import('../pages/agent-detail.js'), title: 'Agent' },
       ],
       container: '#page-content',
     });
     router.navigate('/agents/42');
   ========================================================================== */

/* ── Route Matching ─────────────────────────────────────────────────────── */

/**
 * Parse a route path pattern into a regular expression and parameter names.
 * Supports :param segments and * wildcards.
 *
 * @param {string} pattern - e.g. '/agents/:id'
 * @returns {{ regexp: RegExp, paramNames: string[] }}
 */
function parseRoutePattern(pattern) {
  const paramNames = [];
  const regexStr = pattern
    .replace(/\//g, '\\/')
    .replace(/:(\w+)/g, (_, name) => {
      paramNames.push(name);
      return '([^/]+)';
    })
    .replace(/\*/g, '.*');
  return {
    regexp: new RegExp(`^${regexStr}$`),
    paramNames,
  };
}

/**
 * Extract query parameters from a URL search string.
 * @param {string} search - e.g. '?foo=bar&baz=1'
 * @returns {Object}
 */
function parseQueryString(search) {
  const params = {};
  if (!search || search === '?') return params;
  const searchStr = search.startsWith('?') ? search.slice(1) : search;
  for (const part of searchStr.split('&')) {
    const [key, ...rest] = part.split('=');
    if (key) {
      params[decodeURIComponent(key)] = rest.length > 0
        ? decodeURIComponent(rest.join('='))
        : '';
    }
  }
  return params;
}

/* ── Router Factory ─────────────────────────────────────────────────────── */

/**
 * Create a hash-based SPA router.
 *
 * @param {Object} config
 * @param {Array<Object>} config.routes - Route definitions
 * @param {string} config.routes[].path - URL path pattern (e.g. '/chat', '/agents/:id')
 * @param {string} [config.routes[].name] - Unique route name for programmatic reference
 * @param {Function} config.routes[].component - () => import('./page.js')
 * @param {string} [config.routes[].title] - Page title (sets document.title)
 * @param {string} [config.routes[].icon] - Icon identifier for nav
 * @param {Function} [config.routes[].beforeEnter] - (route) => boolean | Promise<boolean>
 * @param {Function} [config.routes[].onEnter] - (route) => void | Promise<void>
 * @param {Function} [config.routes[].onLeave] - (route) => void | Promise<void>
 * @param {string|Element} [config.container='#page-content'] - Container selector or element
 * @param {boolean} [config.scrollToTop=true] - Scroll to top on navigation
 * @param {Function} [config.beforeEach] - (to, from) => boolean | string | void
 *        Return false to cancel, or a string path to redirect.
 * @param {Function} [config.onError] - (error, route) => void
 * @returns {Router}
 */
export function createRouter(config) {
  const {
    routes: routeDefs = [],
    container: containerSelector = '#page-content',
    scrollToTop: shouldScrollToTop = true,
    beforeEach: globalBeforeEach = null,
    onError: errorHandler = null,
  } = config;

  /** @type {Element} */
  let _container = null;

  /** @type {Array<Object>} Compiled route entries */
  const _routes = routeDefs.map((def) => ({
    ...def,
    _compiled: parseRoutePattern(def.path),
  }));

  /** @type {Object|null} Currently active route info */
  let _currentRoute = null;

  /** @type {Object|null} Previous route info */
  let _previousRoute = null;

  /** @type {string} Current hash path (without #) */
  let _currentPath = '';

  /** @type {Array<string>} Navigation history stack */
  const _historyStack = [];

  /** @type {number} Current position in history stack */
  let _historyIndex = -1;

  /** @type {boolean} Whether we are currently processing a navigation */
  let _isNavigating = false;

  /** @type {boolean} Whether the router has been initialized */
  let _initialized = false;

  /** @type {Function|null} Currently mounted page destroy function */
  let _currentPageDestroy = null;

  /** @type {Function[]} onChange callbacks */
  const _changeListeners = [];

  /** @type {number} Unique ID for tracking route loads */
  let _navigationId = 0;

  /* ── Container Resolution ─────────────────────────────────────────────── */

  function _resolveContainer() {
    if (_container) return _container;
    if (typeof containerSelector === 'string') {
      _container = document.querySelector(containerSelector);
    } else if (containerSelector instanceof Element) {
      _container = containerSelector;
    }
    if (!_container) {
      console.warn('[router] Container element not found, using document body');
      _container = document.body;
    }
    return _container;
  }

  /* ── Route Matching ───────────────────────────────────────────────────── */

  /**
   * Find the first route matching a given path.
   * @param {string} path
   * @returns {Object|null} { route, params }
   */
  function _matchRoute(path) {
    const normalizedPath = path.replace(/\/+$/, '') || '/';
    for (const route of _routes) {
      const match = normalizedPath.match(route._compiled.regexp);
      if (match) {
        const params = {};
        route._compiled.paramNames.forEach((name, index) => {
          params[name] = decodeURIComponent(match[index + 1]);
        });
        return { route, params };
      }
    }
    return null;
  }

  /**
   * Find a route by its name.
   * @param {string} name
   * @returns {Object|undefined}
   */
  function _findRouteByName(name) {
    return _routes.find((r) => r.name === name);
  }

  /* ── Current Route / State ────────────────────────────────────────────── */

  /**
   * Get the current route info.
   * @returns {Object|null} { path, route, params, query, name, title }
   */
  function getCurrentRoute() {
    return _currentRoute;
  }

  /**
   * Get the parameters of the current route.
   * @returns {Object}
   */
  function getRouteParams() {
    return _currentRoute?.params || {};
  }

  /**
   * Get the query parameters of the current route.
   * @returns {Object}
   */
  function getQueryParams() {
    return _currentRoute?.query || {};
  }

  /* ── Navigation ───────────────────────────────────────────────────────── */

  /**
   * Navigate to a path.
   *
   * @param {string} path - Path to navigate to (e.g. '/chat' or '/agents/42')
   * @param {Object} [opts]
   * @param {boolean} [opts.replace=false] - Replace current history entry
   * @param {boolean} [opts.silent=false] - Update hash without triggering navigation
   * @param {Object} [opts.query] - Query parameters to append
   * @returns {Promise<boolean>} True if navigation completed
   */
  async function navigate(path, opts = {}) {
    if (_isNavigating) {
      // Queue the last navigation attempt
      return _deferNavigation(path, opts);
    }

    const { replace = false, silent = false, query } = opts;

    // Build the full hash path with query
    let targetPath = path;
    if (query && Object.keys(query).length > 0) {
      const qs = Object.entries(query)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&');
      targetPath += `?${qs}`;
    }

    if (silent) {
      _currentPath = targetPath;
      return true;
    }

    _isNavigating = true;
    const navId = ++_navigationId;

    try {
      // Resolve the route
      const match = _matchRoute(targetPath);

      // Build route info
      const routeInfo = match
        ? {
            path: targetPath,
            route: match.route,
            params: match.params,
            query: parseQueryString(targetPath.split('?')[1] || ''),
            name: match.route.name,
            title: match.route.title,
          }
        : {
            path: targetPath,
            route: null,
            params: {},
            query: parseQueryString(targetPath.split('?')[1] || ''),
            name: null,
            title: null,
          };

      // ── Navigation Guard: beforeEach ──
      if (globalBeforeEach) {
        const guardResult = await globalBeforeEach(routeInfo, _currentRoute);
        if (guardResult === false) {
          _isNavigating = false;
          return false;
        }
        if (typeof guardResult === 'string') {
          _isNavigating = false;
          navigate(guardResult);
          return false;
        }
      }

      // ── Route Guard: beforeEnter ──
      if (match?.route?.beforeEnter) {
        const guardResult = await match.route.beforeEnter(routeInfo);
        if (guardResult === false) {
          _isNavigating = false;
          return false;
        }
      }

      // ── Lifecycle: onLeave for current page ──
      if (_currentRoute && _currentRoute.route?.onLeave) {
        try {
          await _currentRoute.route.onLeave(_currentRoute);
        } catch (e) {
          console.error('[router] onLeave error:', e);
        }
      }

      // ── Destroy current page ──
      if (_currentPageDestroy) {
        try {
          _currentPageDestroy();
        } catch (e) {
          console.error('[router] destroy error:', e);
        }
        _currentPageDestroy = null;
      }

      // Clear the container
      const container = _resolveContainer();
      container.innerHTML = '';

      // ── Update history ──
      _previousRoute = _currentRoute;
      _currentRoute = routeInfo;
      _currentPath = targetPath;

      if (replace) {
        if (_historyStack.length > 0) {
          _historyStack[_historyIndex] = targetPath;
        }
      } else {
        // Remove any entries after current index (forward history)
        if (_historyIndex < _historyStack.length - 1) {
          _historyStack.splice(_historyIndex + 1);
        }
        _historyStack.push(targetPath);
        _historyIndex = _historyStack.length - 1;
      }

      // Update the URL hash
      if (location.hash !== `#${targetPath}`) {
        location.hash = targetPath;
      }

      // ── Update document title ──
      if (match?.route?.title) {
        document.title = `${match.route.title} — Fiona`;
      } else {
        document.title = 'Fiona';
      }

      // ── Update breadcrumb ──
      _updateBreadcrumb(routeInfo);

      // ── Scroll to top ──
      if (shouldScrollToTop) {
        container.scrollTop = 0;
      }

      // ── 404 Handling ──
      if (!match) {
        container.innerHTML = _renderNotFound(targetPath);
        _isNavigating = false;
        _notifyChange(routeInfo);
        return false;
      }

      // ── Lazy load component ──
      if (match.route.component) {
        try {
          const module = await match.route.component();
          const pageFactory = module.default || module.createPage || module;

          let pageInstance;
          if (typeof pageFactory === 'function') {
            pageInstance = pageFactory(routeInfo);
          }

          // Support both { render(container) } and { mount(container) } and direct function
          if (typeof pageFactory === 'function' && !pageInstance) {
            // If the export is a render function directly
            const html = pageFactory(routeInfo);
            if (typeof html === 'string') {
              container.innerHTML = html;
            }
          } else if (pageInstance) {
            if (typeof pageInstance.render === 'function') {
              const html = pageInstance.render(routeInfo);
              container.innerHTML = html;
              if (typeof pageInstance.mount === 'function') {
                pageInstance.mount(container);
              }
            } else if (typeof pageInstance.mount === 'function') {
              pageInstance.mount(container);
            }
          }

          // Set up destroy
          if (pageInstance && typeof pageInstance.destroy === 'function') {
            _currentPageDestroy = () => pageInstance.destroy();
          } else if (pageInstance && typeof pageInstance.unmount === 'function') {
            _currentPageDestroy = () => pageInstance.unmount();
          }
        } catch (e) {
          console.error('[router] Failed to load component:', e);
          container.innerHTML = _renderError(targetPath, e);
          if (errorHandler) errorHandler(e, routeInfo);
        }
      }

      // ── Lifecycle: onEnter ──
      if (match?.route?.onEnter) {
        try {
          await match.route.onEnter(routeInfo);
        } catch (e) {
          console.error('[router] onEnter error:', e);
        }
      }

      _isNavigating = false;
      _notifyChange(routeInfo);
      return true;
    } catch (e) {
      _isNavigating = false;
      console.error('[router] Navigation error:', e);
      if (errorHandler) errorHandler(e, _currentRoute);
      return false;
    }
  }

  /**
   * Defer a navigation attempt until current navigation completes.
   * Uses a simple single-entry queue.
   * @private
   */
  let _deferredNav = null;

  function _deferNavigation(path, opts) {
    _deferredNav = { path, opts };
    return new Promise((resolve) => {
      const check = () => {
        if (!_isNavigating && _deferredNav) {
          const nav = _deferredNav;
          _deferredNav = null;
          resolve(navigate(nav.path, nav.opts));
        } else {
          setTimeout(check, 16);
        }
      };
      check();
    });
  }

  /* ── Navigation Helpers ───────────────────────────────────────────────── */

  /**
   * Navigate back in history.
   * @returns {Promise<boolean>}
   */
  async function goBack() {
    if (_historyIndex > 0) {
      _historyIndex--;
      const path = _historyStack[_historyIndex];
      return navigate(path, { replace: true });
    }
    return false;
  }

  /**
   * Build a hash URL for a given path.
   * @param {string} path
   * @returns {string} e.g. '#/chat'
   */
  function link(path) {
    return `#${path}`;
  }

  /**
   * Check if the given path matches the current route.
   * @param {string} path
   * @returns {boolean}
   */
  function isActive(path) {
    if (!_currentRoute) return false;
    // Exact match first
    if (_currentRoute.path === path) return true;
    // Check if current path starts with the given path (for parent nav items)
    if (path !== '/' && _currentRoute.path.startsWith(path)) return true;
    return false;
  }

  /* ── Hash Change Handler ──────────────────────────────────────────────── */

  function _onHashChange() {
    const hash = location.hash || '#/';
    const path = hash.startsWith('#') ? hash.slice(1) : hash;
    if (path !== _currentPath) {
      navigate(path);
    }
  }

  /* ── Helpers ──────────────────────────────────────────────────────────── */

  /**
   * Update the breadcrumb in the UI.
   * @param {Object} routeInfo
   */
  function _updateBreadcrumb(routeInfo) {
    const el = document.getElementById('breadcrumb-current');
    if (el) {
      el.textContent = routeInfo?.route?.title || routeInfo?.name || 'Unknown';
    }

    // Update status bar module
    const statusModule = document.getElementById('status-module');
    if (statusModule) {
      statusModule.textContent = routeInfo?.route?.title || routeInfo?.name || '';
    }

    // Update page title
    const pageTitle = document.getElementById('page-title');
    if (pageTitle) {
      pageTitle.textContent = routeInfo?.route?.title || 'Fiona';
    }
  }

  /**
   * Render a 404 not-found state.
   * @param {string} path
   * @returns {string}
   */
  function _renderNotFound(path) {
    return `
      <div class="empty-state">
        <div class="empty-state__icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
               stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
        </div>
        <div class="empty-state__title">Page Not Found</div>
        <div class="empty-state__description">
          No route matches <code>${path}</code>.
        </div>
        <button class="c-btn c-btn--primary" data-action="navigate-home" style="margin-top: var(--space-4);">
          Go to Dashboard
        </button>
      </div>
    `;
  }

  /**
   * Render an error state.
   * @param {string} path
   * @param {Error} error
   * @returns {string}
   */
  function _renderError(path, error) {
    return `
      <div class="empty-state">
        <div class="empty-state__icon" style="color: var(--danger);">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
               stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
        </div>
        <div class="empty-state__title">Failed to Load Page</div>
        <div class="empty-state__description" style="color: var(--danger);">
          ${error.message || 'An unexpected error occurred.'}
        </div>
        <button class="c-btn c-btn--primary" data-action="navigate-home" style="margin-top: var(--space-4);">
          Go to Dashboard
        </button>
      </div>
    `;
  }

  /* ── Change Notifications ─────────────────────────────────────────────── */

  /**
   * Notify all route change listeners.
   * @param {Object} routeInfo
   */
  function _notifyChange(routeInfo) {
    for (const cb of _changeListeners) {
      try {
        cb(routeInfo, _previousRoute);
      } catch (e) {
        console.error('[router] change listener error:', e);
      }
    }
  }

  /**
   * Register a route change listener.
   * @param {Function} callback - (route, previousRoute) => void
   * @returns {Function} Unsubscribe function
   */
  function onChange(callback) {
    _changeListeners.push(callback);
    return () => {
      const idx = _changeListeners.indexOf(callback);
      if (idx >= 0) _changeListeners.splice(idx, 1);
    };
  }

  /* ── Initialization ───────────────────────────────────────────────────── */

  /**
   * Initialize the router.
   * Must be called once to start listening for hash changes.
   */
  function init() {
    if (_initialized) return;
    _initialized = true;

    _resolveContainer();

    // Listen for hash changes
    window.addEventListener('hashchange', _onHashChange);

    // Navigate to the initial route based on current hash
    const initialPath = location.hash
      ? location.hash.slice(1)
      : '/';
    
    // Navigate silently first to set up state, then trigger
    navigate(initialPath || '/');
  }

  /**
   * Destroy the router, cleaning up all listeners.
   */
  function destroy() {
    window.removeEventListener('hashchange', _onHashChange);
    if (_currentPageDestroy) {
      _currentPageDestroy();
      _currentPageDestroy = null;
    }
    _changeListeners.length = 0;
    _routes.length = 0;
    _historyStack.length = 0;
    _currentRoute = null;
    _previousRoute = null;
    _initialized = false;
  }

  /* ── Public API ───────────────────────────────────────────────────────── */

  return {
    navigate,
    goBack,
    getCurrentRoute,
    getRouteParams,
    getQueryParams,
    link,
    isActive,
    onChange,
    init,
    destroy,
    
    // Internal for debugging / testing
    _getRoutes: () => _routes,
    _getHistory: () => [..._historyStack],
  };
}
