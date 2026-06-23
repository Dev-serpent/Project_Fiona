/* ==========================================================================
   app.js — Main Application Bootstrap
   ==========================================================================
   Entry point for the Fiona web frontend.  Initializes the state store,
   router, API client, and all global UI subsystems (keyboard shortcuts,
   sidebar, status bar, command palette, notifications, modals).
   
   Loaded by index.html via <script type="module" src="js/app.js"></script>.
   ========================================================================== */

import { createStore } from './state.js';
import { createRouter } from './router.js';
import { createApi } from './api.js';

/* ── Initial State ──────────────────────────────────────────────────────── */

/**
 * Default application state with all required slices.
 * Each slice maps to a functional domain of the application.
 */
const initialState = {
  /** Application-level settings and metadata */
  app: {
    version: '0.1.0',
    theme: 'dark',
    sidebarCollapsed: false,
    rightPanelOpen: false,
    commandPaletteOpen: false,
    modalOpen: false,
    currentModal: null,
    isOnline: navigator.onLine,
    startTime: Date.now(),
  },

  /** Chat state for the AI agent */
  chat: {
    sessions: [],
    activeSessionId: null,
    messages: [],
    streamToken: null,
    isResponding: false,
    personalities: [],
    activePersonality: null,
  },

  /** Agent configuration and status */
  agents: {
    list: [],
    activeAgentId: null,
    agentStatus: {},
  },

  /** System metrics and health */
  system: {
    status: 'disconnected', // 'disconnected' | 'connecting' | 'connected' | 'error'
    metrics: {
      cpu: 0,
      memory: 0,
      disk: 0,
      uptime: 0,
    },
    serverInfo: null,
    capabilities: [],
    reconnectAttempts: 0,
  },

  /** User and application settings */
  settings: {
    general: {},
    security: {},
    voice: {},
    macros: {},
    shellSafety: {},
    about: {},
    isDirty: {},
  },

  /** Workspace / project state */
  workspace: {
    currentPath: null,
    recentFiles: [],
    openFiles: [],
    activeFileId: null,
  },

  /** Notification center */
  notifications: {
    items: [],
    unreadCount: 0,
    toasts: [],
  },

  /** Terminal sessions */
  terminal: {
    sessions: {},
    activeSessionId: null,
  },

  /** Browser / web views */
  browser: {
    tabs: [],
    activeTabId: null,
    history: [],
  },

  /** File system browser */
  files: {
    currentDir: null,
    items: [],
    selectedPath: null,
    clipboard: null,
  },

  /** Background tasks and progress */
  tasks: {
    queue: [],
    active: null,
    history: [],
  },

  /** Plugin registry state */
  plugins: {
    loaded: [],
    available: [],
    settings: {},
  },
};

/* ── Route Definitions ──────────────────────────────────────────────────── */

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../pages/dashboard.js'),
    title: 'Dashboard',
    icon: 'dashboard',
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../pages/chat.js'),
    title: 'AI Chat',
    icon: 'message',
  },
  {
    path: '/agents',
    name: 'agents',
    component: () => import('../pages/agents.js'),
    title: 'Agents',
    icon: 'bot',
  },
  {
    path: '/agents/:id',
    name: 'agent-detail',
    component: () => import('../pages/agent-status.js'),
    title: 'Agent',
    icon: 'bot',
  },
  {
    path: '/actions',
    name: 'actions',
    component: () => import('../pages/actions.js'),
    title: 'Actions',
    icon: 'bolt',
  },
  {
    path: '/bindings',
    name: 'bindings',
    component: () => import('../pages/bindings.js'),
    title: 'Key Bindings',
    icon: 'keyboard',
  },
  {
    path: '/phiconnect',
    name: 'phiconnect',
    component: () => import('../pages/phiconnect.js'),
    title: 'PhiConnect',
    icon: 'lock',
  },
  {
    path: '/macros',
    name: 'macros',
    component: () => import('../pages/macros.js'),
    title: 'Macros',
    icon: 'play',
  },
  {
    path: '/terminal',
    name: 'terminal',
    component: () => import('../pages/terminal.js'),
    title: 'Terminal',
    icon: 'terminal',
  },
  {
    path: '/vsee',
    name: 'vsee',
    component: () => import('../pages/vsee.js'),
    title: 'Vsee',
    icon: 'eye',
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('../pages/notifications.js'),
    title: 'Notifications',
    icon: 'bell',
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../pages/settings.js'),
    title: 'Settings',
    icon: 'gear',
  },
  {
    path: '/performance',
    name: 'performance',
    component: () => import('../pages/performance.js'),
    title: 'Performance',
    icon: 'activity',
  },
  {
    path: '/files',
    name: 'files',
    component: () => import('../pages/file-explorer.js'),
    title: 'Files',
    icon: 'folder',
  },
  {
    path: '/browser',
    name: 'browser',
    component: () => import('../pages/browser.js'),
    title: 'Browser',
    icon: 'globe',
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('../pages/tasks.js'),
    title: 'Tasks',
    icon: 'check-circle',
  },
  {
    path: '/plugins',
    name: 'plugins',
    component: () => import('../pages/plugins.js'),
    title: 'Plugins',
    icon: 'puzzle',
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('../pages/logs.js'),
    title: 'Logs',
    icon: 'activity',
  },
  {
    path: '/config',
    name: 'config',
    component: () => import('../pages/config.js'),
    title: 'Configuration',
    icon: 'gear',
  },
  {
    path: '/diagnostics',
    name: 'diagnostics',
    component: () => import('../pages/diagnostics.js'),
    title: 'Diagnostics',
    icon: 'activity',
  },
  {
    path: '/devtools',
    name: 'devtools',
    component: () => import('../pages/devtools.js'),
    title: 'Developer Tools',
    icon: 'terminal',
  },
  {
    path: '/workspace',
    name: 'workspace',
    component: () => import('../pages/workspace.js'),
    title: 'Workspace',
    icon: 'folder',
  },
];

