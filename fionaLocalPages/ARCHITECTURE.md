# Fiona Web Frontend — Architecture Blueprint

> **Version:** 2.0  
> **Status:** Implemented  
> **Target:** Complete replacement of all Tkinter GUIs with a standalone web frontend  

> **Note:** This architecture was fully implemented across multiple milestones (see `DEVELOPERNOTE.md` for history). The design decisions below remain authoritative; some implementation details (file maps, route tables, API contracts) now reflect the current state rather than the original plan.

---

## Executive Summary

This document defines the architecture for `fionaLocalPages/`, a standalone HTML/CSS/JS single-page application that replaces all existing Tkinter-based graphical interfaces in Fiona. The frontend communicates with the existing Python backend through an API bridge server (`server/app.py`) that imports Fiona Python modules directly — no intermediate microservices, no containerization, no new deployment pipeline.

The architecture follows a **template-loader-based vanilla JS pattern** with a unidirectional data flow, hash-based SPA routing, pub/sub state management, and WebSocket integration for real-time updates. The aesthetic is dark-first glassmorphism inspired by Cursor, VS Code, Arc Browser, Figma, Warp, and Linear.

---

## 1. Requirements

### 1.1 Functional Requirements

| ID | Requirement | Source |
|----|------------|--------|
| F1 | Replace Tkinter GUIs for: QuikTieper, PhiConnect, TerminalAssist, Vsee, Agent chat, FionaCore settings, CamComs admin, DataClient, RecallVault | Existing GUIs |
| F2 | Agent chat interface with message history, streaming responses, personality selection | `Agent/chat_handler.py` |
| F3 | Action runner — list, search, filter, execute Fiona actions (from `ActionRouter`) | `FionaCore/actions.py` |
| F4 | System dashboard — gauge widgets, resource monitoring, status panels | `TerminalAssist/gui.py` |
| F5 | Key binding manager — view, create, edit, delete QuikTieper bindings | `QuikTieper/gui.py` |
| F6 | Document browser — file tree, recent files, search | Multiple |
| F7 | Notification center — view, dismiss, configure notifications | `FionaCore/notifications.py` |
| F8 | Settings panels — ACL, permissions, voice, macros, shell safety | `FionaCore/` |
| F9 | Real-time updates via WebSocket | System-wide |
| F10 | Cross-module search and navigation | System-wide |

### 1.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|------------|--------|
| N1 | Startup time | < 500ms to interactive |
| N2 | Memory footprint | < 80MB (browser process) |
| N3 | API response time (p95) | < 200ms for cached, < 2s for actions |
| N4 | WebSocket reconnection | < 5s with exponential backoff |
| N5 | Offline degradation | Graceful — show cached state, queue actions |
| N6 | Theme consistency | One dark theme, no light mode (v1) |
| N7 | Accessibility | Semantic HTML, ARIA labels, keyboard navigation |
| N8 | No build step | Zero compile-time tooling, serve static files |

### 1.3 Constraints

- **No bundler/webpack/vite** — the frontend is served as static files; the `cad/server/_frontend` already proved this works with Vite, but for `fionaLocalPages` we serve raw files to eliminate build complexity
- **Vanilla JS only** — no React, Vue, Svelte, or framework
- **Python API server** must import existing Fiona Python modules directly (no subprocess calls)
- **Python stdlib server** or minimal dependencies (aiohttp / FastAPI optional)
- **Must co-exist** with the existing `cad/server/_frontend` — they may eventually merge

---

## 2. Assumptions

1. The API bridge server runs on `127.0.0.1` on a configurable port (default `9876`).
2. A single Python process serves both the REST API and WebSocket connections.
3. The existing Fiona modules are importable without side effects when imported (no auto-start).
4. The frontend is accessed exclusively from the local machine — no CORS concerns beyond `localhost`.
5. The user has Python 3.11+, a modern browser (Chrome/Firefox/Edge 2024+), and Fiona installed.
6. The `server/app.py` script is launched by the existing Fiona CLI (e.g. `fiona web`) or manually.
7. The existing `EventBus` from `fiona.interfaces` will be reused in the API server to subscribe to backend events and forward them over WebSocket.
8. The `fiona.di.FionaContainer` will be used to wire the API server's dependencies.

---

## 3. Architectural Drivers

Ranked by importance:

| Rank | Driver | Rationale |
|------|--------|-----------|
| 1 | **Simplicity** | No framework, no build step, no containerization. The frontend must be approachable for future contributors and trivially debuggable. |
| 2 | **Maintainability** | Component-based architecture with clear separation of concerns. The API bridge must be thin — a pass-through layer, not a business logic host. |
| 3 | **Extensibility** | New pages/modules should be addable by creating one file per page, one API wrapper per module. No routing config changes needed. |
| 4 | **Performance** | The frontend must feel instant on localhost. Minimize DOM updates, use requestAnimationFrame batching, cache API responses aggressively. |
| 5 | **Scalability** | Not a driver for v1 — the frontend serves one user on one machine. Future horizontal scaling is not a concern. |
| 6 | **Security** | Local-only access. The API server must enforce the same ACL/permission checks as the CLI. |

---

## 4. Candidate Architectures

### Option A: Monolithic SPA with Vanilla JS (Recommended)

**Description:** Single HTML file bootstraps a JS app with component-based UI, hash routing, pub/sub state. CSS uses custom properties with BEM naming.

**Advantages:**
- Zero build step — edit and reload
- Maximum simplicity
- Full control over every aspect
- No framework lock-in
- Trivially debuggable in DevTools
- Small payload (~200KB total gzipped)

**Disadvantages:**
- Manual DOM management (no virtual DOM)
- Developer must be disciplined about component lifecycle
- Less ecosystem support

**Complexity:** Low (implementation) / Medium (maintaining discipline)

### Option B: SPA with Preact + Vite

**Advantages:**
- Modern reactive programming model
- Small bundle size (~3KB for Preact)
- Faster development velocity
- HMR during development

**Disadvantages:**
- Build step required
- NPM dependency chain
- Bundler configuration needed
- Contradicts "no framework" constraint

**Complexity:** Medium

### Option C: Multi-Page App with htmx + Alpine.js

**Advantages:**
- Server-rendered HTML via htmx
- Minimal JS on client
- Familiar mental model

**Disadvantages:**
- Server must render HTML (defeats the thin API bridge goal)
- Real-time updates more complex
- Less control over glassmorphism animations
- Poor for the agent chat streaming use case

**Complexity:** High (server-side rendering)

### Option D: Electron or Tauri Desktop App

**Advantages:**
- Native window management
- System tray integration
- IPC for Python backend

**Disadvantages:**
- Massive complexity increase
- Build pipeline required
- Distribution overhead
- Overkill for v1

**Complexity:** Very High

---

## 5. Recommended Architecture

**Option A: Monolithic SPA with Vanilla JS** is selected.

**Rationale:**
1. The project explicitly requires "vanilla JS, no framework."
2. Zero build step aligns with the project's CLI-first, no-npm philosophy.
3. The existing `cad/server/_frontend` already proved this works (it uses Vite, but the architecture is the same).
4. A component-based vanilla JS architecture, with discipline, produces code that is more maintainable than any framework abstraction for an app of this scope (~20-30 pages).
5. Performance on localhost is already excellent without a virtual DOM.

---

## 6. Component Breakdown

### 6.1 Component Tree

