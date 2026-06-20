"""Ray-object intersection utilities for ray-picking."""

from __future__ import annotations

import math
from typing import Any

from cad.geometry.math import Vector3


def ray_aabb_intersect(
    ray_origin: Vector3,
    ray_dir: Vector3,
    aabb_min: Vector3,
    aabb_max: Vector3,
) -> float | None:
    """Returns *t* (distance along *ray_dir*) of the closest intersection, or
    ``None`` if the ray does not intersect the axis-aligned bounding box.

    Uses the **slab method** for ray-AABB intersection.  The ray direction
    does **not** need to be normalized, but *t* values will be in the same
    scale as *ray_dir*.

    Args:
        ray_origin: Origin of the ray in world space.
        ray_dir: Direction vector of the ray (does not need to be unit).
        aabb_min: Minimum corner of the AABB.
        aabb_max: Maximum corner of the AABB.

    Returns:
        The smallest positive *t* value at which the ray enters the AABB,
        or ``None`` if there is no intersection.
    """
    # Compute inverse direction, handling near-zero components gracefully
    inv_dir = Vector3(
        1.0 / ray_dir.x if abs(ray_dir.x) > 1e-15 else float("inf"),
        1.0 / ray_dir.y if abs(ray_dir.y) > 1e-15 else float("inf"),
        1.0 / ray_dir.z if abs(ray_dir.z) > 1e-15 else float("inf"),
    )

    t1 = (aabb_min.x - ray_origin.x) * inv_dir.x
    t2 = (aabb_max.x - ray_origin.x) * inv_dir.x
    t3 = (aabb_min.y - ray_origin.y) * inv_dir.y
    t4 = (aabb_max.y - ray_origin.y) * inv_dir.y
    t5 = (aabb_min.z - ray_origin.z) * inv_dir.z
    t6 = (aabb_max.z - ray_origin.z) * inv_dir.z

    tmin = max(min(t1, t2), min(t3, t4), min(t5, t6))
    tmax = min(max(t1, t2), max(t3, t4), max(t5, t6))

    if tmax < 0 or tmin > tmax:
        return None

    # If tmin is behind the ray origin, use tmax instead
    if tmin < 0:
        return tmax if tmax > 0 else None

    return tmin


def ray_sphere_intersect(
    ray_origin: Vector3,
    ray_dir: Vector3,
    center: Vector3,
    radius: float,
) -> float | None:
    """Returns the closest positive *t* of ray–sphere intersection, or
    ``None`` if the ray misses the sphere.

    Uses the geometric solution to ``|O + tD - C|² = r²``.

    Args:
        ray_origin: Origin of the ray in world space.
        ray_dir: Direction vector of the ray (does **not** need to be unit).
        center: Center of the sphere.
        radius: Radius of the sphere.

    Returns:
        The smallest positive *t* value at which the ray intersects the
        sphere, or ``None``.
    """
    oc = ray_origin - center
    a = ray_dir.dot(ray_dir)
    b = 2.0 * oc.dot(ray_dir)
    c = oc.dot(oc) - radius * radius
    disc = b * b - 4.0 * a * c

    if disc < 0:
        return None

    sqrt_disc = math.sqrt(disc)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    if t1 > 0:
        return t1
    if t2 > 0:
        return t2
    return None


def ray_cylinder_intersect(
    ray_origin: Vector3,
    ray_dir: Vector3,
    center: Vector3,
    radius: float,
    height: float,
) -> float | None:
    """Returns the closest positive *t* of ray–cylinder intersection, or
    ``None`` if the ray misses.

    The cylinder axis is assumed to be the **Z axis** in local space
    (after translating the ray so the cylinder is at *center*).
    Both the cylindrical body and the two end caps are tested.

    Args:
        ray_origin: Origin of the ray in world space.
        ray_dir: Direction vector of the ray (does **not** need to be unit).
        center: Center of the cylinder (midpoint of the axis).
        radius: Radius of the cylinder.
        height: Height of the cylinder along the Z axis.

    Returns:
        The smallest positive *t* value of the closest intersection
        (body or cap), or ``None``.
    """
    # Translate so cylinder is centered at origin
    oc = ray_origin - center
    half_h = height / 2.0

    # ── Body (infinite cylinder in x-y plane) ─────────────────────────
    a = ray_dir.x * ray_dir.x + ray_dir.y * ray_dir.y
    b = 2.0 * (oc.x * ray_dir.x + oc.y * ray_dir.y)
    c = oc.x * oc.x + oc.y * oc.y - radius * radius

    best_t: float | None = None

    disc = b * b - 4.0 * a * c
    if disc >= 0 and abs(a) > 1e-15:
        sqrt_disc = math.sqrt(disc)
        t1 = (-b - sqrt_disc) / (2.0 * a)
        t2 = (-b + sqrt_disc) / (2.0 * a)

        for t in (t1, t2):
            if t < 0:
                continue
            pz = oc.z + ray_dir.z * t
            if abs(pz) <= half_h:
                if best_t is None or t < best_t:
                    best_t = t

    # ── Caps (top and bottom circles) ─────────────────────────────────
    if abs(ray_dir.z) > 1e-15:
        # Bottom cap: z = -half_h
        t_cap = (-half_h - oc.z) / ray_dir.z
        if t_cap > 0:
            px = oc.x + ray_dir.x * t_cap
            py = oc.y + ray_dir.y * t_cap
            if px * px + py * py <= radius * radius:
                if best_t is None or t_cap < best_t:
                    best_t = t_cap

        # Top cap: z = +half_h
        t_cap = (half_h - oc.z) / ray_dir.z
        if t_cap > 0:
            px = oc.x + ray_dir.x * t_cap
            py = oc.y + ray_dir.y * t_cap
            if px * px + py * py <= radius * radius:
                if best_t is None or t_cap < best_t:
                    best_t = t_cap

    return best_t
