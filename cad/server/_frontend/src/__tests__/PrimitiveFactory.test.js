/**
 * Tests for PrimitiveFactory — Three.js mesh creation from CAD object data.
 */
import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import { PrimitiveFactory } from '../scene/PrimitiveFactory.js';

/**
 * Helper to build a property dict in the CAD server format.
 */
function props(overrides = {}) {
  const defaults = {
    x: { name: 'x', type: 'float', value: 0, unit: 'mm' },
    y: { name: 'y', type: 'float', value: 0, unit: 'mm' },
    z: { name: 'z', type: 'float', value: 0, unit: 'mm' },
  };
  return { ...defaults, ...overrides };
}

/**
 * Build a minimal object data dict.
 */
function objData(type, customProps = {}, overrides = {}) {
  return {
    uid: 'test-001',
    name: 'TestObj',
    label: 'TestObj',
    type,
    properties: props(customProps),
    ...overrides,
  };
}

describe('PrimitiveFactory', () => {
  // ── _propValue ───────────────────────────────────────────────────

  describe('_propValue', () => {
    it('extracts value from property dict', () => {
      const p = { width: { value: 25 } };
      expect(PrimitiveFactory._propValue(p, 'width', 10)).toBe(25);
    });

    it('returns fallback when property is missing', () => {
      expect(PrimitiveFactory._propValue({}, 'width', 10)).toBe(10);
    });

    it('returns fallback when property value is not a number', () => {
      const p = { width: { value: 'abc' } };
      expect(PrimitiveFactory._propValue(p, 'width', 10)).toBe(10);
    });
  });

  // ── _createGeometry ──────────────────────────────────────────────

  describe('_createGeometry', () => {
    it('creates a Box geometry with correct dimensions', () => {
      const geo = PrimitiveFactory._createGeometry('Box', {
        width: { value: 20 }, height: { value: 30 }, depth: { value: 40 },
      });
      expect(geo).toBeInstanceOf(THREE.BoxGeometry);
      // BoxGeometry stores parameters
      expect(geo.parameters.width).toBe(20);
      expect(geo.parameters.height).toBe(30);
      expect(geo.parameters.depth).toBe(40);
    });

    it('creates a Sphere geometry with correct radius', () => {
      const geo = PrimitiveFactory._createGeometry('Sphere', {
        radius: { value: 15 },
      });
      expect(geo).toBeInstanceOf(THREE.SphereGeometry);
      expect(geo.parameters.radius).toBe(15);
    });

    it('creates a Cylinder geometry with correct dimensions', () => {
      const geo = PrimitiveFactory._createGeometry('Cylinder', {
        radius: { value: 12 }, height: { value: 50 },
      });
      expect(geo).toBeInstanceOf(THREE.CylinderGeometry);
      expect(geo.parameters.radiusTop).toBe(12);
      expect(geo.parameters.radiusBottom).toBe(12);
      expect(geo.parameters.height).toBe(50);
    });

    it('creates a Cone geometry with correct dimensions', () => {
      const geo = PrimitiveFactory._createGeometry('Cone', {
        radius: { value: 8 }, height: { value: 30 },
      });
      expect(geo).toBeInstanceOf(THREE.ConeGeometry);
      expect(geo.parameters.radius).toBe(8);
      expect(geo.parameters.height).toBe(30);
    });

    it('creates a Torus geometry with correct dimensions', () => {
      const geo = PrimitiveFactory._createGeometry('Torus', {
        major_radius: { value: 25 }, minor_radius: { value: 6 },
      });
      expect(geo).toBeInstanceOf(THREE.TorusGeometry);
      expect(geo.parameters.radius).toBe(25);
      expect(geo.parameters.tube).toBe(6);
    });

    it('falls back to unit Box for unknown types', () => {
      const geo = PrimitiveFactory._createGeometry('Octopus', {});
      expect(geo).toBeInstanceOf(THREE.BoxGeometry);
      expect(geo.parameters.width).toBe(1);
      expect(geo.parameters.height).toBe(1);
      expect(geo.parameters.depth).toBe(1);
    });

    it('uses fallback values when properties are missing', () => {
      const geo = PrimitiveFactory._createGeometry('Box', {});
      expect(geo).toBeInstanceOf(THREE.BoxGeometry);
      expect(geo.parameters.width).toBe(10);
      expect(geo.parameters.height).toBe(10);
      expect(geo.parameters.depth).toBe(10);
    });
  });

  // ── createMesh ───────────────────────────────────────────────────

  describe('createMesh', () => {
    it('returns null for null properties', () => {
      const result = PrimitiveFactory.createMesh({ type: 'Box', name: 'N', properties: null });
      expect(result).toBeNull();
    });

    it('returns null for missing properties key', () => {
      const result = PrimitiveFactory.createMesh({ type: 'Box', name: 'N' });
      expect(result).toBeNull();
    });

    it('creates a THREE.Mesh with correct userData', () => {
      const data = objData('Box', { width: { value: 15 }, height: { value: 25 }, depth: { value: 35 } });
      const mesh = PrimitiveFactory.createMesh(data);
      expect(mesh).toBeInstanceOf(THREE.Mesh);
      expect(mesh.userData.uid).toBe('test-001');
      expect(mesh.userData.name).toBe('TestObj');
      expect(mesh.userData.type).toBe('Box');
    });

    it('positions mesh from x,y,z properties', () => {
      const data = objData('Box', { x: { value: 10 }, y: { value: 20 }, z: { value: 30 } });
      const mesh = PrimitiveFactory.createMesh(data);
      expect(mesh.position.x).toBe(10);
      expect(mesh.position.y).toBe(20);
      expect(mesh.position.z).toBe(30);
    });

    it('uses default position when x,y,z are missing', () => {
      const data = objData('Box', {});
      const mesh = PrimitiveFactory.createMesh(data);
      expect(mesh.position.x).toBe(0);
      expect(mesh.position.y).toBe(0);
      expect(mesh.position.z).toBe(0);
    });

    it('creates mesh for each primitive type', () => {
      const types = ['Box', 'Sphere', 'Cylinder', 'Cone', 'Torus'];
      for (const type of types) {
        const data = objData(type, {});
        const mesh = PrimitiveFactory.createMesh(data);
        expect(mesh).toBeInstanceOf(THREE.Mesh);
        expect(mesh.userData.type).toBe(type);
      }
    });

    it('mesh has correct material properties', () => {
      const data = objData('Box');
      const mesh = PrimitiveFactory.createMesh(data);
      expect(mesh.material).toBeInstanceOf(THREE.MeshStandardMaterial);
      expect(mesh.material.transparent).toBe(true);
      expect(mesh.material.opacity).toBe(0.9);
    });
  });

  // ── Material Factories ───────────────────────────────────────────

  describe('getDefaultMaterial', () => {
    it('returns a MeshStandardMaterial', () => {
      const mat = PrimitiveFactory.getDefaultMaterial();
      expect(mat).toBeInstanceOf(THREE.MeshStandardMaterial);
      expect(mat.color.getHex()).toBe(0x35a7ff);
    });
  });

  describe('getSelectionMaterial', () => {
    it('returns a MeshBasicMaterial with orange wireframe', () => {
      const mat = PrimitiveFactory.getSelectionMaterial();
      expect(mat).toBeInstanceOf(THREE.MeshBasicMaterial);
      expect(mat.color.getHex()).toBe(0xff8800);
      expect(mat.wireframe).toBe(true);
    });
  });

  describe('getHoverMaterial', () => {
    it('returns a MeshBasicMaterial with wireframe', () => {
      const mat = PrimitiveFactory.getHoverMaterial();
      expect(mat).toBeInstanceOf(THREE.MeshBasicMaterial);
      expect(mat.color.getHex()).toBe(0x35a7ff);
      expect(mat.wireframe).toBe(true);
      expect(mat.opacity).toBe(0.3);
    });
  });
});