```
App
├── Shell                              # Persistent chrome around the page content
│   ├── TitleBar                       # Custom title bar (for frameless window future)
│   │   ├── AppLogo
│   │   ├── WindowControls (min/max/close)
│   │   └── ConnectionIndicator         # WebSocket status dot
│   ├── Sidebar                        # Left sidebar — navigation + context
│   │   ├── SidebarHeader              # "Fiona" branding + collapse toggle
│   │   ├── NavList                    # Primary navigation
│   │   │   ├── NavItem (Dashboard)
│   │   │   ├── NavItem (Agent Chat)
│   │   │   ├── NavItem (Actions)
│   │   │   ├── NavItem (Bindings)
│   │   │   ├── NavItem (PhiConnect)
│   │   │   ├── NavItem (Vsee)
│   │   │   ├── NavItem (Macros)
│   │   │   ├── NavItem (Terminal)
│   │   │   └── NavItem (Settings)
│   │   └── SidebarFooter              # Collapse toggle, version info
│   ├── MainArea                       # Dynamic — renders current page
│   │   └── <PageComponent>            # One of the page components
│   ├── RightPanel                     # Optional context panel
│   │   ├── PanelHeader
│   │   ├── PanelContent               # Context-sensitive (properties, details)
│   │   └── PanelFooter
│   └── StatusBar                      # Bottom bar
│       ├── StatusMessage              # Current status text
│       ├── ModuleIndicator            # Active module name
│       ├── Clock
│       └── NotificationBadge          # Unread count
│
├── Overlays                           # Modal layer
│   ├── Modal                          # Generic modal container
│   │   ├── ModalHeader
│   │   ├── ModalBody
│   │   └── ModalFooter
│   ├── Toast                          # Notification toast
│   │   ├── ToastIcon
│   │   ├── ToastMessage
│   │   └── ToastDismiss
│   ├── ConfirmDialog                  # Confirmation prompt
│   └── CommandPalette                 # ⌘K / Ctrl+K command palette
│       ├── SearchInput
│       ├── ResultsList
│       └── ResultItem
│
├── Pages                              # Top-level route targets
│   ├── DashboardPage
│   │   ├── StatusGrid
│   │   │   ├── GaugeCard (CPU, Memory, etc.)
│   │   │   └── MetricCard
│   │   ├── RecentActivity
│   │   │   └── ActivityItem
│   │   └── QuickActions
│   │       └── ActionButton
│   ├── AgentChatPage
│   │   ├── ConversationList
│   │   │   └── ConversationItem
│   │   ├── MessageList
│   │   │   └── MessageBubble
│   │   ├── MessageInput
│   │   │   ├── TextArea
│   │   │   ├── SendButton
│   │   │   └── PersonalitySelector
│   │   └── AgentStatusBar
│   ├── ActionsPage
│   │   ├── ActionSearchBar
│   │   ├── ActionFilterBar
│   │   │   ├── RiskFilter
│   │   │   └── CategoryFilter
│   │   └── ActionList
│   │       └── ActionCard
│   │           ├── ActionHeader
│   │           ├── ActionDetail
│   │           └── ActionRunButton
│   ├── PhiConnectPage
│   │   ├── ContactList
│   │   │   └── ContactItem
│   │   ├── ChatView
│   │   │   ├── MessageList
│   │   │   └── ChatInput
│   │   └── SettingsPanel
│   ├── BindingsPage
│   │   ├── BindingSearchBar
│   │   ├── BindingList
│   │   │   └── BindingRow
│   │   └── BindingEditor (modal)
│   ├── MacrosPage
│   │   ├── MacroList
│   │   │   └── MacroCard
│   │   └── MacroEditor (modal)
│   │       └── StepList
│   │           └── StepRow
│   ├── TerminalPage
│   │   ├── TerminalTabs
│   │   ├── TerminalOutput
│   │   └── TerminalInput
│   ├── VseePage
│   │   ├── HologramCanvas
│   │   ├── PointEditor
│   │   ├── EdgeEditor
│   │   └── ViewControls
│   ├── NotificationsPage
│   │   ├── NotificationList
│   │   │   └── NotificationItem
│   │   └── NotificationSettings
│   └── SettingsPage
│       ├── SettingsNav
│       │   └── SettingsNavItem
│       └── SettingsPane
│           ├── GeneralSettings
│           ├── SecuritySettings (ACL, permissions)
│           ├── VoiceSettings
│           ├── MacroSettings
│           ├── ShellSafetySettings
│           └── AboutPane
│
└── Shared (reusable sub-components)
    ├── Badge
    ├── Button (variants: primary, secondary, ghost, danger)
    ├── Card
    ├── Checkbox
    ├── Chip / Tag
    ├── Dropdown / Select
    ├── Icon (SVG wrapper)
    ├── Input (text, search, textarea)
    ├── Kbd (keyboard shortcut display)
    ├── LoadingSpinner
    ├── ProgressBar
    ├── Radio
    ├── ScrollArea
    ├── SearchInput
    ├── Skeleton (loading placeholder)
    ├── Switch / Toggle
    ├── TabBar
    └── Tooltip
```

### 6.2 Module / File Map (Current Implementation)

```
fionaLocalPages/
├── index.html                 # SPA shell with static sidebar HTML
├── css/
│   ├── globals.css            # CSS reset, custom properties, @font-face
│   ├── layout.css             # App shell grid, sidebar, main area, panels
│   ├── components.css         # All BEM component styles
│   ├── themes.css             # Dark theme variables, glassmorphism
│   └── animations.css         # @keyframes, transition classes
│
├── js/
│   ├── app.js                 # Bootstrap: init store, router, api, register routes
│   ├── router.js              # SPA hash-based router + lazy loading
│   ├── state.js               # Reactive store (pub/sub + localStorage persistence)
│   ├── api.js                 # HTTP client + WebSocket client (single connection)
│   ├── template-loader.js     # Fetches .html templates, interpolates {{variables}}
│   ├── flask-shared.js        # Shared helpers for Flask legacy frontend
│   └── components/
│       ├── BaseComponent.js   # Abstract base for reusable components
│       ├── Sidebar.js         # Navigation sidebar
│       ├── StatusBar.js       # Bottom status bar
│       ├── Modal.js           # Modal dialog container
│       ├── Toast.js           # Notification toast
│       ├── Tabs.js            # Tab panel component
│       ├── TabPanel.js        # Individual tab panel
│       ├── SplitPanel.js      # Resizable split layout
│       ├── DataTable.js       # Sortable, filterable data table
│       ├── FileTree.js        # Collapsible file tree explorer
│       ├── CommandPalette.js  # ⌘K global command palette
│       ├── ContextMenu.js     # Right-click context menu
│       ├── LoadingSkeleton.js # Loading skeleton placeholders
│       ├── MetricsCard.js     # Dashboard metric card
│       ├── ActivityTimeline.js# Activity feed timeline
│       └── _icons.js          # SVG icon definitions
│
├── templates/                 # 26 HTML template files
│   ├── dashboard.html
│   ├── chat.html
│   ├── agents.html
│   ├── actions.html
│   ├── bindings.html
│   ├── phiconnect.html
│   ├── macros.html
│   ├── terminal.html
│   ├── notifications.html
│   ├── settings.html
│   ├── performance.html
│   ├── file-explorer.html
│   ├── browser.html
│   ├── tasks.html
│   ├── plugins.html
│   ├── logs.html
│   ├── config.html
│   ├── diagnostics.html
│   ├── devtools.html
│   ├── workspace.html
│   ├── camcoms.html
│   ├── recall.html
│   ├── desktop.html
│   ├── voice.html
│   ├── agent-status.html
│   └── sidebars.html          # Sidebar template partials
│
├── pages/                     # 27 page modules (JS)
│   ├── dashboard.js
│   ├── chat.js
│   ├── agents.js
│   ├── agent-status.js
│   ├── actions.js
│   ├── bindings.js
│   ├── phiconnect.js
│   ├── macros.js
│   ├── terminal.js
│   ├── notifications.js
│   ├── settings.js
│   ├── performance.js
│   ├── file-explorer.js
│   ├── browser.js
│   ├── tasks.js
│   ├── plugins.js
│   ├── logs.js
│   ├── config.js
│   ├── diagnostics.js
│   ├── devtools.js
│   ├── workspace.js
│   ├── camcoms.js
│   ├── recall.js
│   ├── desktop.js
│   ├── voice.js
│   └── _placeholderPage.js    # Stub for routes not yet implemented
│
└── server/                    # Python backend
    ├── app.py                 # aiohttp server — 115+ routes, WebSocket, SSE
    ├── websocket.py            # WebSocket connection manager
    ├── config.py              # Server configuration
    └── handlers/
        ├── __init__.py
        ├── actions.py         # ActionRouter API
        ├── agent.py           # Agent chat + sessions API
        ├── agents_crud.py     # Agent lifecycle CRUD
        ├── bindings.py        # QuikTieper bindings API
        ├── browser.py         # Browser automation (Selenium) API
        ├── camcoms.py         # CamComs encryption API
        ├── config.py          # Configuration API
        ├── desktop.py         # SeeOnDesk desktop awareness API
        ├── files.py           # File browser API
        ├── macros.py          # Macro engine API
        ├── notifications_handler.py # Notifications API
        ├── phiconnect.py      # PhiConnect chat API
        ├── plugins.py         # Plugin metadata API
        ├── quiktieper.py      # QuikTieper access layer API
        ├── recall.py          # RecallVault memory API
        ├── sciretrieval.py    # Scientific knowledge retrieval API
        ├── settings_handler.py# Settings persistence API
        ├── system.py          # System health + capabilities API
        ├── tasks.py           # Task management API
        ├── terminal.py        # Terminal emulation API (cwd tracked server-side)
        ├── tools_handler.py   # Tools execution API
        └── voice.py           # Voice commands API
```

---

## 7. Interfaces

### 7.1 Component Interface (JS Convention)

Every component factory follows this signature:

```js
// Component factory
function createComponent({ store, api, props } = {}) {
    // Returns component controller
    return {
        mount(containerEl, anchorEl),  // Append to DOM
        unmount(),                      // Remove from DOM, clean up
        update(props),                  // Update component with new props
        element,                        // The root DOM element (after mount)
        // ... component-specific methods
    };
}
```

Every component that subscribes to the store receives an `unsubscribe` function returned during `mount()` and calls it during `unmount()`.

### 7.2 Page Interface

```js
function createPage({ store, api, router }) {
    return {
        mount(containerEl),
        unmount(),        // Called on route exit
        onEnter(),        // Route guard / init hook
        onLeave(),        // Route cleanup hook
        title,            // Page title for document.title + sidebar
        element,
    };
}
```

### 7.3 API Module Interface

```js
// Each api/ module exports an object:
const ActionsApi = {
    // REST methods — return Promises
    list(filter)     -> GET  /api/actions
    get(name)        -> GET  /api/actions/:name
    run(name, opts)  -> POST /api/actions/:name/run

    // WebSocket event subscriptions
    // Return unsubscribe functions
    onActionResult(callback),
    onActionProgress(callback),
};
```

---

## 8. Data Flow

### 8.1 High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (Frontend)                        │
│                                                                   │
│  ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌──────────────┐   │
│  │  Pages   │──▶│Components│──▶│  Store  │◀──│   API Client │   │
│  │ (render) │   │ (events) │   │ (state) │   │  (HTTP + WS) │   │
│  └─────────┘   └──────────┘   └─────────┘   └──────┬───────┘   │
│        ▲                                             │           │
│        │           ┌────────────┐                   │           │
│        └───────────│   Router   │                   │           │
│                    │ (hash SPA) │                   │           │
│                    └────────────┘                   │           │
└─────────────────────────────────────────────────────┼───────────┘
                                                      │
              HTTP REST ────────┐                     │ WebSocket
              + SSE/events      │                     │ JSON-RPC 2.0
                                │                     │
┌───────────────────────────────┼─────────────────────┼───────────┐
│            API Bridge Server (Python aiohttp/FastAPI)            │
│                                                                   │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────────┐  │
│  │ HTTP API │   │ WebSocket    │   │ EventBus Subscriber      │  │
│  │ Handlers │   │ Handler      │   │ (forwards backend events │  │
│  └────┬─────┘   └──────┬───────┘   │  → WS to frontend)       │  │
│       │                │           └──────────┬───────────────┘  │
│       ▼                ▼                      │                  │
│  ┌──────────────────────────────────────────────┐               │
│  │         API Router / Request Handler          │               │
│  │  (imports FionaCore, QuikTieper, Agent, ...)  │               │
│  └──────────────────────┬───────────────────────┘               │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────┐               │
│  │           Existing Fiona Python Modules       │               │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │               │
│  │  │Actions  │ │Agent     │ │QuikTieper    │  │               │
│  │  │Router   │ │ChatHandler│ │Bindings      │  │               │
│  │  ├─────────┤ ├──────────┤ ├──────────────┤  │               │
│  │  │CamComs  │ │Macros    │ │Notifications │  │               │
│  │  │         │ │Engine    │ │              │  │               │
│  │  └─────────┘ └──────────┘ └──────────────┘  │               │
│  └──────────────────────────────────────────────┘               │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### 8.2 Data Flow Scenarios

**Scenario A: Page Load (e.g., ActionsPage)**

```
1. Router matches #/actions → unmounts previous page, mounts ActionsPage
2. ActionsPage.onEnter() is called
3. Page subscribes to store slice: store.subscribe('actions', render)
4. Page calls api.actions.list() → HTTP GET /api/actions
5. API client sends request, returns Promise
6. On response, API client calls store.set('actions', data)
7. Store fires 'actions' event
8. Page's subscription callback fires → render() with new data
9. Component tree re-renders affected DOM
```

**Scenario B: User Runs an Action**

```
1. User clicks "Run" on ActionCard
2. ActionCard emits custom event 'action:run' with action name
3. ActionsPage catches event, calls api.actions.run(name, params)
4. API client sends HTTP POST /api/actions/:name/run
5. Python handler calls ActionRouter.run() → executes command
6. Response returns with ActionResult
7. API client calls store.set('lastActionResult', result)
8. Page re-renders result (Toast notification)
```

**Scenario C: Real-time Update (e.g., Agent Chat streaming)**

```
1. User types message, clicks Send
2. MessageInput emits 'message:send' with text
3. AgentChatPage calls api.agent.sendMessage(sessionId, text)
4. API sends HTTP POST /api/agent/chat/:sessionId/message
5. Python calls AgentChatHandler.send_message() which calls Ollama
6. Ollama streams tokens back → Python yields tokens via Server-Sent Events
   OR Python sends tokens one-by-one over WebSocket as JSON-RPC notifications
7. Frontend API client receives each token
8. Calls store.set('agent.streamToken', token) for each token
9. MessageBubble component streams token into DOM
```

**Scenario D: WebSocket Reconnection**

```
1. WebSocket disconnects (server restart, network blip)
2. api.js detects onclose
3. Dispatches store.set('connection.status', 'disconnected')
4. ConnectionIndicator turns red, StatusBar shows "Reconnecting..."
5. Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
6. On reconnect: api.js calls handshake()
7. Server replays missed events (via event log / version counter)
8. store.set('connection.status', 'connected')
9. ConnectionIndicator turns green
```

### 8.3 Unidirectional Data Flow Rules

1. **User interaction → Component event → Page handler → API call → Store mutation → Re-render**
2. **No component directly mutates the store** — only API wrappers and the page coordinator may call `store.set()`
3. **No component calls the API directly** — only page coordinators
4. **WebSocket events → API client → Store mutation → Re-render**
5. **Router only changes the URL hash and mounts/unmounts pages** — it never touches the store

---

## 9. State Management Design

### 9.1 Store Architecture

The store uses a **pub/sub (observer) pattern** with namespaced slices. The store is a singleton created in `app.js` and injected into all components.

```js
// Store API
const store = new Store({
    initialState: {
        // Connection
        connection: {
            status: 'disconnected',  // 'disconnected' | 'connecting' | 'connected' | 'error'
            serverInfo: null,         // Server version, capabilities
            reconnectAttempts: 0,
        },

        // Global UI state
        ui: {
            sidebarCollapsed: false,
            rightPanelOpen: false,
            rightPanelContent: null,
            theme: 'dark',
            toasts: [],
            modals: [],
            commandPaletteOpen: false,
        },

        // Dashboard
        dashboard: {
            status: null,             // Overall system status
            gauges: {},               // keyed by gauge name
            recentActivity: [],
        },

        // Agent
        agent: {
            sessions: [],             // Conversation list
            activeSessionId: null,
            messages: [],             // Current session messages
            streamToken: null,        // Streaming token buffer
            isResponding: false,
            personalities: [],
            activePersonality: null,
        },

        // Actions
        actions: {
            list: [],                 // All available actions
            filter: {},               // Current filter state
            searchQuery: '',
            lastResult: null,         // Last action execution result
            isRunning: null,          // Action name currently running
        },

        // PhiConnect
        phiconnect: {
            contacts: [],
            activeContactId: null,
            messages: [],             // Current chat messages
            serverStatus: 'stopped',
            settings: {},
        },

        // Bindings
        bindings: {
            list: [],
            searchQuery: '',
        },

        // Macros
        macros: {
            list: [],
            activeMacroId: null,
        },

        // Terminal
        terminal: {
            sessions: {},
            activeSessionId: null,
        },

        // Vsee
        vsee: {
            points: '',
            edges: '',
            renderState: null,
        },

        // Notifications
        notifications: {
            items: [],
            unreadCount: 0,
        },

        // Settings
        settings: {
            general: {},
            security: {},             // ACL, permissions
            voice: {},
            shellSafety: {},
            about: {},
            isDirty: {},              // Track unsaved changes per section
        },
    },
});
```

### 9.2 Store Methods

```js
class Store {
    // Get entire state or a slice by path
    get(path?: string): any

    // Set a value at a path and notify subscribers
    set(path: string, value: any, { silent?: boolean } = {}): void

    // Update a slice shallowly (merge)
    update(path: string, partial: object, { silent?: boolean } = {}): void

    // Subscribe to changes at a path (supports wildcards)
    subscribe(path: string, callback: (newValue, oldValue) => void): () => void
    // Returns unsubscribe function

    // Subscribe to all changes
    subscribeAll(callback: (path, newValue, oldValue) => void): () => void

    // Reset state to initial (on full reconnect)
    reset(path?: string): void

    // Create a derived/sub-store that computes from another path
    derive(path: string, transform: (value) => any): ReadOnlyStore
}
```

### 9.3 Path Convention

Paths use dot notation: `'actions.list'`, `'agent.messages'`, `'ui.toasts'`.