/* ── Global App Object ──────────────────────────────────────────────────── */

/**
 * @namespace FionaApp
 */
const app = {
  /** @type {import('./state.js').Store} */
  store: null,
  /** @type {import('./router.js').Router} */
  router: null,
  /** @type {import('./api.js').ApiClient} */
  api: null,

  /** @type {Object} Store references to initialized subsystems */
  subsystems: {},

  /** @type {boolean} Whether the app has been booted */
  initialized: false,
};

/* ── Initialization ─────────────────────────────────────────────────────── */

/**
 * Bootstrap the application.
 * Called once when the module loads.
 */
async function init() {
  if (app.initialized) return;

  console.log('[fiona] Initializing Fiona frontend v0.1.0');

  try {
    // ── 1. Create Store ──
    console.log('[fiona] Initializing state store');
    app.store = createStore(initialState, { logger: true });

    // Persist UI state and settings to localStorage
    app.store.persist('app');
    app.store.persist('settings');

    // ── 2. Create API Client ──
    console.log('[fiona] Initializing API client');
    app.api = createApi({
      baseURL: 'http://localhost:8765',
      timeout: 30000,
      onError: (error) => {
        console.error('[fiona] API error:', error);
        app.store.set('system.status', 'error');
        _addToast({
          type: 'error',
          message: error.message || 'A network error occurred.',
        });
      },
    });

    // ── 3. Set up API request interceptor for auth/headers ──
    app.api.onRequest((config) => {
      // Could attach tokens or additional headers here
      return config;
    });

    // ── 4. Set up API response interceptor for connection tracking ──
    app.api.onResponse((response) => {
      if (response.ok) {
        app.store.set('system.status', 'connected', { silent: true });
      }
      return response;
    });

    // ── 5. Create Router ──
    console.log('[fiona] Initializing router');
    const container = document.getElementById('page-content');
    app.router = createRouter({
      routes,
      container: container || '#page-content',
      scrollToTop: true,
      beforeEach: (to, from) => {
        // Global navigation guard — can redirect or cancel
        return true;
      },
      onError: (error, route) => {
        console.error(`[fiona] Route error on ${route?.path}:`, error);
        _addToast({
          type: 'error',
          message: `Failed to load ${route?.title || 'page'}: ${error.message}`,
          duration: 5000,
        });
      },
    });

    // ── 6. Initialize Global UI Systems ──
    console.log('[fiona] Initializing UI systems');
    _initGlobalShortcuts();
    _initSidebar();
    _initStatusBar();
    _initCommandPalette();
    _initNotificationSystem();
    _initModalSystem();
    _initResizeHandler();
    _initBeforeUnload();
    _initClock();
    _initConnectionIndicator();
    _initHeaderActions();

    // ── 7. Register service worker (placeholder) ──
    _registerServiceWorker();

    // ── 8. Start the router ──
    app.router.init();

    // ── 9. Connect to backend WebSocket ──
    _connectWebSocket();

    // ── 10. Expose app globally for debugging ──
    window.__fiona = app;
    window.fiona = app;

    app.initialized = true;
    console.log('[fiona] Fiona frontend initialized successfully');
  } catch (err) {
    console.error('[fiona] Failed to initialize:', err);
    _showFatalError(err);
  }
}

