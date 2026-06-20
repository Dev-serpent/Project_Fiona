"""Core math types and operations for CAD geometry."""

from __future__ import annotations

import math
from typing import Any


# ── 2D Vector ────────────────────────────────────────────────────────

class Vector2:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)

    def __add__(self, other: Vector2) -> Vector2:
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, s: float) -> Vector2:
        return Vector2(self.x * s, self.y * s)

    def __neg__(self) -> Vector2:
        return Vector2(-self.x, -self.y)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector2):
            return NotImplemented
        return abs(self.x - other.x) < 1e-10 and abs(self.y - other.y) < 1e-10

    def dot(self, other: Vector2) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vector2) -> float:
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self) -> Vector2:
        ln = self.length()
        if ln < 1e-15:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / ln, self.y / ln)

    def perpendicular(self) -> Vector2:
        return Vector2(-self.y, self.x)

    def angle(self) -> float:
        return math.atan2(self.y, self.x)

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}

    @staticmethod
    def from_angle(angle_rad: float, length: float = 1.0) -> Vector2:
        return Vector2(math.cos(angle_rad) * length, math.sin(angle_rad) * length)

    def __repr__(self) -> str:
        return f"Vector2({self.x:.4f}, {self.y:.4f})"


# ── 3D Vector ────────────────────────────────────────────────────────