Wildcard subscriptions: `'agent.*'` subscribes to all changes under `agent`. `'*'` subscribes to everything.

### 9.4 Persistence Strategy

| Data | Strategy | Mechanism |
|------|----------|-----------|
| UI state (sidebar collapse, panel state) | `localStorage` | On every `ui.*` change, debounced 1s sync |
| Active session IDs | `localStorage` | On route change |
| Theme preference | `localStorage` | On `ui.theme` change |
| Server URL | `localStorage` | On settings save |
| Notifications | In-memory only | Refreshed from server on connect |
| Agent sessions | Server-side | API calls |
| Action history | Server-side | API calls / CmdTrace |
| Sensitive data | Never persisted | No tokens, keys, or credentials stored in browser |

Persistence is handled by a single module `js/persist.js` that subscribes to the store and writes to `localStorage`. On app boot, it reads `localStorage` and hydrates the store.

### 9.5 Action Types (convention)

All state mutations are implicit — the store has no action/reducer concept. Mutations happen via `store.set()` and `store.update()`. The pattern of "who sets what" is documented in the API modules:

```js
// api/actions.js — documents the mutations it performs:
//   store.set('actions.list', data)         // After GET /api/actions
//   store.set('actions.lastResult', result)  // After POST /api/actions/:name/run
//   store.set('actions.isRunning', name)     // Before running
//   store.set('actions.isRunning', null)     // After completion
```

---

## 10. Router Design

### 10.1 Route Table

```js
// Implemented route table (27 routes in js/app.js)
const ROUTES = [
  { path: '/',              name: 'dashboard',     title: 'Dashboard',         icon: 'dashboard' },
  { path: '/chat',          name: 'chat',          title: 'AI Chat',           icon: 'message' },
  { path: '/agents',        name: 'agents',        title: 'Agents',            icon: 'bot' },
  { path: '/agents/:id',    name: 'agent-detail',  title: 'Agent Detail',      icon: 'bot' },
  { path: '/actions',       name: 'actions',       title: 'Actions',           icon: 'bolt' },
  { path: '/bindings',      name: 'bindings',      title: 'Key Bindings',      icon: 'keyboard' },
  { path: '/phiconnect',    name: 'phiconnect',    title: 'PhiConnect',        icon: 'lock' },
  { path: '/macros',        name: 'macros',        title: 'Macros',            icon: 'play' },
  { path: '/terminal',      name: 'terminal',      title: 'Terminal',          icon: 'terminal' },
  { path: '/notifications', name: 'notifications',  title: 'Notifications',     icon: 'bell' },
  { path: '/settings',      name: 'settings',      title: 'Settings',          icon: 'gear' },
  { path: '/performance',   name: 'performance',   title: 'Performance',       icon: 'activity' },
  { path: '/files',         name: 'files',         title: 'Files',             icon: 'folder' },
  { path: '/browser',       name: 'browser',       title: 'Browser',           icon: 'globe' },
  { path: '/tasks',         name: 'tasks',         title: 'Tasks',             icon: 'check-circle' },
  { path: '/plugins',       name: 'plugins',       title: 'Plugins',           icon: 'puzzle' },
  { path: '/logs',          name: 'logs',          title: 'Logs',              icon: 'activity' },
  { path: '/config',        name: 'config',        title: 'Configuration',     icon: 'gear' },
  { path: '/diagnostics',   name: 'diagnostics',   title: 'Diagnostics',       icon: 'activity' },
  { path: '/devtools',      name: 'devtools',      title: 'Developer Tools',   icon: 'terminal' },
  { path: '/workspace',     name: 'workspace',     title: 'Workspace',         icon: 'folder' },
  { path: '/camcoms',       name: 'camcoms',       title: 'CamComs',           icon: 'wifi' },
  { path: '/recall',        name: 'recall',        title: 'RecallVault',       icon: 'search' },
  { path: '/desktop',       name: 'desktop',       title: 'SeeOnDesk',         icon: 'maximize' },
  { path: '/voice',         name: 'voice',         title: 'Voice Commands',    icon: 'message' },
];
```

### 10.2 Router API

```js
class Router {
    constructor({ routes, store, containerEl });

    // Navigate to a path
    navigate(path: string, { replace?: boolean } = {}): void;

    // Current route info
    get currentRoute(): { path, page, params, query };

    // Current path (hash)
    get currentPath(): string;

    // Go back
    back(): void;

    // Build URL with params
    buildUrl(path: string, params?: object, query?: object): string;

    // Subscribe to route changes
    onChange(callback: (route) => void): () => void;
}
```

### 10.3 Lifecycle Hooks

Every page can define:

```js
const page = {
    // Called before mount — can return false to cancel navigation
    async beforeEnter({ from, to, params, router, store }) {
        // Return true to proceed, false to cancel
        // Can also redirect: router.navigate('/other')
    },

    // Called after DOM is mounted
    async onEnter({ from, params, router, store, api }) {
        // Initialize data, subscribe to store, etc.
    },

    // Called before unmount
    async onLeave({ to, router, store }) {
        // Cleanup: unsubscribe, save state, etc.
    },

    // Called when route params change but same page
    async onUpdate({ params, router, store }) {
        // Handle param changes without full remount
    },
};
```

### 10.4 Route Guards

Route guards are defined in the route definition:

```js
const ROUTES = {
    '/settings/security': {
        page: 'SecuritySettings',
        title: 'Security',
        guard: async ({ store }) => {
            // Must be connected to server
            if (store.get('connection.status') !== 'connected') {
                return { redirect: '/' };
            }
            // Must have permission
            const permitted = await api.settings.checkPermission('security');
            if (!permitted) {
                return { redirect: '/settings/general' };
            }
            return true;
        },
    },
};
```

### 10.5 404 Handling

Any unmatched route renders a `NotFoundPage` with a link back to `/`.

---

## 11. API Contract

### 11.1 REST Endpoints

Base URL: `http://127.0.0.1:9876/api/v1`

#### System

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/health` | Server health check | `{ status, version, uptime }` |
| GET | `/api/v1/capabilities` | List server capabilities | `{ modules: [...], features: [...] }` |
| POST | `/api/v1/restart` | Restart server (admin) | `{ ok }`  |

#### Actions

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/actions` | List all actions | `[{ name, description, risk, permission, ... }]` |
| GET | `/api/v1/actions/:name` | Get action details | `{ name, description, ... }` |
| POST | `/api/v1/actions/:name/run` | Execute an action | `{ ok, action, detail, stdout, stderr, ... }` |

#### Agent Chat

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/agent/sessions` | List chat sessions | `[{ id, name, created, messageCount }]` |
| POST | `/api/v1/agent/sessions` | Create session | `{ id, name }` |
| GET | `/api/v1/agent/sessions/:id` | Get session | `{ id, name, messages: [...] }` |
| DELETE | `/api/v1/agent/sessions/:id` | Delete session | `{ ok }` |
| POST | `/api/v1/agent/sessions/:id/message` | Send message (streams response) | SSE stream of tokens |

#### Agents CRUD

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/agents` | List all agents | `[{ id, name, status, ... }]` |
| POST | `/api/v1/agents` | Create agent | `{ id, name, model, ... }` |
| POST | `/api/v1/agents/:id/pause` | Pause agent | `{ ok }` |
| POST | `/api/v1/agents/:id/resume` | Resume agent | `{ ok }` |
| POST | `/api/v1/agents/:id/stop` | Stop agent | `{ ok }` |
| POST | `/api/v1/agents/:id/restart` | Restart agent | `{ ok }` |
| GET | `/api/v1/agents/models` | List available models | `[{ name, ... }]` |

#### Bindings

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/bindings` | List all bindings | `[{ name, command, keys, ... }]` |
| GET | `/api/v1/bindings/apps` | List discoverable apps | `[{ name, exec, ... }]` |
| POST | `/api/v1/bindings/save` | Save bindings | `{ ok }` |

#### Browser Automation (Selenium)

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/v1/browser/start` | Start browser instance | `{ ok, context_id }` |
| POST | `/api/v1/browser/stop` | Stop browser instance | `{ ok }` |
| GET | `/api/v1/browser/status` | Browser status | `{ running, context_id, ... }` |
| POST | `/api/v1/browser/navigate` | Navigate to URL | `{ ok, title, url }` |
| POST | `/api/v1/browser/click` | Click element | `{ ok }` |
| POST | `/api/v1/browser/type` | Type text | `{ ok }` |
| POST | `/api/v1/browser/screenshot` | Capture screenshot | `{ ok, image_data }` |