/* ── Keyboard Shortcuts ─────────────────────────────────────────────────── */

/**
 * Register global keyboard shortcuts.
 * @private
 */
function _initGlobalShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K — Command palette
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      _toggleCommandPalette();
      return;
    }

    // Ctrl/Cmd + B — Toggle sidebar
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      _toggleSidebar();
      return;
    }

    // Escape — Close modals, command palette, panels
    if (e.key === 'Escape') {
      const appState = app.store.get('app');
      if (appState.commandPaletteOpen) {
        _toggleCommandPalette();
        return;
      }
      if (appState.modalOpen) {
        _closeModal();
        return;
      }
      if (appState.rightPanelOpen) {
        _toggleRightPanel();
        return;
      }
    }

    // Ctrl/Cmd + , — Open settings
    if ((e.ctrlKey || e.metaKey) && e.key === ',') {
      e.preventDefault();
      app.router.navigate('/settings');
      return;
    }

    // Alt + N — Notifications
    if (e.altKey && e.key === 'n') {
      e.preventDefault();
      app.router.navigate('/notifications');
      return;
    }

    // Ctrl/Cmd + Shift + Z — Redo
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'z') {
      e.preventDefault();
      app.store.redo();
      return;
    }

    // Ctrl/Cmd + Z — Undo (when not in input)
    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !_isInInput(e.target)) {
      e.preventDefault();
      app.store.undo();
      return;
    }
  });
}

/**
 * Check if the event target is a text input element.
 * @param {Element} target
 * @returns {boolean}
 */
function _isInInput(target) {
  const tag = target?.tagName?.toLowerCase();
  return tag === 'input' || tag === 'textarea' || target?.isContentEditable;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */

/**
 * Set up sidebar navigation and toggle behavior.
 * @private
 */
function _initSidebar() {
  // Toggle sidebar via button
  const toggleBtn = document.querySelector('[data-action="toggle-sidebar"]');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', _toggleSidebar);
  }

  const collapseBtn = document.getElementById('sidebar-collapse-btn');
  if (collapseBtn) {
    collapseBtn.addEventListener('click', _toggleSidebar);
  }

  // Populate sidebar navigation from routes
  _renderSidebarNav();

  // Restore collapsed state from store hydration
  const appState = app.store.get('app');
  if (appState.sidebarCollapsed) {
    document.getElementById('app-main')?.classList.add('app-main--sidebar-collapsed');
  }

  // Listen for sidebar collapse state changes
  app.store.subscribe('app.sidebarCollapsed', (collapsed) => {
    const main = document.getElementById('app-main');
    if (main) {
      main.classList.toggle('app-main--sidebar-collapsed', collapsed);
    }
    try {
      localStorage.setItem('fiona_sidebar_collapsed', String(collapsed));
    } catch { /* ignore */ }
  });
}

/**
 * Toggle the sidebar collapsed state.
 * @private
 */
function _toggleSidebar() {
  const current = app.store.get('app.sidebarCollapsed');
  app.store.set('app.sidebarCollapsed', !current);
}

/**
 * Toggle the right panel.
 * @private
 */
function _toggleRightPanel() {
  const current = app.store.get('app.rightPanelOpen');
  app.store.set('app.rightPanelOpen', !current);
  const panel = document.getElementById('right-panel');
  if (panel) {
    panel.classList.toggle('right-panel--hidden', current);
  }
}

/**
 * Render sidebar navigation items from route definitions.
 * @private
 */
