/**
 * CadStore — Central application state.
 *
 * Holds the last-known document state, selection, camera, undo/redo
 * stacks, and connection status.  Panels read from this store and
 * re-render when the relevant section changes.
 */
export class CadStore {
  constructor() {
    /** @type {object|null} Last known document state from server */
    this.document = null;

    /** @type {number} Monotonic version counter from server */
    this.version = 0;

    /** @type {{position: number[], target: number[]}} Camera state */
    this.camera = { position: [50, 50, 100], target: [0, 0, 0] };

    /** @type {Set<string>} Selected object UIDs */
    this.selection = new Set();

    /** @type {Array<object>} Local undo snapshots */
    this.undoStack = [];

    /** @type {Array<object>} Local redo snapshots */
    this.redoStack = [];

    /** @type {boolean} Whether there are unsaved changes */
    this.isDirty = false;

    /** @type {string|null} Current active document ID */
    this.docId = null;

    /** @type {Array<{docId: string, name: string}>} Open documents */
    this.documents = [];

    /** @type {string} Connection status: 'disconnected'|'connecting'|'connected'|'error' */
    this.status = 'disconnected';

    /** @type {Array<function>} Change listeners (callback -> cleanup function) */
    this._listeners = [];
  }

  // ── Subscriptions ────────────────────────────────────────────────

  /**
   * Subscribe to store changes.
   * @param {function} callback - Called with no arguments after every mutation.
   * @returns {function} Call to unsubscribe.
   */
  subscribe(callback) {
    this._listeners.push(callback);
    return () => {
      const idx = this._listeners.indexOf(callback);
      if (idx !== -1) this._listeners.splice(idx, 1);
    };
  }

  _notify() {
    for (const cb of this._listeners) {
      try { cb(); } catch (e) { console.warn('Store listener error:', e); }
    }
  }

  // ── Document State ────────────────────────────────────────────────

  /**
   * Replace the entire document state.
   * Called after a full server document snapshot arrives.
   * @param {object} document - Document dict (from Document.to_dict())
   */
  setFullState(document) {
    this.document = document;
    this.version = (this.version || 0) + 1;
    this.selection.clear();
    this._notify();
  }

  /**
   * Apply incremental changes to the current document.
   * Called when a document_updated event arrives with a changeSet.
   * @param {{created?: object[], modified?: object[], deleted?: string[]}} changeSet
   */
  applyChanges(changeSet) {
    if (!this.document) return;

    const objMap = new Map();
    for (const obj of (this.document.objects || [])) {
      objMap.set(obj.uid, obj);
    }

    // Remove deleted
    for (const uid of (changeSet.deleted || [])) {
      objMap.delete(uid);
      this.selection.delete(uid);
    }

    // Add created
    for (const obj of (changeSet.created || [])) {
      objMap.set(obj.uid, obj);
    }

    // Update modified
    for (const obj of (changeSet.modified || [])) {
      objMap.set(obj.uid, obj);
    }

    this.document.objects = Array.from(objMap.values());
    this.version++;
    this._notify();
  }

  // ── Selection ────────────────────────────────────────────────────

  /**
   * Select a single object, clearing previous selection.
   * @param {string} uid
   */
  selectObject(uid) {
    this.selection.clear();
    if (uid) this.selection.add(uid);
    this._notify();
  }

  /**
   * Toggle selection of an object (multi-select).
   * @param {string} uid
   */
  toggleSelect(uid) {
    if (this.selection.has(uid)) {
      this.selection.delete(uid);
    } else {
      this.selection.add(uid);
    }
    this._notify();
  }

  /** Clear all selection. */
  deselectAll() {
    this.selection.clear();
    this._notify();
  }

  /**
   * @returns {object|null} The currently selected object's data, or null.
   */
  getSelectedObject() {
    if (!this.document || this.selection.size === 0) return null;
    const uid = this.selection.values().next().value;
    return (this.document.objects || []).find(o => o.uid === uid) || null;
  }

  // ── Undo / Redo ──────────────────────────────────────────────────

  /**
   * Push a snapshot onto the undo stack.
   * Clears the redo stack.
   * @param {object} snapshot - Document state captured before a mutation.
   */
  pushUndo(snapshot) {
    this.undoStack.push(snapshot);
    this.redoStack = [];
    // Cap at 50 entries
    if (this.undoStack.length > 50) {
      this.undoStack.shift();
    }
    this._notify();
  }

  /**
   * Pop the most recent undo snapshot.
   * @returns {object|null}
   */
  popUndo() {
    if (this.undoStack.length === 0) return null;
    const snapshot = this.undoStack.pop();
    this.redoStack.push(this.document ? { ...this.document } : {});
    this._notify();
    return snapshot;
  }

  /**
   * Pop the most recent redo snapshot.
   * @returns {object|null}
   */
  popRedo() {
    if (this.redoStack.length === 0) return null;
    const snapshot = this.redoStack.pop();
    this.undoStack.push(this.document ? { ...this.document } : {});
    this._notify();
    return snapshot;
  }

  // ── Convenience Getters ──────────────────────────────────────────

  /** @returns {number} Count of objects in the current document. */
  get objectCount() {
    return this.document ? (this.document.objects || []).length : 0;
  }

  /** @returns {Array<object>} Objects in the current document. */
  get objects() {
    return this.document ? (this.document.objects || []) : [];
  }

  /** @returns {string|null} Name of the current document, or null. */
  get documentName() {
    return this.document ? this.document.name : null;
  }

  // ── Serialize / Deserialize (for local undo snapshots) ───────────

  /**
   * Capture a snapshot of the current selectable state (for local undo).
   * @returns {object}
   */
  captureSnapshot() {
    return {
      selection: Array.from(this.selection),
      document: this.document ? JSON.parse(JSON.stringify(this.document)) : null,
    };
  }

  /**
   * Restore from a snapshot returned by captureSnapshot().
   * @param {object} snap
   */
  restoreSnapshot(snap) {
    this.document = snap.document ? JSON.parse(JSON.stringify(snap.document)) : null;
    this.selection = new Set(snap.selection || []);
    this._notify();
  }
}
