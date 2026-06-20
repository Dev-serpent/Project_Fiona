"""Geometric transformations — translate, rotate, scale, mirror, project."""

from __future__ import annotations

from cad.geometry.math import Vector3, Matrix4


def translate(v: Vector3) -> Matrix4:
    """Create a translation matrix."""
    return Matrix4.translation(v.x, v.y, v.z)


def rotate(axis: Vector3, angle_rad: float) -> Matrix4:
    """Create a rotation matrix around an axis."""
    return Matrix4.rotation(axis, angle_rad)


def scale(sx: float = 1.0, sy: float = 1.0, sz: float = 1.0) -> Matrix4:
    """Create a scaling matrix."""
    return Matrix4.scaling(sx, sy, sz)


def mirror(normal: Vector3) -> Matrix4:
    """Create a reflection matrix across a plane through origin with given normal."""
    n = normal.normalized()
    x, y, z = n.x, n.y, n.z
    m = Matrix4.identity()
    m.data[0] = 1 - 2 * x * x
    m.data[1] = -2 * x * y
    m.data[2] = -2 * x * z
    m.data[4] = -2 * x * y
    m.data[5] = 1 - 2 * y * y
    m.data[6] = -2 * y * z
    m.data[8] = -2 * x * z
    m.data[9] = -2 * y * z
    m.data[10] = 1 - 2 * z * z
    return m


def transform_point(p: Vector3, matrix: Matrix4) -> Vector3:
    """Transform a point by a 4×4 matrix (with perspective divide)."""
    return matrix.transform_point(p)


def transform_vector(v: Vector3, matrix: Matrix4) -> Vector3:
    """Transform a direction vector by a 4×4 matrix (no translation)."""
    return matrix.transform_vector(v)


def compose(*matrices: Matrix4) -> Matrix4:
    """Compose multiple transforms: result = m1 @ m2 @ m3 ..."""
    result = Matrix4.identity()
    for m in matrices:
        result = m @ result
    return result
