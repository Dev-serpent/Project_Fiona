"""Geometry modifiers — extrude, revolve, sweep, loft, project."""

from __future__ import annotations

import math
from typing import Any

from cad.geometry.math import Vector3, Matrix4, Plane


def extrude(vertices: list[Vector3], direction: Vector3, distance: float) -> list[Vector3]:
    """Extrude a set of 3D vertices along a direction.

    Returns the original + extruded vertices forming a solid.
    """
    offset = direction.normalized() * distance
    extruded = [v + offset for v in vertices]
    return vertices + extruded


def revolve(vertices: list[Vector3], axis_point: Vector3,
            axis_dir: Vector3, angle_deg: float,
            segments: int = 32) -> list[Vector3]:
    """Revolve vertices around an axis."""
    axis = axis_dir.normalized()
    angle_rad = math.radians(angle_deg)
    result: list[Vector3] = []
    for i in range(segments + 1):
        theta = angle_rad * i / segments
        m = Matrix4.rotation(axis, theta)
        t = Matrix4.translation(axis_point.x, axis_point.y, axis_point.z)
        tm = t @ m @ t.inverse()
        for v in vertices:
            result.append(tm.transform_point(v))
    return result


def sweep(profile: list[Vector3], path: list[Vector3]) -> list[Vector3]:
    """Sweep a profile along a path (simple translation at each path point)."""
    if not path:
        return profile
    result: list[Vector3] = []
    for i, p in enumerate(path):
        if i == 0:
            continue
        prev = path[i - 1]
        delta = p - prev
        for v in profile:
            result.append(v + delta)
    return result


def loft(profiles: list[list[Vector3]]) -> list[list[Vector3]]:
    """Loft between multiple profiles. Returns interpolated cross-sections."""
    if not profiles:
        return []
    if len(profiles) == 1:
        return profiles
    result: list[list[Vector3]] = [profiles[0]]
    for i in range(1, len(profiles)):
        prev = profiles[i - 1]
        curr = profiles[i]
        # Simple linear interpolation between corresponding vertices
        n = min(len(prev), len(curr))
        interp = [(prev[j] + curr[j]) * 0.5 for j in range(n)]
        result.append(interp)
    result.append(profiles[-1])
    return result


def project_point(point: Vector3, plane: Plane) -> Vector3:
    """Project a 3D point onto a plane."""
    d = plane.distance_to(point)
    return point - plane.normal * d


def project_vector(v: Vector3, plane: Plane) -> Vector3:
    """Project a vector onto a plane."""
    n = plane.normal
    return v - n * v.dot(n)