function _renderSidebarNav() {
  const navContent = document.getElementById('sidebar-nav-content');
  if (!navContent) return;

  // Group routes into navigation sections
  const navItems = routes
    .filter((r) => r.path !== '/') // Exclude dashboard for sidebar (handled separately)
    .map((r) => ({
      path: r.path,
      name: r.name,
      title: r.title,
      icon: r.icon,
    }));

  // Main sections
  const primarySections = [
    { label: 'Dashboard', path: '/', icon: 'dashboard', name: 'dashboard', title: 'Dashboard' },
    ...navItems,
  ];

  const navHtml = primarySections
    .map(
      (item) => `
    <a class="sidebar__nav-item${item.path === '/' ? ' sidebar__nav-item--active' : ''}"
       href="#${item.path}"
       data-nav-path="${item.path}"
       title="${item.title}">
      <span class="sidebar__nav-icon">${_getIconSvg(item.icon)}</span>
      <span class="sidebar__nav-label">${item.title}</span>
    </a>`
    )
    .join('');

  navContent.innerHTML = navHtml;

  // Set up click handlers for nav items
  navContent.addEventListener('click', (e) => {
    const navItem = e.target.closest('.sidebar__nav-item');
    if (navItem) {
      e.preventDefault();
      const path = navItem.dataset.navPath;
      if (path) {
        app.router.navigate(path);
      }
    }
  });

  // Update active state on route change
  app.router.onChange((route) => {
    const items = navContent.querySelectorAll('.sidebar__nav-item');
    items.forEach((item) => {
      const itemPath = item.dataset.navPath;
      const isActive = app.router.isActive(itemPath);
      item.classList.toggle('sidebar__nav-item--active', isActive);
    });
  });
}

/**
 * Get a simple SVG icon string by name.
 * Returns a plain SVG string for direct use in string concatenation
 * or regular template literals (not html-tagged templates).
 * @param {string} iconName
 * @returns {string}
 * @private
 */
function _getIconSvg(iconName) {
  const icons = {
    dashboard: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    message: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    bot: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>',
    bolt: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    keyboard: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M8 16h8"/></svg>',
    lock: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    play: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
    terminal: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
    eye: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
    bell: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
    gear: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    folder: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    globe: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    'check-circle': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    puzzle: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-6"/><path d="M22 18h-6"/><path d="M22 6h-6"/><path d="M8 2v4"/><path d="M8 18v4"/><circle cx="8" cy="12" r="4"/></svg>',
    activity: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  };

  return icons[iconName] || icons.dashboard;
}

/* ── Status Bar ─────────────────────────────────────────────────────────── */

/**
 * Set up status bar updates (clock, connection status, notifications).
 * @private
 */
function _initStatusBar() {
  // Update status message on store changes
  app.store.subscribe('system.status', (status) => {
    const statusMsg = document.getElementById('status-message');
    if (statusMsg) {
      const messages = {
        disconnected: 'Disconnected',
        connecting: 'Connecting…',
        connected: 'Connected',
        error: 'Connection Error',
      };
      statusMsg.textContent = messages[status] || status;
    }
  });
}

/* ── Clock ──────────────────────────────────────────────────────────────── */

/**
 * Update the clock in the status bar every minute.
 * @private
 */
function _initClock() {
  const clockEl = document.getElementById('status-clock');
  if (!clockEl) return;

  function updateClock() {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    clockEl.textContent = `${displayHours}:${minutes} ${ampm}`;
  }

  updateClock();
  setInterval(updateClock, 30000); // Update every 30 seconds
}

/* ── Connection Indicator ───────────────────────────────────────────────── */

/**
 * Set up the connection indicator in the header and status bar.
 * @private
 */
function _initConnectionIndicator() {
  const indicator = document.getElementById('connection-indicator');
  const statusLabel = document.getElementById('status-connection');

  app.store.subscribe('system.status', (status) => {
    // Update header indicator
    if (indicator) {
      indicator.className = `connection-indicator connection-indicator--${status}`;
      const label = indicator.querySelector('.connection-indicator__label');
      if (label) {
        const labels = {
          disconnected: 'Disconnected',
          connecting: 'Connecting…',
          connected: 'Connected',
          error: 'Error',
        };
        label.textContent = labels[status] || status;
      }
    }

    // Update status bar
    if (statusLabel) {
      const labels = {
        disconnected: 'Disconnected',
        connecting: 'Connecting…',
        connected: 'Connected',
        error: 'Error',
      };
      statusLabel.textContent = labels[status] || status;
    }
  });
}

/* ── Command Palette ────────────────────────────────────────────────────── */

/**
 * Initialize the command palette subsystem.
 * @private
 */
