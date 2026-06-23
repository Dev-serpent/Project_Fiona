/**
 * main.js — Fiona CAD Frontend Entry Point
 *
 * Initializes:
 *  - Three.js scene (Z-up)
 *  - WebSocket JSON-RPC 2.0 client
 *  - Application state store
 *  - All UI panels (toolbar, project tree, property editor, console, status bar)
 *  - Camera sync
 *  - Connection lifecycle management
 */

import * as THREE from 'three';
import { RpcClient } from './client.js';
import { CadStore } from './store.js';
import { SceneManager } from './scene/SceneManager.js';
import { CameraSync } from './scene/CameraSync.js';
import { Toolbar } from './panels/Toolbar.js';
import { ProjectTree } from './panels/ProjectTree.js';
import { PropertyEditor } from './panels/PropertyEditor.js';
import { ConsolePanel } from './panels/ConsolePanel.js';
import { StatusBar } from './panels/StatusBar.js';
import { AgentConsole } from './panels/AgentConsole.js';

// ── Constants ──────────────────────────────────────────────────────

const WS_URL = 'ws://127.0.0.1:8765/ws';
// In dev mode with Vite proxy, use:
// const WS_URL = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`;

// ── DOM References ─────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);
const viewport = $('viewport');
const toolbarEl = $('toolbar');
const treeEl = $('project-tree');
const propEl = $('property-editor');
const consoleEl = $('console-panel');
const statusBarEl = $('status-bar');
const panelAgentEl = $('panel-agent');

// ── Application State ──────────────────────────────────────────────

const store = new CadStore();

// ── Three.js Scene ─────────────────────────────────────────────────

const sceneManager = new SceneManager(viewport);
sceneManager.startAnimation();

// ── WebSocket RPC Client ───────────────────────────────────────────

const client = new RpcClient(WS_URL);

// ── Camera Sync ────────────────────────────────────────────────────

const cameraSync = new CameraSync(sceneManager.camera, sceneManager.controls, client, {
  syncInterval: 2000, // Send camera state every 2s
  sendToServer: true,
  receiveFromServer: true,
});

// ── Toast Notification ─────────────────────────────────────────────

function showToast(message, type = 'info', duration = 4000) {
  // Find or create toast container
  let toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);

  // Animate out after duration
  setTimeout(() => {
    toast.style.transition = 'opacity 0.3s, transform 0.3s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ── UI Panels ──────────────────────────────────────────────────────

const toolbar = new Toolbar(toolbarEl, client, store, sceneManager, {
  onToast: showToast,
});

const projectTree = new ProjectTree(treeEl, client, store);

const propertyEditor = new PropertyEditor(propEl, client, store);

const consolePanel = new ConsolePanel(consoleEl, client, store);

const statusBar = new StatusBar(statusBarEl, store);

// Agent Console (initially hidden, shown via tab)
const agentConsole = new AgentConsole(panelAgentEl, client, store);

// ── Tab / Panel Navigation ─────────────────────────────────────────

/**
 * Show a named panel/tab, hiding others.
 * Currently supports 'viewport' (default 3D view) and 'agent' (supervisor console).
 */
function showPanel(name) {
  // Update nav button active states
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.panel === name);
  });

  // Toggle main content vs. agent panel
  const mainContent = document.getElementById('main-content');
  const agentPanel = document.getElementById('panel-agent');
  const bottomPanel = document.getElementById('bottom-panel');

  if (name === 'agent') {
    mainContent.classList.add('hidden');
    agentPanel.classList.remove('hidden');
    bottomPanel.classList.add('hidden'); // Console is less relevant when viewing agent
  } else {
    mainContent.classList.remove('hidden');
    agentPanel.classList.add('hidden');
    bottomPanel.classList.remove('hidden');
  }
}

// Wire nav buttons
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    showPanel(btn.dataset.panel);
  });
});

// ── Coordinate Selection Across Panels ─────────────────────────────

projectTree.on('select', (uid) => {
  sceneManager.deselectAll();
  if (uid) sceneManager.selectObject(uid);
});

projectTree.on('delete', async (uid) => {
  if (!store.docId) return;
  try {
    await client.call('command.execute', {
      doc_id: store.docId,
      name: 'delete_object',
      kwargs: { uid },
    });
    showToast('Object deleted', 'success');
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, 'error');
  }
});

projectTree.on('focus', (uid) => {
  // Focus camera on object
  const mesh = sceneManager.getObject(uid);
  if (mesh) {
    // Create a bounding box target
    const box = new THREE.Box3().setFromObject(mesh);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const dist = Math.max(size.x, size.y, size.z) * 2.5;

    sceneManager.controls.target.copy(center);
    sceneManager.camera.position.set(
      center.x + dist * 0.577,
      center.y + dist * 0.577,
      center.z + dist * 0.577
    );
    sceneManager.controls.update();
    showToast(`Focused on ${mesh.userData.name}`, 'info');
  }
});

// ── Viewport Object Click → Selection ──────────────────────────────

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

sceneManager.renderer.domElement.addEventListener('click', (event) => {
  const rect = sceneManager.renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

  raycaster.setFromCamera(pointer, sceneManager.camera);

  // Collect all meshes
  const meshes = Object.values(sceneManager.objects);
  const intersects = raycaster.intersectObjects(meshes);

  if (intersects.length > 0) {
    const hit = intersects[0].object;
    const uid = hit.userData.uid;
    if (uid) {
      store.selectObject(uid);
      sceneManager.selectObject(uid);
      showToast(`Selected: ${hit.userData.name}`, 'info');
    }
  } else {
    // Click on empty space — deselect
    store.deselectAll();
    sceneManager.deselectAll();
  }
});

