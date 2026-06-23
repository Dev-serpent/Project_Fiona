/**
 * PrimitiveFactory — Creates Three.js meshes from CAD primitive data.
 *
 * The incoming objData comes from CADObject.to_dict(), which looks like:
 * {
 *   uid: "abc-123",
 *   name: "Box001",
 *   label: "Box001",
 *   type: "Box",
 *   properties: {
 *     width:  { name: "width",  type: "float", value: 10, unit: "mm", ... },
 *     height: { name: "height", type: "float", value: 20, unit: "mm", ... },
 *     ...
 *   },
 *   dependencies: []
 * }
 *
 * Each property has a { value } field.  For primitives the value is
 * always a plain number (float).  Position is stored as properties
 * named "x", "y", "z".
 */

import * as THREE from 'three';

export class PrimitiveFactory {
  /**
   * Build a Three.js Mesh from a CAD object dict.
   * @param {object} objData - Object data from the server (CADObject.to_dict()).
   * @returns {THREE.Mesh|null}
   */
  static createMesh(objData) {
    const { type, name, properties } = objData;
    if (!properties) return null;

    const geo = PrimitiveFactory._createGeometry(type, properties);
    if (!geo) return null;

    const mat = new THREE.MeshStandardMaterial({
      color: 0x35a7ff,
      roughness: 0.6,
      metalness: 0.2,
      transparent: true,
      opacity: 0.9,
      side: THREE.DoubleSide,
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(
      PrimitiveFactory._propValue(properties, 'x', 0),
      PrimitiveFactory._propValue(properties, 'y', 0),
      PrimitiveFactory._propValue(properties, 'z', 0)
    );

    // Store metadata for raycasting / selection
    mesh.userData = {
      uid: objData.uid,
      name: name,
      label: objData.label || name,
      type: type,
    };

    return mesh;
  }

  /**
   * Get the material used for newly created meshes.
   * Useful for creating highlight/selection materials of the same style.
   * @returns {THREE.MeshStandardMaterial}
   */
  static getDefaultMaterial() {
    return new THREE.MeshStandardMaterial({
      color: 0x35a7ff,
      roughness: 0.6,
      metalness: 0.2,
      transparent: true,
      opacity: 0.9,
      side: THREE.DoubleSide,
    });
  }

  /**
   * Create a selection-highlight material (orange outline).
   * @returns {THREE.MeshBasicMaterial}
   */
  static getSelectionMaterial() {
    return new THREE.MeshBasicMaterial({
      color: 0xff8800,
      wireframe: true,
      transparent: true,
      opacity: 0.6,
    });
  }

  /**
   * Create a wireframe overlay material for hover feedback.
   * @returns {THREE.MeshBasicMaterial}
   */
  static getHoverMaterial() {
    return new THREE.MeshBasicMaterial({
      color: 0x35a7ff,
      wireframe: true,
      transparent: true,
      opacity: 0.3,
    });
  }

  // ── Geometry builders ─────────────────────────────────────────────

  /**
   * Create a Three.js BufferGeometry from CAD primitive type + properties.
   * @param {string} type - Primitive type name (Box, Cylinder, Sphere, Cone, Torus).
   * @param {object} props - Properties dict from CADObject.to_dict().
   * @returns {THREE.BufferGeometry|null}
   */
  static _createGeometry(type, props) {
    switch (type) {
      case 'Box':
        return new THREE.BoxGeometry(
          PrimitiveFactory._propValue(props, 'width', 10),
          PrimitiveFactory._propValue(props, 'height', 10),
          PrimitiveFactory._propValue(props, 'depth', 10)
        );

      case 'Cylinder': {
        // CylinderGeometry is Z-up by default in Three.js.
        // In Fiona, Cylinder extends along Z, so we rotate it.
        const geo = new THREE.CylinderGeometry(
          PrimitiveFactory._propValue(props, 'radius', 10),
          PrimitiveFactory._propValue(props, 'radius', 10),
          PrimitiveFactory._propValue(props, 'height', 25),
          32,
          1,
          true
        );
        // Three.js CylinderGeometry is Y-up; Fiona is Z-up.
        // The cylinder axis is already Z since Fiona primitives are defined
        // with height along Z.  CylinderGeometry default axis is Y, so
        // rotate -90° around X to align with Z.
        geo.rotateX(-Math.PI / 2);
        return geo;
      }

      case 'Sphere':
        return new THREE.SphereGeometry(
          PrimitiveFactory._propValue(props, 'radius', 10),
          32,
          24
        );

      case 'Cone': {
        const geo = new THREE.ConeGeometry(
          PrimitiveFactory._propValue(props, 'radius', 10),
          PrimitiveFactory._propValue(props, 'height', 25),
          32,
          1,
          true
        );
        geo.rotateX(-Math.PI / 2);
        return geo;
      }

      case 'Torus':
        return new THREE.TorusGeometry(
          PrimitiveFactory._propValue(props, 'major_radius', 20),
          PrimitiveFactory._propValue(props, 'minor_radius', 5),
          24,
          32
        );

      default:
        console.warn(`PrimitiveFactory: unknown type "${type}" — fallback to Box`);
        return new THREE.BoxGeometry(1, 1, 1);
    }
  }

  /**
   * Safely extract a property value from the properties dict.
   * Property dicts from the server look like { value: <number>, ... }.
   * @param {object} props
   * @param {string} name
   * @param {number} fallback
   * @returns {number}
   */
  static _propValue(props, name, fallback) {
    if (!props[name]) return fallback;
    const v = props[name].value;
    return typeof v === 'number' ? v : fallback;
  }
}