#### CamComs

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/camcoms/status` | CamComs status | `{ running, keys, ... }` |
| POST | `/api/v1/camcoms/encrypt` | Encrypt message | `{ ciphertext }` |
| POST | `/api/v1/camcoms/decrypt` | Decrypt message | `{ plaintext }` |
| POST | `/api/v1/camcoms/send` | Send encrypted message | `{ ok }` |

#### Desktop (SeeOnDesk)

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/desktop/status` | Desktop awareness status | `{ active_window, ... }` |

#### Files

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/files/list` | List directory | `[{ name, path, type, size, ... }]` |
| GET | `/api/v1/files/read` | Read file content | `{ content }` |
| POST | `/api/v1/files/write` | Write file content | `{ ok }` |

#### Macros

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/macros` | List macros | `[{ name, steps, ... }]` |
| POST | `/api/v1/macros` | Create macro | `{ name, steps }` |
| PUT | `/api/v1/macros/:name` | Update macro | `{ name, steps }` |
| DELETE | `/api/v1/macros/:name` | Delete macro | `{ ok }` |
| POST | `/api/v1/macros/:name/run` | Run macro | `{ ok, results }` |

#### Notifications

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/notifications` | List notifications | `[{ id, message, level, timestamp }]` |
| POST | `/api/v1/notifications` | Send notification | `{ id }` |
| DELETE | `/api/v1/notifications/:id` | Dismiss notification | `{ ok }` |

#### PhiConnect

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/phiconnect/status` | Server status | `{ running, port, ... }` |
| GET | `/api/v1/phiconnect/identity` | Local identity | `{ fingerprint, ... }` |
| GET | `/api/v1/phiconnect/messages` | Get messages | `[{ from, to, content, timestamp }]` |
| POST | `/api/v1/phiconnect/send` | Send message | `{ ok }` |
| POST | `/api/v1/phiconnect/trust` | Manage trusted peers | `{ ok }` |

#### Plugins

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/plugins` | List available plugins | `[{ id, name, version, ... }]` |

#### QuikTieper

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/quiktieper/status` | QuikTieper status | `{ running, bindings_count, ... }` |
| GET | `/api/v1/quiktieper/presets` | List presets | `[{ name, bindings, ... }]` |
| POST | `/api/v1/quiktieper/launcher` | Run app launcher | `{ ok }` |
| POST | `/api/v1/quiktieper/import-apps` | Import desktop apps | `{ imported, total }` |
| POST | `/api/v1/quiktieper/assign-keys` | Assign launch keys | `{ assigned, ... }` |

#### RecallVault

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/recall/search` | Search recall store | `[{ key, value, timestamp }]` |
| POST | `/api/v1/recall/remember` | Store a value | `{ ok }` |
| DELETE | `/api/v1/recall/forget/:key` | Remove a value | `{ ok }` |
| GET | `/api/v1/recall/categories` | List categories | `[string]` |

#### Scientific Retrieval

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/sciretrieval/search` | Scientific search query | `{ results }` |

#### Settings

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/settings` | Get all settings | `{ general, security, ... }` |
| PUT | `/api/v1/settings` | Update all settings | `{ ok }` |

#### System

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/tasks` | List tasks | `[{ id, name, status, ... }]` |

#### Terminal (cwd tracked server-side)

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/v1/terminal/execute` | Execute command | `{ stdout, stderr, returncode, cwd }` |
| GET | `/api/v1/terminal/autocomplete` | Get completions | `{ suggestions }` |
| POST | `/api/v1/terminal/autocomplete` | Get completions (POST) | `{ suggestions }` |
| GET | `/api/v1/terminal/cwd` | Get current working directory | `{ cwd }` |

#### Tools

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/tools` | List tools | `[{ id, name, ... }]` |
| POST | `/api/v1/tools/execute` | Execute tool | `{ result }` |

#### Voice

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/v1/voice/status` | Voice system status | `{ listening, ... }` |
| POST | `/api/v1/voice/command` | Execute voice command | `{ ok }` |

### 11.2 WebSocket Events

**Connection:** `ws://127.0.0.1:9876/ws`

**Protocol:** JSON-RPC 2.0 over WebSocket (same pattern as existing `cad/server/`)

**Handshake:**

```json
// Client → Server
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "handshake",
    "params": {
        "client_name": "fiona-localpages",
        "client_version": "1.0.0",
        "protocol_version": "1.0",
        "capabilities": ["full_state", "incremental_updates"]
    }
}

// Server → Client
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "server_name": "fiona-api",
        "server_version": "0.1.0",
        "protocol_version": "1.0",
        "modules": ["actions", "agent", "bindings", "phiconnect", ...],
        "capabilities": ["events", "streaming", "full_state"]
    }
}
```

**Server-to-Client Events (JSON-RPC Notifications):**

```json
// No "id" field — these are notifications

// Connection lifecycle
{"jsonrpc":"2.0","method":"connection.ready","params":{"serverInfo": {...}}}
{"jsonrpc":"2.0","method":"connection.heartbeat","params":{"timestamp": ...}}

// Agent streaming
{"jsonrpc":"2.0","method":"agent.token","params":{"sessionId":"...","token":"..."}}
{"jsonrpc":"2.0","method":"agent.done","params":{"sessionId":"...","fullResponse":"..."}}
{"jsonrpc":"2.0","method":"agent.error","params":{"sessionId":"...","error":"..."}}

// Action updates
{"jsonrpc":"2.0","method":"action.started","params":{"name":"...","id":"..."}}
{"jsonrpc":"2.0","method":"action.completed","params":{"name":"...","id":"...","result":{...}}}
{"jsonrpc":"2.0","method":"action.progress","params":{"name":"...","progress":0.5,"message":"..."}}

// System events
{"jsonrpc":"2.0","method":"system.notification","params":{"id":"...","level":"info","message":"...","timestamp":"..."}}

// Document state (for Vsee/CAD)
{"jsonrpc":"2.0","method":"document.updated","params":{"changeSet":{...}}}
{"jsonrpc":"2.0","method":"document.selection","params":{"uid":"..."}}

// PhiConnect events
{"jsonrpc":"2.0","method":"phiconnect.message","params":{"from":"...","content":"...","timestamp":"..."}}
{"jsonrpc":"2.0","method":"phiconnect.status","params":{"running":true,"port":8766}}

// Binding changes (cross-process sync)
{"jsonrpc":"2.0","method":"bindings.updated","params":{"bindings":[...]}}
```

**All HTTP endpoints return standardized JSON envelopes:**

```json
// Success
{ "ok": true, "data": ..., "meta": { "timestamp": "...", "duration_ms": 12 } }

// Error
{ "ok": false, "error": { "code": "NOT_FOUND", "message": "Action not found" }, "meta": { "timestamp": "..." } }
```

---

## 12. CSS Architecture

### 12.1 Design Tokens

Defined as CSS custom properties in `css/globals.css`:

```css
:root {
    /* ── Color Palette ──────────────────────────────────── */
    --color-bg-base:        #0f111a;
    --color-bg-surface:     #1a1c25;
    --color-bg-elevated:    #22242f;
    --color-bg-hover:       #2a2d3a;
    --color-bg-active:      #32354a;

    --color-border-default: #2e3140;
    --color-border-subtle:  #232635;
    --color-border-accent:  #00f0ff33;

    --color-text-primary:   #e2e8f0;
    --color-text-secondary: #94a3b8;
    --color-text-muted:     #64748b;
    --color-text-inverse:   #0f111a;

    --color-accent:         #00f0ff;
    --color-accent-hover:   #33f3ff;
    --color-accent-muted:   #00f0ff22;

    --color-info:           #38bdf8;
    --color-success:        #22c55e;
    --color-warning:        #eab308;
    --color-error:          #ef4444;

    /* ── Glassmorphism ───────────────────────────────────── */
    --glass-bg:             rgba(26, 28, 37, 0.7);
    --glass-border:         rgba(255, 255, 255, 0.06);
    --glass-blur:           12px;

    /* ── Spacing (4px base) ──────────────────────────────── */
    --space-0:    0px;
    --space-1:    4px;
    --space-2:    8px;
    --space-3:    12px;
    --space-4:    16px;
    --space-5:    20px;
    --space-6:    24px;
    --space-8:    32px;
    --space-10:   40px;
    --space-12:   48px;
    --space-16:   64px;

    /* ── Typography ──────────────────────────────────────── */
    --font-family:            'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-mono:              'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    --font-size-xs:           11px;
    --font-size-sm:           13px;
    --font-size-base:         14px;
    --font-size-lg:           16px;
    --font-size-xl:           20px;
    --font-size-2xl:          24px;
    --font-size-3xl:          32px;
    --font-weight-normal:     400;
    --font-weight-medium:     500;
    --font-weight-semibold:   600;
    --font-weight-bold:       700;
    --line-height-tight:      1.25;
    --line-height-normal:     1.5;
    --line-height-relaxed:    1.75;

    /* ── Border Radius ───────────────────────────────────── */
    --radius-sm:      4px;
    --radius-md:      8px;
    --radius-lg:      12px;
    --radius-xl:      16px;
    --radius-full:    9999px;

    /* ── Shadows ─────────────────────────────────────────── */
    --shadow-sm:      0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-md:      0 4px 12px rgba(0, 0, 0, 0.4);
    --shadow-lg:      0 8px 24px rgba(0, 0, 0, 0.5);
    --shadow-glow:    0 0 20px rgba(0, 240, 255, 0.15);

    /* ── Z-Index Scale ───────────────────────────────────── */
    --z-base:          0;
    --z-sidebar:       10;
    --z-header:        20;
    --z-overlay:       30;
    --z-modal:         40;
    --z-toast:         50;
    --z-command-palette: 60;
    --z-tooltip:       70;

    /* ── Transitions ─────────────────────────────────────── */
    --transition-fast:     150ms ease;
    --transition-normal:   250ms ease;
    --transition-slow:     400ms ease;
    --transition-spring:   300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

### 12.2 Naming Convention: BEM

```css
/* Block */
.sidebar { ... }