// Viewport mouse move → coordinate display
// (The StatusBar coordinate display placeholder)
const coordsEl = document.getElementById('viewport-coords');
if (coordsEl) {
  sceneManager.renderer.domElement.addEventListener('mousemove', (event) => {
    // Simple screen-space coords for now
    coordsEl.textContent = `X: ${event.offsetX}  Y: ${event.offsetY}`;
  });
}

// ── Resize Handling ────────────────────────────────────────────────

function handleResize() {
  const rect = viewport.getBoundingClientRect();
  sceneManager.resize(rect.width, rect.height);
}

window.addEventListener('resize', handleResize);

// Also observe the viewport element for size changes
if (window.ResizeObserver) {
  const resizeObserver = new ResizeObserver(() => handleResize());
  resizeObserver.observe(viewport);
}

// Initial resize
handleResize();

// ── Connection Lifecycle ───────────────────────────────────────────

async function connect() {
  store.status = 'connecting';
  statusBar.setMessage('Connecting...', 0);

  try {
    await client.connect();
    store.status = 'connected';
    statusBar.setMessage('Connected to server', 3000);

    // Perform handshake
    const caps = await client.handshake();
    consolePanel.appendOutput(`Handshake complete: ${JSON.stringify(caps)}`, 'system');

    // Start camera sync after connection
    cameraSync.start();

    // Create or get the default document
    try {
      const docList = await client.call('document.list', {});
      if (docList && docList.length > 0) {
        store.docId = docList[0].doc_id || docList[0].docId;
        // Request full state
        const docState = await client.call('document.get_state', { doc_id: store.docId });
        if (docState) {
          store.setFullState(docState);
          sceneManager.rebuildScene(docState);
          statusBar.setMessage(`Opened: ${docState.name}`, 3000);
        }
      } else {
        // Create a new document
        const created = await client.call('document.create', { name: 'Untitled' });
        store.docId = created.doc_id || created.docId;
        statusBar.setMessage('Created new document', 3000);
      }
    } catch (err) {
      consolePanel.appendOutput(`Document init: ${err.message}`, 'warning');
    }
  } catch (err) {
    store.status = 'error';
    statusBar.setMessage(`Connection failed: ${err.message}`, 0);
    consolePanel.appendOutput(`Connection error: ${err.message}`, 'error');
    showToast('Failed to connect to server', 'error', 8000);
  }

  statusBar._refresh(); // Update display
}

// ── Server Event Handlers ──────────────────────────────────────────

client.on('document_updated', (payload) => {
  // Full document snapshot arrived
  if (payload.document) {
    store.setFullState(payload.document);
    sceneManager.rebuildScene(payload.document);
  }
  // Incremental changes
  if (payload.changes) {
    store.applyChanges(payload.changes);
    // Apply changes to scene
    const changes = payload.changes;
    if (changes.created) {
      for (const obj of changes.created) {
        sceneManager.addObject(obj);
      }
    }
    if (changes.modified) {
      for (const obj of changes.modified) {
        sceneManager.updateObject(obj.uid, obj.properties);
      }
    }
    if (changes.deleted) {
      for (const uid of changes.deleted) {
        sceneManager.removeObject(uid);
      }
    }
  }
});

client.on('connection_open', () => {
  store.status = 'connected';
  statusBar.setMessage('Connected', 2000);
});

client.on('connection_close', (payload) => {
  store.status = 'disconnected';
  statusBar.setMessage(`Disconnected (code=${payload.code})`, 0);
});

client.on('connection_error', () => {
  store.status = 'error';
  statusBar.setMessage('Connection error', 0);
});

client.on('reconnecting', (payload) => {
  store.status = 'connecting';
  statusBar.setMessage(`Reconnecting (${payload.attempt}/${payload.maxRetries})...`, 0);
});

client.on('reconnected', () => {
  store.status = 'connected';
  statusBar.setMessage('Reconnected', 3000);
  // Re-sync document state
  if (store.docId) {
    client.call('document.get_state', { doc_id: store.docId })
      .then((docState) => {
        if (docState) {
          store.setFullState(docState);
          sceneManager.rebuildScene(docState);
        }
      })
      .catch((err) => console.warn('Re-sync error:', err));
  }
});

client.on('reconnect_exhausted', () => {
  store.status = 'error';
  statusBar.setMessage('Could not reconnect to server', 0);
  showToast('Connection lost. Reload to retry.', 'error', 0);
});

client.on('camera_updated', (payload) => {
  cameraSync.applyCameraState(payload);
});

client.on('server_message', (payload) => {
  if (payload && payload.message) {
    consolePanel.appendOutput(`[Server] ${payload.message}`, 'system');
  }
});

// ── Startup ────────────────────────────────────────────────────────

consolePanel.appendOutput('Starting Fiona CAD frontend...', 'system');
connect().catch((err) => {
  console.error('Startup error:', err);
  showToast('Startup error: ' + err.message, 'error', 0);
});

// ── Expose for Debugging ───────────────────────────────────────────

window.__fiona = {
  client,
  store,
  sceneManager,
  cameraSync,
  Toolbar,
};
