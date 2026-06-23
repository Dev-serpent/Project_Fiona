# Prototypes

Fiona contains several prototype and experimental subsystems that are functional but not yet production-ready. These projects explore specific capabilities and may evolve independently from the main platform.

## CAD (ficad)

The CAD subsystem (`cad/`) is an experimental parametric 3D modeler with:

- **Python backend**: Document management, geometry primitives (Box, Cylinder, Sphere, Cone, Torus), boolean operations, constraints, sketches, assembly, undo/redo command stack, and STL/OBJ/SVG export.
- **Three.js frontend**: Vite-bundled SPA with WebSocket JSON-RPC 2.0 communication, 3D viewport with OrbitControls, raycasting-based object selection, editable property grid, project tree, interactive console, and agent supervisor panel.
- **Architecture**: Pure Python stdlib WebSocket server (no extra Python dependencies), standalone frontend using `three@^0.170.0`.

Status: Early prototype (v0.1.0). The geometry kernel and command system are functional; the frontend provides a basic 3D modeling UI. Not yet integrated with the main Fiona CLI or fionaLocalPages.

**Tests**: 98 Python server tests + 87 JavaScript frontend tests.

## fionaLocalPages (Web Dashboard)

The `fionaLocalPages/` web frontend is a modern single-page application (SPA) that serves as an operational dashboard for Fiona. It is a prototype for a browser-based control surface alongside the existing CLI and Tkinter GUI.

- **Backend**: Python `aiohttp` HTTP server with REST API at `/api/v1/` (11 endpoint groups: system, agent, actions, voice, terminal, files, config, browser, desktop, recall, macros, camcoms), WebSocket at `/ws` for real-time push, and SSE at `/api/v1/stream`.
- **Frontend**: Vanilla JavaScript SPA with hash-based routing (22 pages: dashboard, chat, agents, actions, bindings, phiconnect, macros, terminal, vsee, notifications, settings, performance, files, browser, tasks, plugins, logs, config, diagnostics, devtools, workspace), custom component system, and CSS theming.
- **Architecture**: The Python server serves static SPA files and proxies API calls to Fiona subsystems. Communication is over REST + WebSocket for real-time updates.

Status: Evolving prototype. Core pages (dashboard, chat, settings, terminal) are functional; some pages are stubs. Production concerns like authentication, theming, and full module coverage are still being addressed. Not the primary interface — the CLI and Tkinter GUI remain the main control surfaces.

## Vsee

Vsee (`Vsee/`) is a 3D point and edge wireframe hologram viewer. It renders connected wireframe shapes from coordinate data. See the [Vsee module page](modules/vsee.md) for details.

Status: Basic wireframe viewer. True optical holography and richer primitives are future work.

## EyeControl

EyeControl (`EyeControl/`) is an optional camera-based eye-controlled mouse tracker using MediaPipe face mesh landmarks. See the [EyeControl module page](modules/eyecontrol.md) for details.

Status: Functional prototype. Requires a camera feed and optional dependencies (OpenCV, MediaPipe, PyAutoGUI).