class Vector3:
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, s: float) -> Vector3:
        return Vector3(self.x * s, self.y * s, self.z * s)

    def __neg__(self) -> Vector3:
        return Vector3(-self.x, -self.y, -self.z)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector3):
            return NotImplemented
        return (abs(self.x - other.x) < 1e-10 and
                abs(self.y - other.y) < 1e-10 and
                abs(self.z - other.z) < 1e-10)

    def dot(self, other: Vector3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y + self.z * self.z

    def normalized(self) -> Vector3:
        ln = self.length()
        if ln < 1e-15:
            return Vector3(0.0, 0.0, 0.0)
        return Vector3(self.x / ln, self.y / ln, self.z / ln)

    def to_2d(self, plane: Plane | None = None) -> Vector2:
        if plane is None:
            return Vector2(self.x, self.y)
        return plane.project_2d(self)

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @staticmethod
    def zero() -> Vector3:
        return Vector3(0.0, 0.0, 0.0)

    @staticmethod
    def unit_x() -> Vector3:
        return Vector3(1.0, 0.0, 0.0)

    @staticmethod
    def unit_y() -> Vector3:
        return Vector3(0.0, 1.0, 0.0)

    @staticmethod
    def unit_z() -> Vector3:
        return Vector3(0.0, 0.0, 1.0)

    def __repr__(self) -> str:
        return f"Vector3({self.x:.4f}, {self.y:.4f}, {self.z:.4f})"


# ── 4×4 Matrix ──────────────────────────────────────────────────────

class Matrix4:
    """Column-major 4×4 transformation matrix."""

    def __init__(self, data: list[float] | None = None) -> None:
        if data is not None and len(data) == 16:
            self.data = list(data)
        else:
            self.data = [0.0] * 16
            self.data[0] = self.data[5] = self.data[10] = self.data[15] = 1.0

    @staticmethod
    def identity() -> Matrix4:
        return Matrix4()

    @staticmethod
    def translation(x: float, y: float, z: float) -> Matrix4:
        m = Matrix4.identity()
        m.data[12] = x
        m.data[13] = y
        m.data[14] = z
        return m

    @staticmethod
    def rotation_x(angle_rad: float) -> Matrix4:
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        m = Matrix4.identity()
        m.data[5] = c; m.data[6] = s
        m.data[9] = -s; m.data[10] = c
        return m

    @staticmethod
    def rotation_y(angle_rad: float) -> Matrix4:
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        m = Matrix4.identity()
        m.data[0] = c; m.data[2] = -s
        m.data[8] = s; m.data[10] = c
        return m

    @staticmethod
    def rotation_z(angle_rad: float) -> Matrix4:
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        m = Matrix4.identity()
        m.data[0] = c; m.data[1] = s
        m.data[4] = -s; m.data[5] = c
        return m

    @staticmethod
    def rotation(axis: Vector3, angle_rad: float) -> Matrix4:
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        t = 1.0 - c
        ax = axis.normalized()
        x, y, z = ax.x, ax.y, ax.z
        m = Matrix4.identity()
        m.data[0] = t * x * x + c; m.data[1] = t * x * y + s * z; m.data[2] = t * x * z - s * y
        m.data[4] = t * x * y - s * z; m.data[5] = t * y * y + c; m.data[6] = t * y * z + s * x
        m.data[8] = t * x * z + s * y; m.data[9] = t * y * z - s * x; m.data[10] = t * z * z + c
        return m

    @staticmethod
    def scaling(sx: float, sy: float, sz: float) -> Matrix4:
        m = Matrix4.identity()
        m.data[0] = sx; m.data[5] = sy; m.data[10] = sz
        return m

    @staticmethod
    def perspective(fov_deg: float, aspect: float, near: float, far: float) -> Matrix4:
        f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
        m = Matrix4()
        m.data[0] = f / aspect
        m.data[5] = f
        m.data[10] = (far + near) / (near - far)
        m.data[11] = -1.0
        m.data[14] = (2.0 * far * near) / (near - far)
        m.data[15] = 0.0
        return m

    @staticmethod
    def look_at(eye: Vector3, target: Vector3, up: Vector3) -> Matrix4:
        f = (target - eye).normalized()
        s = f.cross(up).normalized()
        u = s.cross(f)
        m = Matrix4()
        m.data[0] = s.x; m.data[1] = u.x; m.data[2] = -f.x
        m.data[4] = s.y; m.data[5] = u.y; m.data[6] = -f.y
        m.data[8] = s.z; m.data[9] = u.z; m.data[10] = -f.z
        m.data[12] = -s.dot(eye); m.data[13] = -u.dot(eye); m.data[14] = f.dot(eye)
        return m

    def __matmul__(self, other: Matrix4) -> Matrix4:
        a = self.data
        b = other.data
        result = [0.0] * 16
        for i in range(4):
            for j in range(4):
                result[j * 4 + i] = (
                    a[0 * 4 + i] * b[j * 4 + 0] +
                    a[1 * 4 + i] * b[j * 4 + 1] +
                    a[2 * 4 + i] * b[j * 4 + 2] +
                    a[3 * 4 + i] * b[j * 4 + 3]
                )
        return Matrix4(result)

    def transform_point(self, p: Vector3) -> Vector3:
        d = self.data
        x = p.x * d[0] + p.y * d[4] + p.z * d[8] + d[12]
        y = p.x * d[1] + p.y * d[5] + p.z * d[9] + d[13]
        z = p.x * d[2] + p.y * d[6] + p.z * d[10] + d[14]
        w = p.x * d[3] + p.y * d[7] + p.z * d[11] + d[15]
        if abs(w) > 1e-15:
            return Vector3(x / w, y / w, z / w)
        return Vector3(x, y, z)

    def transform_vector(self, v: Vector3) -> Vector3:
        d = self.data
        return Vector3(
            v.x * d[0] + v.y * d[4] + v.z * d[8],
            v.x * d[1] + v.y * d[5] + v.z * d[9],
            v.x * d[2] + v.y * d[6] + v.z * d[10],
        )

    def inverse(self) -> Matrix4:
        m = self.data
        inv = [0.0] * 16
        inv[0] = m[5]*m[10]*m[15] - m[5]*m[11]*m[14] - m[9]*m[6]*m[15] + m[9]*m[7]*m[14] + m[13]*m[6]*m[11] - m[13]*m[7]*m[10]
        inv[4] = -m[4]*m[10]*m[15] + m[4]*m[11]*m[14] + m[8]*m[6]*m[15] - m[8]*m[7]*m[14] - m[12]*m[6]*m[11] + m[12]*m[7]*m[10]
        inv[8] = m[4]*m[9]*m[15] - m[4]*m[11]*m[13] - m[8]*m[5]*m[15] + m[8]*m[7]*m[13] + m[12]*m[5]*m[11] - m[12]*m[7]*m[9]
        inv[12] = -m[4]*m[9]*m[14] + m[4]*m[10]*m[13] + m[8]*m[5]*m[14] - m[8]*m[6]*m[13] - m[12]*m[5]*m[10] + m[12]*m[6]*m[9]
        det = m[0]*inv[0] + m[1]*inv[4] + m[2]*inv[8] + m[3]*inv[12]
        if abs(det) < 1e-15:
            return Matrix4.identity()
        det_inv = 1.0 / det
        inv[1] = -m[1]*m[10]*m[15] + m[1]*m[11]*m[14] + m[9]*m[2]*m[15] - m[9]*m[3]*m[14] - m[13]*m[2]*m[11] + m[13]*m[3]*m[10]
        inv[5] = m[0]*m[10]*m[15] - m[0]*m[11]*m[14] - m[8]*m[2]*m[15] + m[8]*m[3]*m[14] + m[12]*m[2]*m[11] - m[12]*m[3]*m[10]
        inv[9] = -m[0]*m[9]*m[15] + m[0]*m[11]*m[13] + m[8]*m[1]*m[15] - m[8]*m[3]*m[13] - m[12]*m[1]*m[11] + m[12]*m[3]*m[9]
        inv[13] = m[0]*m[9]*m[14] - m[0]*m[10]*m[13] - m[8]*m[1]*m[14] + m[8]*m[2]*m[13] + m[12]*m[1]*m[10] - m[12]*m[2]*m[9]
        inv[2] = m[1]*m[6]*m[15] - m[1]*m[7]*m[14] - m[5]*m[2]*m[15] + m[5]*m[3]*m[14] + m[13]*m[2]*m[7] - m[13]*m[3]*m[6]
        inv[6] = -m[0]*m[6]*m[15] + m[0]*m[7]*m[14] + m[4]*m[2]*m[15] - m[4]*m[3]*m[14] - m[12]*m[2]*m[7] + m[12]*m[3]*m[6]
        inv[10] = m[0]*m[5]*m[15] - m[0]*m[7]*m[13] - m[4]*m[1]*m[15] + m[4]*m[3]*m[13] + m[12]*m[1]*m[7] - m[12]*m[3]*m[5]
        inv[14] = -m[0]*m[5]*m[14] + m[0]*m[6]*m[13] + m[4]*m[1]*m[14] - m[4]*m[2]*m[13] - m[12]*m[1]*m[6] + m[12]*m[2]*m[5]
        inv[3] = -m[1]*m[6]*m[11] + m[1]*m[7]*m[10] + m[5]*m[2]*m[11] - m[5]*m[3]*m[10] - m[9]*m[2]*m[7] + m[9]*m[3]*m[6]
        inv[7] = m[0]*m[6]*m[11] - m[0]*m[7]*m[10] - m[4]*m[2]*m[11] + m[4]*m[3]*m[10] + m[8]*m[2]*m[7] - m[8]*m[3]*m[6]
        inv[11] = -m[0]*m[5]*m[11] + m[0]*m[7]*m[9] + m[4]*m[1]*m[11] - m[4]*m[3]*m[9] - m[8]*m[1]*m[7] + m[8]*m[3]*m[5]
        inv[15] = m[0]*m[5]*m[10] - m[0]*m[6]*m[9] - m[4]*m[1]*m[10] + m[4]*m[2]*m[9] + m[8]*m[1]*m[6] - m[8]*m[2]*m[5]
        return Matrix4([v * det_inv for v in inv])

    def to_list(self) -> list[float]:
        return list(self.data)

    def to_dict(self) -> dict[str, list[float]]:
        return {"data": self.data}

    def __repr__(self) -> str:
        return f"Matrix4({self.data[:4]}, {self.data[4:8]}, {self.data[8:12]}, {self.data[12:]})"


# ── Plane ────────────────────────────────────────────────────────────

class Plane:
    """A plane defined by origin + normal."""

    def __init__(self, origin: Vector3 = Vector3.zero(),
                 normal: Vector3 = Vector3.unit_z()) -> None:
        self.origin = origin
        self.normal = normal.normalized()
        # Build local coordinate frame
        self._build_frame()

    def _build_frame(self) -> None:
        # Build a canonical orthonormal frame where _u and _v span the plane
        n = self.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        if az >= ax and az >= ay:
            # Normal is closest to Z: use X as reference
            ref = Vector3.unit_x()
        elif ay >= ax and ay >= az:
            # Normal is closest to Y: use Z as reference
            ref = Vector3.unit_z()
        else:
            # Normal is closest to X: use Y as reference
            ref = Vector3.unit_y()
        self._u = n.cross(ref).normalized()
        if self._u.length_sq() < 1e-15:
            # Fallback: use a different reference
            ref2 = Vector3.unit_y() if ref != Vector3.unit_y() else Vector3.unit_z()
            self._u = n.cross(ref2).normalized()
        self._v = n.cross(self._u).normalized()
        # Ensure right-handed frame
        if self._u.cross(self._v).dot(n) < 0:
            self._v = self._v * -1.0

    def project_3d(self, p: Vector2) -> Vector3:
        return self.origin + self._u * p.x + self._v * p.y

    def project_2d(self, p: Vector3) -> Vector2:
        d = p - self.origin
        return Vector2(d.dot(self._u), d.dot(self._v))

    def distance_to(self, p: Vector3) -> float:
        return (p - self.origin).dot(self.normal)

    def side(self, p: Vector3) -> float:
        d = self.distance_to(p)
        if abs(d) < 1e-10:
            return 0.0
        return 1.0 if d > 0 else -1.0

    @staticmethod
    def XY() -> Plane:
        p = Plane.__new__(Plane)
        p.origin = Vector3.zero()
        p.normal = Vector3.unit_z()
        p._u = Vector3.unit_x()
        p._v = Vector3.unit_y()
        return p

    @staticmethod
    def XZ() -> Plane:
        p = Plane.__new__(Plane)
        p.origin = Vector3.zero()
        p.normal = Vector3.unit_y()
        p._u = Vector3.unit_x()
        p._v = Vector3.unit_z()
        return p

    @staticmethod
    def YZ() -> Plane:
        p = Plane.__new__(Plane)
        p.origin = Vector3.zero()
        p.normal = Vector3.unit_x()
        p._u = Vector3.unit_y()
        p._v = Vector3.unit_z()
        return p

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Plane):
            return NotImplemented
        return self.origin == other.origin and self.normal == other.normal

    def __hash__(self) -> int:
        return hash((self.origin, self.normal))

    def to_dict(self) -> dict[str, Any]:
        return {"origin": self.origin.to_dict(), "normal": self.normal.to_dict()}

    def __repr__(self) -> str:
        return f"Plane(origin={self.origin}, normal={self.normal})"


# ── Utility Functions ────────────────────────────────────────────────

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance(a: Vector3, b: Vector3) -> float:
    return (a - b).length()


def normalize(v: Vector3) -> Vector3:
    return v.normalized()