/* Block__Element */
.sidebar__header { ... }
.sidebar__nav { ... }
.sidebar__footer { ... }

/* Block--Modifier */
.sidebar--collapsed { ... }
.sidebar--expanded { ... }

/* Block__Element--Modifier */
.sidebar__nav-item--active { ... }
.sidebar__nav-item--disabled { ... }

/* Component class prefix: c- */
.c-card { ... }
.c-button { ... }
.c-button--primary { ... }
.c-button--ghost { ... }

/* Utility classes */
.u-hidden { display: none !important; }
.u-flex-center { display: flex; align-items: center; justify-content: center; }
.u-text-muted { color: var(--color-text-muted); }

/* State classes (js-managed) */
.is-loading { opacity: 0.6; pointer-events: none; }
.is-active { ... }
.is-error { ... }
```

### 12.3 CSS File Responsibilities

| File | Purpose | Size (est.) |
|------|---------|-------------|
| `globals.css` | CSS reset, custom properties, @font-face, base element styles | 4KB |
| `layout.css` | App shell grid, sidebar, main area, panels, status bar | 3KB |
| `components.css` | All BEM component styles (cards, buttons, inputs, modals, etc.) | 8KB |
| `animations.css` | @keyframes, transition utilities, animation classes | 2KB |
| `themes.css` | Dark theme variables, glassmorphism classes, scrollbar styling | 2KB |

### 12.4 Glassmorphism Pattern

```css
.glass {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
}

.glass--strong {
    background: rgba(26, 28, 37, 0.85);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.08);
}
```

---

## 13. Module Dependency Graph

```
index.html                              # SPA shell — loads only js/app.js
└── js/app.js                           # Bootstrap entry (singleton module)
    ├── js/state.js                     # Reactive store (pub/sub, no deps)
    ├── js/router.js                    # Hash-based router (no deps)
    ├── js/api.js                       # HTTP + WebSocket client (singleton)
    ├── js/template-loader.js           # Fetches .html, interpolates {{vars}}
    │
    ├── js/components/                   # Reusable UI widgets
    │   ├── BaseComponent.js
    │   ├── Sidebar.js                  # Depends on state.js
    │   ├── StatusBar.js                # Depends on state.js
    │   ├── Modal.js                    # Depends on state.js
    │   ├── Toast.js                    # Depends on state.js
    │   ├── Tabs.js                     # Depends on state.js
    │   ├── TabPanel.js
    │   ├── SplitPanel.js
    │   ├── DataTable.js                # Depends on state.js
    │   ├── FileTree.js
    │   ├── CommandPalette.js           # Depends on state.js
    │   ├── ContextMenu.js
    │   ├── LoadingSkeleton.js
    │   ├── MetricsCard.js
    │   ├── ActivityTimeline.js
    │   └── _icons.js                   # SVG icon defs
    │
    ├── templates/                      # 26 .html files (loaded lazily)
    │   ├── dashboard.html              # via template-loader.js
    │   ├── chat.html                   # using fetch() + innerHTML
    │   ├── agents.html
    │   ├── ... (26 total, see §6.2)
    │   └── sidebars.html
    │
    └── pages/                          # 27 page modules (loaded lazily)
        ├── dashboard.js                # Uses state.js, api.js, template-loader.js
        ├── chat.js
        ├── agents.js
        ├── agent-status.js
        ├── actions.js
        ├── bindings.js
        ├── phiconnect.js
        ├── macros.js
        ├── terminal.js
        ├── notifications.js
        ├── settings.js
        ├── performance.js
        ├── file-explorer.js
        ├── browser.js
        ├── tasks.js
        ├── plugins.js
        ├── logs.js
        ├── config.js
        ├── diagnostics.js
        ├── devtools.js
        ├── workspace.js
        ├── camcoms.js
        ├── recall.js
        ├── desktop.js
        ├── voice.js
        └── _placeholderPage.js
```

**Key decisions:**

1. `index.html` loads only `js/app.js` via `<script type="module">`.
2. `app.js` uses dynamic `import()` to load pages lazily when routed.
3. `api.js` is a singleton — all API modules get a reference to the same instance at init time.
4. `state.js` is a singleton — every component/page gets a reference to the same store.
5. Pages are NOT in the import graph until navigated to — this keeps initial load fast.
6. `components/` HTML partials in `components/` are fetched via `fetch()` and inserted as innerHTML.

### 13.1 Lazy Loading Strategy

```js
// app.js — route configuration (simplified)
const routes = [
  { path: '/',         component: () => import('../pages/dashboard.js'), ... },
  { path: '/chat',     component: () => import('../pages/chat.js'), ... },
  { path: '/terminal', component: () => import('../pages/terminal.js'), ... },
  // ... 26 routes total
];
```

Each page module exports either a plain object `{ render, mount, destroy }` or a factory function `createPage(...)`. The router handles both export patterns (added as a fix for blank pages when object exports were not handled).

---

## 14. API Server Architecture (Python)

### 14.1 High-Level Design

```
server/
├── app.py              # Entry point — aiohttp app, 115+ routes, WebSocket at /ws, SSE
├── websocket.py         # WebSocket connection manager (ping-pong, peer tracking, periodic push)
├── config.py           # Server configuration
└── handlers/           # Request handlers (24 modules)
    ├── __init__.py
    ├── actions.py              # ActionRouter API
    ├── agent.py                # Agent chat + sessions
    ├── agents_crud.py          # Agent lifecycle CRUD
    ├── bindings.py             # QuikTieper bindings
    ├── browser.py              # Selenium browser automation
    ├── camcoms.py              # CamComs encryption
    ├── config.py               # Server configuration
    ├── desktop.py              # SeeOnDesk desktop awareness
    ├── files.py                # File browser
    ├── macros.py               # Macro engine
    ├── notifications_handler.py# Notifications
    ├── phiconnect.py           # PhiConnect chat
    ├── plugins.py              # Plugin metadata
    ├── quiktieper.py           # QuikTieper access layer
    ├── recall.py               # RecallVault memory
    ├── sciretrieval.py         # Scientific knowledge retrieval
    ├── settings_handler.py     # Settings persistence (settings.txt)
    ├── system.py               # System health + capabilities
    ├── tasks.py                # Task management
    ├── terminal.py             # Terminal emulation (cwd tracked server-side)
    ├── tools_handler.py        # Tools execution
    └── voice.py                # Voice commands
```

### 14.2 Python Server — `app.py` (skeleton)

```python
"""Fiona HTTP + WebSocket API Server.

Imports existing Fiona modules directly and exposes them over
REST and WebSocket.  Designed to be launched from the Fiona CLI
or run standalone.
"""

import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web, web_ws

from fiona.di import FionaContainer
from fiona.interfaces import EventBus
from FionaCore import ActionRouter, default_action_specs
from fiona import get_logger

logger = get_logger(__name__)


def create_app(container: FionaContainer | None = None) -> web.Application:
    """Build the aiohttp application with all routes and middleware."""
    if container is None:
        container = _build_container()

    app = web.Application(middlewares=[error_middleware, timing_middleware])

    # Store container in app context
    app['container'] = container
    app['event_bus'] = container.resolve('event_bus')

    # Register REST routes
    _register_routes(app, container)

    # Register WebSocket endpoint
    app.router.add_get('/ws', ws_handler)

    # Register static file serving for fionaLocalPages
    app.router.add_static('/', Path(__file__).parent.parent, show_index=True)

    # Start EventBus → WebSocket bridge
    app.on_startup.append(_start_event_bridge)

    return app


