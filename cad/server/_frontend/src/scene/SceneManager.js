/**
 * SceneManager — Three.js scene lifecycle and rendering.
 *
 * Manages the Three.js scene, camera, renderer, OrbitControls,
 * object meshes, selection highlighting, grid, axes, and lighting.
 *
 * Coordinate system: Z-up (matching Fiona's convention).
 *   camera.up.set(0, 0, 1)
 *   Grid on XY plane, Y forward, X right, Z up.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PrimitiveFactory } from './PrimitiveFactory.js';

export class SceneManager {
  /**
   * @param {HTMLElement} container - The DOM element to mount the canvas into.
   */
  constructor(container) {
    if (!container) throw new Error('SceneManager requires a container element');

    // ── Scene ──────────────────────────────────────────────────────
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x1a1a2e);

    // ── Camera (Z-up) ──────────────────────────────────────────────
    this.camera = new THREE.PerspectiveCamera(45, 1, 1, 10000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(50, 50, 100);

    // ── Renderer ───────────────────────────────────────────────────
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x1a1a2e);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    container.appendChild(this.renderer.domElement);

    // ── Controls ───────────────────────────────────────────────────
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 0, 0);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.1;
    this.controls.rotateSpeed = 0.8;
    this.controls.zoomSpeed = 1.2;
    this.controls.panSpeed = 0.6;
    this.controls.minDistance = 5;
    this.controls.maxDistance = 5000;
    this.controls.update();

    // ── Object Storage ─────────────────────────────────────────────
    /** @type {Object<string, THREE.Mesh>} uid -> mesh */
    this.objects = {};
    /** @type {Object<string, THREE.Mesh>} uid -> orange wireframe overlay for selection */
    this._selectionOverlays = {};

    // ── Grid (XY plane for Z-up) ───────────────────────────────────
    this.gridHelper = new THREE.GridHelper(200, 20, 0x444466, 0x333355);
    // GridHelper is Y-up by default. Rotate -90° around X to lie on XY plane.
    this.gridHelper.rotation.x = Math.PI / 2;
    this.gridHelper.position.z = -0.01; // Slightly below origin to avoid z-fighting
    this.scene.add(this.gridHelper);
    this._showGrid = true;

    // ── Axes ───────────────────────────────────────────────────────
    const axesHelper = new THREE.AxesHelper(20);
    this.scene.add(axesHelper);

    // ── Lighting ───────────────────────────────────────────────────
    const ambientLight = new THREE.AmbientLight(0x404060, 0.6);
    this.scene.add(ambientLight);

    const hemisphereLight = new THREE.HemisphereLight(0x606080, 0x303050, 0.6);
    this.scene.add(hemisphereLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
    directionalLight.position.set(80, 80, 120);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    directionalLight.shadow.camera.near = 1;
    directionalLight.shadow.camera.far = 500;
    directionalLight.shadow.camera.left = -150;
    directionalLight.shadow.camera.right = 150;
    directionalLight.shadow.camera.top = 150;
    directionalLight.shadow.camera.bottom = -150;
    this.scene.add(directionalLight);

    const fillLight = new THREE.DirectionalLight(0x8888ff, 0.3);
    fillLight.position.set(-50, 0, 50);
    this.scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xffffff, 0.2);
    rimLight.position.set(0, -80, 50);
    this.scene.add(rimLight);

    // ── Render Loop ────────────────────────────────────────────────
    this._animating = false;
    this._renderId = null;
  }

  // ── Scene Rebuild ─────────────────────────────────────────────────

  /**
   * Completely rebuild the scene from a document state.
   * Removes all existing meshes and recreates them.
   * @param {object} documentState - Document dict from Document.to_dict().
   */
  rebuildScene(documentState) {
    // Remove all current objects
    this._clearAllObjects();

    if (!documentState || !documentState.objects) return;

    for (const objData of documentState.objects) {
      this.addObject(objData);
    }
  }

  // ── Object Management ─────────────────────────────────────────────

  /**
   * Add a single object to the scene.
   * @param {object} objData - Object data from CADObject.to_dict().
   * @returns {THREE.Mesh|null}
   */
  addObject(objData) {
    const mesh = PrimitiveFactory.createMesh(objData);
    if (!mesh) return null;

    const uid = objData.uid;
    this.objects[uid] = mesh;
    this.scene.add(mesh);
    return mesh;
  }

  /**
   * Update an existing object's geometry and position.
   * @param {string} uid - Object UID.
   * @param {object} properties - Updated properties dict.
   */
  updateObject(uid, properties) {
    const existing = this.objects[uid];
    if (!existing) return;

    const objData = {
      uid,
      name: existing.userData.name,
      label: existing.userData.label,
      type: existing.userData.type,
      properties,
    };

    const newMesh = PrimitiveFactory.createMesh(objData);
    if (!newMesh) return;

    // Copy user data from old mesh
    newMesh.userData = { ...existing.userData };

    // Swap in scene
    this.scene.remove(existing);
    this.scene.add(newMesh);
    this.objects[uid] = newMesh;

    // If there's a selection overlay for this object, rebuild it too
    if (this._selectionOverlays[uid]) {
      this.deselectAll();
      this.selectObject(uid);
    }

    // Dispose old geometry
    existing.geometry.dispose();
  }

  /**
   * Remove an object from the scene.
   * @param {string} uid - Object UID.
   */
  removeObject(uid) {
    const mesh = this.objects[uid];
    if (mesh) {
      this.scene.remove(mesh);
      mesh.geometry.dispose();
      delete this.objects[uid];
    }

    // Remove selection overlay if any
    if (this._selectionOverlays[uid]) {
      this.scene.remove(this._selectionOverlays[uid]);
      this._selectionOverlays[uid].geometry.dispose();
      delete this._selectionOverlays[uid];
    }
  }

  /**
   * Get a mesh by object UID.
   * @param {string} uid
   * @returns {THREE.Mesh|undefined}
   */
  getObject(uid) {
    return this.objects[uid];
  }

  // ── Selection ─────────────────────────────────────────────────────

  /**
   * Highlight a single object with an orange wireframe overlay.
   * @param {string} uid
   */
  selectObject(uid) {
    this.deselectAll();

    const mesh = this.objects[uid];
    if (!mesh) return;

    const selMat = PrimitiveFactory.getSelectionMaterial();
    const selGeo = mesh.geometry.clone();
    const overlay = new THREE.Mesh(selGeo, selMat);
    overlay.position.copy(mesh.position);
    overlay.rotation.copy(mesh.rotation);
    overlay.scale.copy(mesh.scale);
    overlay.renderOrder = 1; // Render on top

    this._selectionOverlays[uid] = overlay;
    this.scene.add(overlay);
  }

  /** Clear all selection overlays. */
  deselectAll() {
    for (const uid of Object.keys(this._selectionOverlays)) {
      this.scene.remove(this._selectionOverlays[uid]);
      this._selectionOverlays[uid].geometry.dispose();
    }
    this._selectionOverlays = {};
  }

  // ── Grid Toggle ───────────────────────────────────────────────────

  /** @param {boolean} visible */
  set showGrid(visible) {
    this._showGrid = visible;
    this.gridHelper.visible = visible;
  }

  /** @returns {boolean} */
  get showGrid() {
    return this._showGrid;
  }

  // ── Camera ────────────────────────────────────────────────────────

  /** Reset camera to default position and target. */
  resetCamera() {
    this.camera.position.set(50, 50, 100);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  // ── Resize ────────────────────────────────────────────────────────

  /**
   * Handle container resize.
   * @param {number} width
   * @param {number} height
   */
  resize(width, height) {
    if (width === 0 || height === 0) return;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  // ── Rendering ─────────────────────────────────────────────────────

  /** Render a single frame. */
  render() {
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  /**
   * Start the requestAnimationFrame loop.
   */
  startAnimation() {
    if (this._animating) return;
    this._animating = true;

    const loop = () => {
      if (!this._animating) return;
      this.render();
      this._renderId = requestAnimationFrame(loop);
    };

    loop();
  }

  /**
   * Stop the animation loop.
   */
  stopAnimation() {
    this._animating = false;
    if (this._renderId !== null) {
      cancelAnimationFrame(this._renderId);
      this._renderId = null;
    }
  }

  // ── Internal ──────────────────────────────────────────────────────

  /** Remove all objects from the scene and dispose resources. */
  _clearAllObjects() {
    for (const uid of Object.keys(this.objects)) {
      this.removeObject(uid);
    }
    this._selectionOverlays = {};
  }

  /**
   * Clean up all Three.js resources.
   * Call when the scene will no longer be used.
   */
  dispose() {
    this.stopAnimation();
    this._clearAllObjects();
    this.scene.remove(this.gridHelper);
    this.renderer.dispose();
  }
}