function _initCommandPalette() {
  const paletteContainer = document.getElementById('command-palette-container');

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      _toggleCommandPalette();
    }
  });

  // Close on backdrop click
  if (paletteContainer) {
    paletteContainer.addEventListener('click', (e) => {
      if (e.target === paletteContainer) {
        _toggleCommandPalette();
      }
    });

    // Close on Escape (handled by global shortcuts, but also here)
    paletteContainer.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        _toggleCommandPalette();
      }
    });
  }

  // Sync with store
  app.store.subscribe('app.commandPaletteOpen', (isOpen) => {
    if (paletteContainer) {
      paletteContainer.classList.toggle('command-palette--open', isOpen);
      paletteContainer.style.display = isOpen ? 'flex' : 'none';
    }
  });
}

/**
 * Toggle the command palette open/closed.
 * @private
 */
function _toggleCommandPalette() {
  const current = app.store.get('app.commandPaletteOpen');
  app.store.set('app.commandPaletteOpen', !current);
}

/* ── Notification System ────────────────────────────────────────────────── */

/**
 * Initialize the notification / toast display system.
 * @private
 */
function _initNotificationSystem() {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) return;

  // Listen for new toasts
  app.store.subscribe('notifications.toasts', (toasts) => {
    // Render active toasts
    const toastHtml = toasts.map((t) => `
      <div class="c-toast c-toast--${t.type || 'info'}" data-toast-id="${t.id}">
        <div class="c-toast__icon">${_getToastIcon(t.type)}</div>
        <div class="c-toast__content">
          <div class="c-toast__message">${_escapeHtml(t.message)}</div>
          ${t.details ? `<div class="c-toast__details">${_escapeHtml(t.details)}</div>` : ''}
        </div>
        <button class="c-toast__dismiss" data-toast-dismiss="${t.id}" aria-label="Dismiss">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    `).join('');

    toastContainer.innerHTML = toastHtml;

    // Set up dismiss handlers
    toastContainer.querySelectorAll('[data-toast-dismiss]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.toastDismiss;
        _removeToast(id);
      });
    });
  });

  // Update notification badge
  app.store.subscribe('notifications.unreadCount', (count) => {
    const badge = document.getElementById('status-notification-count');
    if (badge) {
      badge.textContent = String(count);
    }
  });
}

/**
 * Add a toast notification.
 * @param {Object} toast
 * @param {string} toast.type - 'info' | 'success' | 'warning' | 'error'
 * @param {string} toast.message
 * @param {string} [toast.details]
 * @param {number} [toast.duration=4000]
 * @private
 */
function _addToast(toast) {
  const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const newToast = { ...toast, id };
  const toasts = app.store.get('notifications.toasts');
  app.store.set('notifications.toasts', [...toasts, newToast]);

  // Auto-dismiss after duration
  const duration = toast.duration || 4000;
  setTimeout(() => _removeToast(id), duration);
}

/**
 * Remove a toast by id.
 * @param {string} id
 * @private
 */
function _removeToast(id) {
  const toasts = app.store.get('notifications.toasts');
  app.store.set('notifications.toasts', toasts.filter((t) => t.id !== id));
}

/**
 * Get an SVG icon for a toast type.
 * @param {string} type
 * @returns {string}
 * @private
 */
function _getToastIcon(type) {
  const icons = {
    info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    warning: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    error: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
  };
  return icons[type] || icons.info;
}

/* ── Modal System ───────────────────────────────────────────────────────── */

/**
 * Initialize the modal display system.
 * @private
 */
function _initModalSystem() {
  const modalContainer = document.getElementById('modal-container');
  if (!modalContainer) return;

  // Close modal on backdrop click
  modalContainer.addEventListener('click', (e) => {
    if (e.target === modalContainer) {
      _closeModal();
    }
  });

  app.store.subscribe('app.modalOpen', (isOpen) => {
    if (modalContainer) {
      modalContainer.classList.toggle('modal--open', isOpen);
      modalContainer.style.display = isOpen ? 'flex' : 'none';
    }

    // Prevent body scroll when modal is open
    document.body.style.overflow = isOpen ? 'hidden' : '';
  });
}

/**
 * Open a modal with content.
 * @param {Object} modalConfig
 * @param {string} modalConfig.title
 * @param {string} modalConfig.body - HTML for the modal body
 * @param {string} [modalConfig.size] - 'sm' | 'md' | 'lg' | 'xl'
 * @param {Array<Object>} [modalConfig.actions] - Footer action buttons
 * @private
 */