def _build_container() -> FionaContainer:
    """Build and wire the dependency injection container."""
    container = FionaContainer()

    # Core services
    container.register_instance('event_bus', EventBus())
    container.register_instance('action_router', ActionRouter(default_action_specs()))

    # Subsystem services (imported lazily on first use)
    container.register_factory('chat_handler', lambda: _import_chat_handler())
    container.register_factory('binding_manager', lambda: _import_binding_manager())
    # ... etc

    return container


# Module-level WebSocket connections set
# (In production, replace with a connection manager)
_ws_connections: set[web_ws.WebSocketResponse] = set()


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle WebSocket upgrade and lifecycle."""
    ws = web_ws.WebSocketResponse()
    await ws.prepare(request)
    _ws_connections.add(ws)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                # Handle JSON-RPC requests
                await _handle_rpc(ws, data)
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WS error: {ws.exception()}")
    finally:
        _ws_connections.discard(ws)

    return ws


async def _start_event_bridge(app: web.Application):
    """Bridge EventBus events to WebSocket."""
    bus: EventBus = app['event_bus']

    # Define what events get bridged and their WS event names
    EVENT_MAP = {
        # 'DocumentModified': 'document.updated',
    }

    subscriptions = []
    for py_event, ws_event in EVENT_MAP.items():
        sub = bus.subscribe(py_event, lambda e, name=ws_event: _broadcast(name, e))
        subscriptions.append(sub)

    app['event_bridge_subs'] = subscriptions


def _broadcast(method: str, params: dict):
    """Send a JSON-RPC notification to all connected WebSocket clients."""
    payload = json.dumps({
        'jsonrpc': '2.0',
        'method': method,
        'params': params,
    })
    for ws in _ws_connections.copy():
        try:
            asyncio.ensure_future(ws.send_str(payload))
        except Exception:
            _ws_connections.discard(ws)


def main(host='127.0.0.1', port=9876):
    """Run the server."""
    app = create_app()
    web.run_app(app, host=host, port=port)


if __name__ == '__main__':
    main()
```

### 14.3 Handler Pattern

Each handler module follows this pattern:

```python
# handlers/actions.py

from FionaCore import ActionRouter, ActionResult


async def list_actions(request: web.Request) -> web.Response:
    """GET /api/actions"""
    router: ActionRouter = request.app['container'].resolve('action_router')
    actions = router.list_actions()
    return web.json_response({'ok': True, 'data': actions})


async def get_action(request: web.Request) -> web.Response:
    """GET /api/actions/{name}"""
    name = request.match_info['name']
    router: ActionRouter = request.app['container'].resolve('action_router')
    try:
        spec = router.get(name)
        return web.json_response({'ok': True, 'data': spec.to_dict()})
    except ValueError as e:
        return web.json_response({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': str(e)}}, status=404)


async def run_action(request: web.Request) -> web.Response:
    """POST /api/actions/{name}/run"""
    name = request.match_info['name']
    body = await request.json()
    router: ActionRouter = request.app['container'].resolve('action_router')

    try:
        result = router.run(
            name,
            source=body.get('source', 'web'),
            permission_profile=body.get('permission_profile', 'local'),
            dry_run=body.get('dry_run', False),
            timeout_seconds=body.get('timeout_seconds', 30),
        )
        return web.json_response({'ok': True, 'data': result.to_dict()})
    except ValueError as e:
        return web.json_response({'ok': False, 'error': {'code': 'INVALID', 'message': str(e)}}, status=400)
```

---

## 15. Architecture Decision Records

### ADR-001: Vanilla JS over Framework

**Decision:** Use vanilla JavaScript with a component-based pattern instead of React, Vue, or Svelte.

**Context:** The project requires "vanilla JS, no framework." The frontend has ~20-30 pages, moderate complexity, and a single developer. Frameworks introduce build tooling, dependency chains, and abstraction overhead.

**Alternatives considered:**
- **Preact + Vite:** Smaller than React, but still has build step and NPM dependency.
- **Vue + Vite:** More approachable but same build-step issue.
- **Alpine.js + htmx:** Server-rendered approach that shifts complexity to the Python server.

**Consequences:**
- (+) Zero build step — edit HTML/CSS/JS and reload.
- (+) Maximum debuggability — inspect, modify, reload in DevTools without source maps.
- (+) No framework churn — core patterns survive for years.
- (-) Manual DOM management — developer must handle lifecycle, cleanup, and re-rendering.
- (-) No virtual DOM — full re-renders of page sections may be less efficient than React's diffing.
- (-) Developer must enforce architectural discipline (component teardown, memory management).

### ADR-002: Pub/Sub State over Redux Pattern

**Decision:** Use a simple pub/sub store with namespaced paths instead of a Redux-style reducer pattern.

**Context:** The store needs to support ~20 namespaced slices. The data flow is straightforward: API response → store mutation → re-render. There's no need for time-travel debugging, middleware chains, or complex action/reducer logic. The existing `cad/server/_frontend` store uses a simpler pattern successfully.

**Alternatives considered:**
- **Redux-style (actions, reducers, dispatch):** Over-engineered for this scope. Actions are boilerplate; reducers add indirection.
- **MobX-style (observables):** Requires a reactive library (violates "vanilla JS").
- **EventEmitter pattern (node.js style):** No path-based subscriptions, harder to reason about.

**Consequences:**
- (+) Minimal API surface — `get()`, `set()`, `subscribe()`, `update()` is all that's needed.
- (+) Path-based subscriptions allow granular re-rendering.
- (+) Easy to test — the store is a plain object with listeners.
- (-) No built-in immutability enforcement — developer discipline required.
- (-) Path strings can have typos — no TypeScript to catch them.

### ADR-003: Hash-based Routing over History API

**Decision:** Use `window.location.hash` for SPA routing instead of the History API.

**Context:** The frontend is served as static files from `file://` or from `127.0.0.1:9876/`. Hash-based routing works reliably in both modes. History API requires a server that serves `index.html` for all routes (SPA fallback), which adds complexity.

**Alternatives considered:**
- **History API:** Cleaner URLs (`/actions` vs `#/actions`), but requires server-side catch-all route.
- **Manual `location.pathname` parsing:** Same as History API, same server requirement.

**Consequences:**
- (+) Works everywhere without server configuration.
- (+) Simple to implement — listen for `hashchange` event.
- (-) URLs have `#/` prefix (aesthetic concern, not functional).
- (-) Server-side rendering impossible (not needed for v1).

### ADR-004: aiohttp over FastAPI

**Decision:** Use aiohttp for the Python API server instead of FastAPI.

**Context:** The existing `cad/server/` uses pure stdlib `asyncio` (no framework). For `fionaLocalPages/server/`, a minimal framework is desired for route definition, middleware, and WebSocket support. Both aiohttp and FastAPI satisfy this.

**Alternatives considered:**
- **FastAPI:** More popular, auto-generated OpenAPI docs, Pydantic validation. Heavier dependency tree (3.5MB vs 1.2MB).
- **Stdlib only:** The CAD server proved this works, but manual route dispatching and WebSocket frame parsing are tedious and error-prone.
- **Flask:** Synchronous, can't natively handle WebSocket alongside HTTP without extensions.

**Consequences:**
- (+) Lightweight dependency — aiohttp is pure Python with minimal deps.
- (+) Native WebSocket support — same framework for HTTP and WS.
- (+) Proven pattern — aiohttp is mature and well-documented.
- (-) No auto-generated API docs (unlike FastAPI).
- (-) Request/response validation must be manual or via a small helper.
- (-) Smaller ecosystem than FastAPI.

**Note:** FastAPI is also acceptable if the team prefers it. This ADR can be revisited. The critical requirement is that the server runs on stdlib + one framework.

### ADR-005: Single Connection for HTTP and WebSocket

**Decision:** Use a single aiohttp server for both REST API and WebSocket, on the same port.

**Context:** Two separate servers (one for API, one for WebSocket) adds complexity for port management, CORS, and deployment. A single server simplifies everything.

**Alternatives considered:**
- **Separate servers:** API on 9876, WS on 9877. Two processes or two ports. More complex to manage.
- **Uvicorn + Starlette:** Similar pattern to aiohttp but with ASGI.

**Consequences:**
- (+) Single port, single process, single lifecycle.
- (+) Shared state between REST handlers and WebSocket handlers is trivial.
- (+) Simpler for the CLI to launch.

### ADR-006: Server-Sent Events over WebSocket Polling for Streaming

**Decision:** Use Server-Sent Events (SSE) for agent chat token streaming and fall back to WebSocket JSON-RPC notifications for other real-time events.

**Context:** Agent chat streaming requires sending many small text chunks (tokens) from server to client. SSE is purpose-built for this. WebSocket is used for bidirectional messaging (client requests + server events).

**Alternatives considered:**
- **Pure WebSocket streaming:** Send tokens as JSON-RPC notifications. Works but requires more framing on each message.
- **Long polling:** Inefficient for real-time streaming.
- **Chunked transfer encoding (HTTP):** Works but no native browser API for event parsing.

**Consequences:**
- (+) SSE has automatic reconnection and built-in event parsing (`EventSource` API).
- (+) Lower overhead per message than WebSocket.
- (+) SSE can be consumed by any HTTP client.
- (-) SSE is unidirectional (server→client only). WebSocket is still needed for bidirectional events.

### ADR-007: BEM Naming over CSS-in-JS

**Decision:** Use BEM (Block Element Modifier) for CSS naming instead of CSS-in-JS or utility-first frameworks.

**Context:** No build step means no CSS-in-JS runtime. Tailwind-style utility classes would conflict with the design aesthetic and create verbose HTML.

**Alternatives considered:**
- **CSS-in-JS (styled-components, etc.):** Requires bundler and JS runtime overhead.
- **Tailwind CSS:** Utility-first conflicts with component-based architecture; verbose HTML; requires build step.
- **CSS Modules:** Requires bundler.

**Consequences:**
- (+) Predictable, scoped class names — low specificity conflicts.
- (+) Works with any CSS methodology (no tooling needed).
- (+) Familiar to most frontend developers.
- (-) Verbose HTML (many class attributes).
- (-) Manual namespacing.

---

## 16. Risk Analysis

| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|------------|
| R1 | **Module import side effects** — Some Fiona modules may execute side effects on import (file creation, server starts) | **High** | Medium | Audit all imports; wrap in lazy factories; use `FionaContainer.register_factory()` |
| R2 | **WebSocket connection loss during action** — User runs an action, WS disconnects before result | **Medium** | Low | Action execution is synchronous on server; result is returned in HTTP response body; WS is only for notifications |
| R3 | **Memory leaks in SPA** — Components not properly unmounting, subscriptions not cleaned up | **Medium** | High | Enforce lifecycle convention: every `subscribe()` returns unsubscribe, every `mount()` stores cleanup functions, `unmount()` calls all cleanup |
| R4 | **CSS specificity conflicts** — Multiple CSS files loaded globally, component styles may conflict | **Low** | Medium | BEM convention + consistent file ordering; use `.c-` prefix for components |
| R5 | **API server port conflict** — Port 9876 may conflict with existing services | **Low** | Medium | Make port configurable via CLI argument and env var; detect port in use and warn |
| R6 | **Browser compatibility** — CSS `backdrop-filter` (glassmorphism) not supported in older browsers | **Low** | Low | Provide fallback for `backdrop-filter` (solid background); progressive enhancement |
| R7 | **Large page modules** — Some pages (e.g., SettingsPage) may grow very large | **Medium** | Medium | Split large pages into sub-components; lazy-load settings sections |
| R8 | **Callback hell in async flows** — Nested API calls, streaming, state updates may create tangled callbacks | **Medium** | Medium | Use `async/await` consistently; use the store as the single coordination point; avoid callbacks for data flow |
| R9 | **Performance of large lists** — Actions list, notifications, or binding list with 1000+ items may cause DOM slowdown | **Low** | Medium | Virtual scrolling if needed (implement as a component); pagination on API side |
| R10 | **Cross-module state conflicts** — Two modules write to the same store path | **Low** | Low | Enforce namespaced store paths; document every mutation path in the API module |

---

## 17. Future Evolution

### 17.1 Horizontal Scaling

Not relevant for v1 (single-user desktop app). If Fiona grows to serve multiple users:

- Replace in-process `EventBus` → Redis pub/sub
- Replace in-memory WebSocket set → Redis-backed connection manager
- Add reverse proxy (nginx) for TLS and load balancing

### 17.2 Modularization

If the frontend grows beyond 30 pages:

- Extract pages into independently loadable "module bundles"
- Add a plugin system for third-party pages
- Consider migrating to a framework (Preact would be the natural choice)

### 17.3 Caching

Future performance improvements:

- Add an in-memory cache layer in `api.js` with TTL per endpoint
- Cache action specs (they rarely change)
- Cache notification history with `localStorage` fallback

### 17.4 Database Migration

- For offline support: IndexedDB wrapper to cache document data
- For settings persistence: `localStorage` is sufficient for v1
- For large data sets (CmdTrace logs): server-side pagination + IndexedDB cache

### 17.5 Theming

- For light mode: Add a `[data-theme="light"]` selector in `themes.css` overriding the custom properties
- For high-contrast mode: Separate set of custom properties
- For accent color customization: Expose `--color-accent` as a setting

### 17.6 Build Step (When Needed)

If the frontend outgrows vanilla JS patterns:

1. Switch from `<script type="module">` to Vite
2. Add TypeScript for type safety
3. Add CSS preprocessing (PostCSS, Sass) for nesting
4. Add a testing framework (Playwright component tests, Vitest for unit)

The architecture is designed so that migration to a build step is additive — the file structure, component patterns, and module boundaries all remain valid.

### 17.7 Merging with CAD Frontend

The `cad/server/_frontend` and `fionaLocalPages` should eventually merge:

- `cad` becomes a module (`/cad` route) within the unified frontend
- The REST API serves both CAD and Fiona endpoints
- The component library (`css/components.css`, `js/components/`) is shared
- The state store accommodates both CAD and Fiona state slices

---

## 18. Implementation Status

All phases described above have been **fully implemented** across multiple milestones:

### Phase 1: Foundation ✅
- Directory structure, CSS files (`globals.css`, `layout.css`, `themes.css`, `animations.css`, `components.css`), `state.js` (pub/sub store with localStorage persistence), `utils.js` (DOM helpers, debounce, format) — all created.

### Phase 2: Core Infrastructure ✅
- `api.js` (HTTP client + WebSocket with reconnection, handshake, SSE streaming), `router.js` (hash-based SPA with lazy loading, lifecycle hooks, guards, history stack), `app.js` (bootstrap with 26 route definitions, sidebar/status bar injection), `index.html` (SPA shell with static sidebar HTML)

### Phase 3: Component Library ✅
- 15+ reusable components: `BaseComponent`, `Sidebar`, `StatusBar`, `Modal`, `Toast`, `Tabs`, `TabPanel`, `SplitPanel`, `DataTable`, `FileTree`, `CommandPalette`, `ContextMenu`, `LoadingSkeleton`, `MetricsCard`, `ActivityTimeline`

### Phase 4: Python API Server ✅
- `server/app.py` — aiohttp with 115+ routes, middleware, static file serving, WebSocket at `/ws`, SSE at `/api/v1/stream`
- `server/websocket.py` — WebSocket connection manager with ping-pong, periodic push, peer tracking
- 24 handler modules covering all subsystems (actions, agent, agents_crud, bindings, browser, camcoms, config, desktop, files, macros, notifications, phiconnect, plugins, quiktieper, recall, sciretrieval, settings, system, tasks, terminal, tools_handler, voice)

### Phase 5: Pages ✅
- 27 page modules (26 active + 1 placeholder stub) — each with `render()`, `mount()`, `destroy()` lifecycle
- Template-loader pattern: 26 `.html` template files loaded dynamically via `js/template-loader.js`
- All pages handle loading, error, empty, and data states
- Every JS file passes `node -c` syntax check

### Phase 6: Polish ✅
- Error handling: toast notifications, error states in all pages, global error boundary in router
- Loading states: `LoadingSkeleton` component, per-page loading indicators
- Command palette: `CommandPalette` component (⌘K)
- Keyboard shortcuts: navigation shortcuts, sidebar toggle, escape-to-close
- Terminal autocomplete, server-side `cd` tracking, command history

---

## 19. Quality Checklist

- [x] Requirements understood and documented (Section 1)
- [x] Assumptions explicitly stated (Section 2)
- [x] Architectural drivers ranked and justified (Section 3)
- [x] Multiple architectures evaluated (Section 4)
- [x] Tradeoffs explained for each candidate (Section 4)
- [x] Recommended architecture selected and justified (Section 5)
- [x] Component tree fully enumerated (Section 6)
- [x] Interfaces defined (Section 7)
- [x] Data flow described with scenarios (Section 8)
- [x] State management designed with store shape, path convention, persistence (Section 9)
- [x] Router designed with route table, lifecycle hooks, guards (Section 10)
- [x] API contract specified (Section 11)
- [x] CSS architecture designed with tokens, BEM, file structure (Section 12)
- [x] Module dependency graph documented (Section 13)
- [x] Python API server architecture specified (Section 14)
- [x] Architecture Decision Records created (Section 15)
- [x] Risks documented with severity, likelihood, mitigation (Section 16)
- [x] Future evolution described (Section 17)
- [x] Implementation tasks sequenced (Section 18)
