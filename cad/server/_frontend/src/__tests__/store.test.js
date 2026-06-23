/**
 * Tests for CadStore — central application state.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { CadStore } from '../store.js';

describe('CadStore', () => {
  let store;

  beforeEach(() => {
    store = new CadStore();
  });

  // ── Initial State ─────────────────────────────────────────────────

  describe('initial state', () => {
    it('starts in disconnected state', () => {
      expect(store.status).toBe('disconnected');
    });

    it('has empty document', () => {
      expect(store.document).toBeNull();
      expect(store.objectCount).toBe(0);
      expect(store.objects).toEqual([]);
      expect(store.documentName).toBeNull();
    });

    it('has default camera position', () => {
      expect(store.camera).toEqual({ position: [50, 50, 100], target: [0, 0, 0] });
    });

    it('starts with empty selection', () => {
      expect(store.selection.size).toBe(0);
      expect(store.getSelectedObject()).toBeNull();
    });

    it('starts with empty undo/redo stacks', () => {
      expect(store.undoStack).toEqual([]);
      expect(store.redoStack).toEqual([]);
    });

    it('is not dirty', () => {
      expect(store.isDirty).toBe(false);
    });
  });

  // ── Document State ─────────────────────────────────────────────────

  describe('setFullState', () => {
    const doc = {
      name: 'TestDoc',
      objects: [
        { uid: 'obj1', name: 'Box001', type: 'Box', properties: {} },
        { uid: 'obj2', name: 'Sphere001', type: 'Sphere', properties: {} },
      ],
    };

    it('replaces the document and increments version', () => {
      const v0 = store.version;
      store.setFullState(doc);
      expect(store.document).toEqual(doc);
      expect(store.version).toBe(v0 + 1);
    });

    it('clears selection when setting state', () => {
      store.selection.add('obj1');
      store.setFullState(doc);
      expect(store.selection.size).toBe(0);
    });

    it('updates convenience getters', () => {
      store.setFullState(doc);
      expect(store.objectCount).toBe(2);
      expect(store.objects).toEqual(doc.objects);
      expect(store.documentName).toBe('TestDoc');
    });

    it('notifies listeners', () => {
      const calls = [];
      store.subscribe(() => calls.push('notified'));
      store.setFullState(doc);
      expect(calls).toEqual(['notified']);
    });
  });

  describe('applyChanges', () => {
    function makeDoc() {
      return {
        name: 'BaseDoc',
        objects: [
          { uid: 'keep', name: 'Keep', type: 'Box', properties: {} },
          { uid: 'delete', name: 'Delete', type: 'Sphere', properties: {} },
          { uid: 'modify', name: 'Modify', type: 'Cone', properties: { h: { value: 10 } } },
        ],
      };
    }

    beforeEach(() => {
      store.setFullState(makeDoc());
    });

    it('does nothing if document is null', () => {
      const emptyStore = new CadStore();
      emptyStore.applyChanges({ created: [{ uid: 'new' }] });
      expect(emptyStore.document).toBeNull();
    });

    it('adds created objects', () => {
      const newObj = { uid: 'new', name: 'NewObj', type: 'Box', properties: {} };
      store.applyChanges({ created: [newObj] });
      expect(store.objectCount).toBe(4);
      expect(store.objects.find(o => o.uid === 'new')).toEqual(newObj);
    });

    it('removes deleted objects and selection', () => {
      store.selection.add('delete');
      store.applyChanges({ deleted: ['delete'] });
      expect(store.objectCount).toBe(2);
      expect(store.objects.find(o => o.uid === 'delete')).toBeUndefined();
      expect(store.selection.has('delete')).toBe(false);
    });

    it('updates modified objects', () => {
      store.applyChanges({
        modified: [{ uid: 'modify', name: 'Modified', type: 'Cone', properties: { h: { value: 99 } } }],
      });
      const obj = store.objects.find(o => o.uid === 'modify');
      expect(obj.name).toBe('Modified');
      expect(obj.properties.h.value).toBe(99);
    });

    it('increments version on changes', () => {
      const v0 = store.version;
      store.applyChanges({ created: [{ uid: 'n', name: 'N', type: 'Box', properties: {} }] });
      expect(store.version).toBe(v0 + 1);
    });

    it('notifies listeners', () => {
      const calls = [];
      store.subscribe(() => calls.push('notified'));
      store.applyChanges({ created: [{ uid: 'n', name: 'N', type: 'Box', properties: {} }] });
      expect(calls.length).toBe(1);
    });
  });

  // ── Selection ─────────────────────────────────────────────────────

  describe('selection', () => {
    const objects = [
      { uid: 'a', name: 'A', type: 'Box', properties: {} },
      { uid: 'b', name: 'B', type: 'Box', properties: {} },
      { uid: 'c', name: 'C', type: 'Box', properties: {} },
    ];
    const doc = { name: 'SelDoc', objects };

    beforeEach(() => {
      store.setFullState(doc);
    });

    it('selectObject selects a single uid', () => {
      store.selectObject('a');
      expect(store.selection.has('a')).toBe(true);
      expect(store.selection.size).toBe(1);
    });

    it('selectObject clears previous selection', () => {
      store.selectObject('a');
      store.selectObject('b');
      expect(store.selection.has('a')).toBe(false);
      expect(store.selection.has('b')).toBe(true);
      expect(store.selection.size).toBe(1);
    });

    it('selectObject with null/undefined clears selection', () => {
      store.selectObject('a');
      store.selectObject(null);
      expect(store.selection.size).toBe(0);
    });

    it('toggleSelect adds uid if absent', () => {
      store.toggleSelect('a');
      expect(store.selection.has('a')).toBe(true);
    });

    it('toggleSelect removes uid if present', () => {
      store.selection.add('a');
      store.toggleSelect('a');
      expect(store.selection.has('a')).toBe(false);
    });

    it('deselectAll clears everything', () => {
      store.selection.add('a');
      store.selection.add('b');
      store.deselectAll();
      expect(store.selection.size).toBe(0);
    });

    it('getSelectedObject returns the first selected object', () => {
      store.selectObject('b');
      const obj = store.getSelectedObject();
      expect(obj.uid).toBe('b');
      expect(obj.name).toBe('B');
    });

    it('getSelectedObject returns null when nothing selected', () => {
      expect(store.getSelectedObject()).toBeNull();
    });

    it('getSelectedObject returns null if uid not in document', () => {
      store.selectObject('nonexistent');
      expect(store.getSelectedObject()).toBeNull();
    });

    it('notifies on selection changes', () => {
      const calls = [];
      store.subscribe(() => calls.push('x'));
      store.selectObject('a');
      expect(calls.length).toBe(1);
      store.toggleSelect('b');
      expect(calls.length).toBe(2);
      store.deselectAll();
      expect(calls.length).toBe(3);
    });
  });

  // ── Undo / Redo ──────────────────────────────────────────────────

  describe('undo/redo', () => {
    const doc = { name: 'URDoc', objects: [{ uid: 'x', name: 'X', type: 'Box', properties: {} }] };

    beforeEach(() => {
      store.setFullState(doc);
    });

    it('pushUndo adds snapshot and clears redo stack', () => {
      store.redoStack.push({ old: 'stuff' });
      store.pushUndo({ snap: 'data' });
      expect(store.undoStack.length).toBe(1);
      expect(store.redoStack).toEqual([]);
    });

    it('pushUndo caps at 50 entries', () => {
      for (let i = 0; i < 55; i++) {
        store.pushUndo({ i });
      }
      expect(store.undoStack.length).toBe(50);
      expect(store.undoStack[0].i).toBe(5); // oldest shifted off
    });

    it('popUndo returns null when empty', () => {
      expect(store.popUndo()).toBeNull();
    });

    it('popUndo returns snapshot and pushes current doc to redo', () => {
      store.pushUndo({ snapshot: 'old' });
      const result = store.popUndo();
      expect(result).toEqual({ snapshot: 'old' });
      expect(store.redoStack.length).toBe(1);
    });

    it('popRedo returns null when empty', () => {
      expect(store.popRedo()).toBeNull();
    });

    it('popRedo returns snapshot and pushes current doc to undo', () => {
      store.pushUndo({ snap: 's1' }); // push to undo
      store.popUndo(); // undo — pushes current to redo
      const result = store.popRedo();
      expect(result).not.toBeNull();
      expect(store.undoStack.length).toBe(1);
    });

    it('notifies on undo/redo operations', () => {
      const calls = [];
      store.subscribe(() => calls.push('x'));
      store.pushUndo({});
      store.popUndo();
      expect(calls.length).toBe(2);
    });
  });

  // ── Subscriptions ─────────────────────────────────────────────────

  describe('subscriptions', () => {
    it('subscribe returns an unsubscribe function', () => {
      const unsub = store.subscribe(() => {});
      expect(typeof unsub).toBe('function');
    });

    it('calls listener on mutation', () => {
      let called = false;
      store.subscribe(() => { called = true; });
      store.selectObject('a');
      expect(called).toBe(true);
    });

    it('does not call listener after unsubscribe', () => {
      let count = 0;
      const unsub = store.subscribe(() => { count++; });
      unsub();
      store.deselectAll();
      expect(count).toBe(0);
    });

    it('supports multiple listeners', () => {
      let a = 0, b = 0;
      store.subscribe(() => { a++; });
      store.subscribe(() => { b++; });
      store.setFullState({ name: 'D', objects: [] });
      expect(a).toBe(1);
      expect(b).toBe(1);
    });

    it('survives a listener that throws', () => {
      let secondCalled = false;
      store.subscribe(() => { throw new Error('boom'); });
      store.subscribe(() => { secondCalled = true; });
      store.setFullState({ name: 'D', objects: [] });
      expect(secondCalled).toBe(true);
    });
  });

  // ── Snapshot Serialization ────────────────────────────────────────

  describe('captureSnapshot / restoreSnapshot', () => {
    function makeDoc() {
      return {
        name: 'SnapDoc',
        objects: [{ uid: 'a', name: 'A', type: 'Box', properties: {} }],
      };
    }

    beforeEach(() => {
      store.setFullState(makeDoc());
    });

    it('captureSnapshot returns current state', () => {
      store.selectObject('a');
      const snap = store.captureSnapshot();
      expect(snap.selection).toEqual(['a']);
      expect(snap.document).toEqual(makeDoc());
    });

    it('restoreSnapshot restores previous state', () => {
      store.selectObject('a');
      const snap = store.captureSnapshot();
      store.setFullState({ name: 'Other', objects: [] });
      store.restoreSnapshot(snap);
      expect(store.document).toEqual(makeDoc());
      expect(store.selection.has('a')).toBe(true);
    });

    it('restoreSnapshot notifies listeners', () => {
      const calls = [];
      store.subscribe(() => calls.push('x'));
      store.restoreSnapshot({ selection: [], document: null });
      expect(calls.length).toBe(1);
    });

    it('restoreSnapshot handles null document', () => {
      store.restoreSnapshot({ selection: [], document: null });
      expect(store.document).toBeNull();
    });
  });

  // ── Connection Status ─────────────────────────────────────────────

  describe('connection status', () => {
    it('transitions through status values', () => {
      expect(store.status).toBe('disconnected');
      store.status = 'connecting';
      expect(store.status).toBe('connecting');
      store.status = 'connected';
      expect(store.status).toBe('connected');
      store.status = 'error';
      expect(store.status).toBe('error');
    });
  });
});