function _openModal(modalConfig) {
  const modalContainer = document.getElementById('modal-container');
  if (!modalContainer) return;

  const actionsHtml = (modalConfig.actions || [])
    .map((action) => `
      <button class="c-btn c-btn--${action.variant || 'primary'}"
              data-modal-action="${action.id || ''}">
        ${action.label}
      </button>
    `).join('');

  modalContainer.innerHTML = `
    <div class="c-modal c-modal--${modalConfig.size || 'md'}">
      <div class="c-modal__header">
        <h3 class="c-modal__title">${_escapeHtml(modalConfig.title)}</h3>
        <button class="c-modal__close" data-action="close-modal" aria-label="Close">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="c-modal__body">${modalConfig.body}</div>
      ${actionsHtml ? `<div class="c-modal__footer">${actionsHtml}</div>` : ''}
    </div>
  `;

  // Set up close handlers
  modalContainer.querySelector('[data-action="close-modal"]')?.addEventListener('click', _closeModal);

  // Set up action handlers
  modalContainer.querySelectorAll('[data-modal-action]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const actionId = btn.dataset.modalAction;
      if (modalConfig.onAction) modalConfig.onAction(actionId);
    });
  });

  app.store.set('app.modalOpen', true);
  app.store.set('app.currentModal', modalConfig);
}

/**
 * Close the currently open modal.
 * @private
 */
function _closeModal() {
  app.store.set('app.modalOpen', false);
  app.store.set('app.currentModal', null);
  const modalContainer = document.getElementById('modal-container');
  if (modalContainer) {
    modalContainer.innerHTML = '';
  }
  document.body.style.overflow = '';
}

/* ── Header Actions ─────────────────────────────────────────────────────── */

/**
 * Bind clicks on header action buttons.
 * @private
 */
function _initHeaderActions() {
  // Settings button
  const settingsBtn = document.getElementById('header-settings-btn');
  settingsBtn?.addEventListener('click', () => {
    app.router.navigate('/settings');
  });

  // Notifications button
  const notifBtn = document.getElementById('header-notifications-btn');
  notifBtn?.addEventListener('click', () => {
    app.router.navigate('/notifications');
  });

  // Search / command palette trigger
  const searchTrigger = document.getElementById('search-trigger');
  searchTrigger?.addEventListener('click', _toggleCommandPalette);

  // Global data-action dispatcher
  document.addEventListener('click', (e) => {
    const actionEl = e.target.closest('[data-action]');
    if (!actionEl) return;
    const action = actionEl.dataset.action;
    switch (action) {
      case 'open-settings':
        app.router.navigate('/settings');
        break;
      case 'open-notifications':
        app.router.navigate('/notifications');
        break;
      case 'open-command-palette':
        _toggleCommandPalette();
        break;
      case 'toggle-sidebar':
        _toggleSidebar();
        break;
      case 'collapse-sidebar':
        _toggleSidebar();
        break;
      case 'close-panel':
        _toggleRightPanel();
        break;
      case 'open-help':
        // TODO: Implement help system
        _addToast({ type: 'info', message: 'Help system coming soon' });
        break;
      case 'navigate-home':
        app.router.navigate('/');
        break;
      case 'close-modal':
        _closeModal();
        break;
      default:
        // Allow custom actions to be handled elsewhere
        break;
    }
  });
}

/* ── Resize Handler ─────────────────────────────────────────────────────── */

/**
 * Handle window resize events for responsive layout adjustments.
 * @private
 */
function _initResizeHandler() {
  let resizeTimeout;

  window.addEventListener('resize', () => {
    // Debounce resize handler
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      const width = window.innerWidth;
      const height = window.innerHeight;

      // Auto-collapse sidebar on small screens (< 900px)
      if (width < 900) {
        const collapsed = app.store.get('app.sidebarCollapsed');
        if (!collapsed) {
          app.store.set('app.sidebarCollapsed', true);
        }
      }

      // Dispatch a custom event for components to listen to
      window.dispatchEvent(new CustomEvent('fiona:resize', {
        detail: { width, height },
      }));
    }, 150);
  });
}

/* ── Before Unload ──────────────────────────────────────────────────────── */

/**
 * Warn the user before closing if there are unsaved changes.
 * @private
 */
function _initBeforeUnload() {
  window.addEventListener('beforeunload', (e) => {
    const isDirty = app.store.get('settings.isDirty');
    const hasDirty = Object.values(isDirty).some((v) => v === true);
    if (hasDirty) {
      e.preventDefault();
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
    }
  });
}

/* ── WebSocket Connection ───────────────────────────────────────────────── */

/**
 * Connect to the backend WebSocket for real-time updates.
 * @private
 */
function _connectWebSocket() {
  const baseURL = app.api._getBaseURL();
  const wsURL = baseURL.replace(/^http/, 'ws') + '/ws';

  app.store.set('system.status', 'connecting');

  try {
    const conn = app.api.connect(wsURL, {
      autoReconnect: true,
    });

    conn.on('open', () => {
      console.log('[fiona] WebSocket connected');
      app.store.set('system.status', 'connected');
      app.store.set('system.reconnectAttempts', 0);

      // Send handshake
      app.api.send('handshake', {
        client_name: 'fiona-localpages',
        client_version: '0.1.0',
        protocol_version: '1.0',
        capabilities: ['full_state', 'incremental_updates'],
      }, 1);
    });

    conn.on('close', () => {
      console.log('[fiona] WebSocket disconnected');
      app.store.set('system.status', 'disconnected');
    });

    conn.on('reconnecting', ({ attempt, delay }) => {
      console.log(`[fiona] WebSocket reconnecting (attempt ${attempt}) in ${delay}ms`);
      app.store.set('system.status', 'connecting');
      app.store.set('system.reconnectAttempts', attempt);
    });

    conn.on('error', (err) => {
      console.error('[fiona] WebSocket error:', err);
      app.store.set('system.status', 'error');
    });

    // Listen for JSON-RPC notifications
    app.api.on('connection.ready', (params) => {
      console.log('[fiona] Server ready:', params);
      app.store.set('system.serverInfo', params);
      app.store.set('system.status', 'connected');
    });

    app.api.on('system.notification', (params) => {
      // Add to notification center
      const items = app.store.get('notifications.items');
      app.store.set('notifications.items', [params, ...items]);
      app.store.set('notifications.unreadCount', app.store.get('notifications.unreadCount') + 1);

      // Also show as toast for high-priority messages
      if (params.level === 'error' || params.level === 'warning') {
        _addToast({
          type: params.level,
          message: params.message,
        });
      }
    });

  } catch (err) {
    console.error('[fiona] Failed to connect WebSocket:', err);
    app.store.set('system.status', 'error');
  }
}

/* ── Service Worker ─────────────────────────────────────────────────────── */

/**
 * Register the service worker for offline support (placeholder).
 * @private
 */
async function _registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    try {
      // Registration is commented out until sw.js is implemented
      // const registration = await navigator.serviceWorker.register('/sw.js');
      // console.log('[fiona] ServiceWorker registered:', registration.scope);
      console.log('[fiona] ServiceWorker registration ready (not yet active)');
    } catch (err) {
      console.warn('[fiona] ServiceWorker registration failed:', err);
    }
  }
}

/* ── Fatal Error ────────────────────────────────────────────────────────── */

/**
 * Display a fatal initialization error in the UI.
 * @param {Error} err
 * @private
 */
function _showFatalError(err) {
  const container = document.getElementById('page-content');
  if (container) {
    container.innerHTML = `
      <div class="empty-state" style="margin-top: 20vh;">
        <div class="empty-state__icon" style="color: var(--danger);">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
               stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
        </div>
        <div class="empty-state__title">Failed to Start</div>
        <div class="empty-state__description" style="color: var(--danger);">
          ${_escapeHtml(err.message || 'An unexpected error occurred during initialization.')}
        </div>
        <pre style="margin-top: var(--space-4); max-width: 600px; text-align: left; font-size: var(--font-size-xs);">${_escapeHtml(err.stack || '')}</pre>
        <button class="c-btn c-btn--primary" style="margin-top: var(--space-6);" onclick="location.reload()">
          Reload
        </button>
      </div>
    `;
  }
}

/* ── Utility: Escape HTML ───────────────────────────────────────────────── */

/**
 * Escape HTML special characters.
 * @param {string} str
 * @returns {string}
 * @private
 */
function _escapeHtml(str) {
  if (!str) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(str).replace(/[&<>"']/g, (ch) => map[ch]);
}

/* ── Boot ───────────────────────────────────────────────────────────────── */

// Self-executing initialization when the DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

/* ── Export ─────────────────────────────────────────────────────────────── */

export { app };
export default app;
