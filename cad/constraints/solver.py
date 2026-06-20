"""2D constraint solver using direct constraint solving with gradient fallback."""

from __future__ import annotations

import math
from typing import Any

from cad.constraints.types import (
    Constraint, ConstraintKind,
    Coincident, Horizontal, Vertical,
    Distance, Angle, Radius, Fix,
)
from cad.core.object import CADObject


class ConstraintError(Exception):
    """Raised when the constraint solver cannot converge."""


def _solve_single_dof(entity: CADObject, prop_name: str,
                       target: float, strength: float = 1.0) -> None:
    """Move a single property toward a target value."""
    prop = entity.get_property(prop_name)
    if prop is not None and not prop.readonly:
        current = prop.value
        error = target - current
        prop.value = current + error * strength


def _solve_double_dof(e1: CADObject, p1: str,
                       e2: CADObject, p2: str,
                       target: float, strength: float = 0.5) -> None:
    """Move two properties symmetrically toward a target relative difference."""
    v1 = e1.get_property_value(p1)
    v2 = e2.get_property_value(p2)
    diff = v1 - v2
    error = diff - target
    correction = error * strength * 0.5
    prop1 = e1.get_property(p1)
    prop2 = e2.get_property(p2)
    if prop1 and not prop1.readonly:
        prop1.value = v1 - correction
    if prop2 and not prop2.readonly:
        prop2.value = v2 + correction


def _direct_solve_horizontal(constraint: Horizontal) -> bool:
    """Directly solve a horizontal constraint by averaging Y values."""
    line = constraint.entities[0]
    y1 = line.get_property_value("y1")
    y2 = line.get_property_value("y2")
    avg = (y1 + y2) * 0.5
    _solve_single_dof(line, "y1", avg, 1.0)
    _solve_single_dof(line, "y2", avg, 1.0)
    return True


def _direct_solve_vertical(constraint: Vertical) -> bool:
    """Directly solve a vertical constraint by averaging X values."""
    line = constraint.entities[0]
    x1 = line.get_property_value("x1")
    x2 = line.get_property_value("x2")
    avg = (x1 + x2) * 0.5
    _solve_single_dof(line, "x1", avg, 1.0)
    _solve_single_dof(line, "x2", avg, 1.0)
    return True


def _direct_solve_coincident(constraint: Coincident) -> bool:
    """Directly solve a coincident constraint by averaging positions."""
    p1 = constraint.entities[0]
    p2 = constraint.entities[1]
    x1 = p1.get_property_value("x")
    y1 = p1.get_property_value("y")
    x2 = p2.get_property_value("x")
    y2 = p2.get_property_value("y")
    avg_x = (x1 + x2) * 0.5
    avg_y = (y1 + y2) * 0.5
    _solve_single_dof(p1, "x", avg_x, 1.0)
    _solve_single_dof(p1, "y", avg_y, 1.0)
    _solve_single_dof(p2, "x", avg_x, 1.0)
    _solve_single_dof(p2, "y", avg_y, 1.0)
    return True


def _direct_solve_distance(constraint: Distance) -> bool:
    """Directly solve a distance constraint by moving points along the line.

    Respects Fix constraints: if a point has readonly properties, only the
    non-fixed point(s) are moved to satisfy the target distance.
    """
    p1 = constraint.entities[0]
    p2 = constraint.entities[1]
    x1 = p1.get_property_value("x")
    y1 = p1.get_property_value("y")
    x2 = p2.get_property_value("x")
    y2 = p2.get_property_value("y")
    dx = x2 - x1
    dy = y2 - y1
    current = math.sqrt(dx * dx + dy * dy)
    if current < 1e-10:
        return False
    target = constraint.target_value

    # Normalize direction vector
    nx = dx / current
    ny = dy / current

    # Determine which properties are movable
    p1_x_ro = p1.get_property("x") is not None and p1.get_property("x").readonly
    p1_y_ro = p1.get_property("y") is not None and p1.get_property("y").readonly
    p2_x_ro = p2.get_property("x") is not None and p2.get_property("x").readonly
    p2_y_ro = p2.get_property("y") is not None and p2.get_property("y").readonly

    p1_movable = not p1_x_ro and not p1_y_ro
    p2_movable = not p2_x_ro and not p2_y_ro

    if not p1_movable and not p2_movable:
        # Neither point can move — cannot satisfy
        return False

    if p1_movable and p2_movable:
        # Both movable: move symmetrically toward/away from midpoint
        mid_x = (x1 + x2) * 0.5
        mid_y = (y1 + y2) * 0.5
        half_dx = nx * target * 0.5
        half_dy = ny * target * 0.5
        _solve_single_dof(p1, "x", mid_x - half_dx, 1.0)
        _solve_single_dof(p1, "y", mid_y - half_dy, 1.0)
        _solve_single_dof(p2, "x", mid_x + half_dx, 1.0)
        _solve_single_dof(p2, "y", mid_y + half_dy, 1.0)
    elif p1_movable:
        # Only p1 moves: place it at target distance along the line
        _solve_single_dof(p1, "x", x2 - nx * target, 1.0)
        _solve_single_dof(p1, "y", y2 - ny * target, 1.0)
    else:
        # Only p2 moves: place it at target distance along the line
        _solve_single_dof(p2, "x", x1 + nx * target, 1.0)
        _solve_single_dof(p2, "y", y1 + ny * target, 1.0)
    return True


def _direct_solve_radius(constraint: Radius) -> bool:
    """Directly set the radius of a circle."""
    circle = constraint.entities[0]
    _solve_single_dof(circle, "radius", constraint.target_value, 1.0)
    return True


class ConstraintSolver:
    """Solves 2D geometric constraints using direct methods with gradient descent fallback.

    For simple constraints (Horizontal, Vertical, Coincident, Distance, Radius),
    direct analytical solutions are used. For complex coupled systems,
    gradient descent is employed as a fallback.
    """

    def __init__(self, max_iterations: int = 100,
                 tolerance: float = 1e-6) -> None:
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self._constraints: list[Constraint] = []

    def add_constraint(self, constraint: Constraint) -> None:
        self._constraints.append(constraint)

    def remove_constraint(self, constraint: Constraint) -> None:
        self._constraints.remove(constraint)

    def clear(self) -> None:
        self._constraints.clear()

    @property
    def constraints(self) -> list[Constraint]:
        return list(self._constraints)

    def solve(self) -> float:
        """Run the solver until convergence. Returns final total error."""
        if not self._constraints:
            return 0.0

        # Phase 1: Direct solve loop (fast convergence for simple constraints)
        prev_error = float('inf')
        for iteration in range(self.max_iterations):
            total_error = self._compute_total_error()

            if total_error < self.tolerance:
                return total_error
            if total_error >= prev_error:
                break  # No further improvement

            prev_error = total_error

            for constraint in self._constraints:
                self._try_direct_solve(constraint)

        # Phase 2: Gradient descent for remaining error (only if needed)
        final_error = self._compute_total_error()
        if final_error > self.tolerance:
            final_error = self._solve_gradient_descent()
        return final_error

    def _try_direct_solve(self, constraint: Constraint) -> bool:
        """Try to directly solve a constraint. Returns True if progress was made."""
        kind = constraint.kind
        try:
            if kind == ConstraintKind.HORIZONTAL:
                return _direct_solve_horizontal(constraint)  # type: ignore
            elif kind == ConstraintKind.VERTICAL:
                return _direct_solve_vertical(constraint)  # type: ignore
            elif kind == ConstraintKind.COINCIDENT:
                return _direct_solve_coincident(constraint)  # type: ignore
            elif kind == ConstraintKind.DISTANCE:
                return _direct_solve_distance(constraint)  # type: ignore
            elif kind == ConstraintKind.RADIUS:
                return _direct_solve_radius(constraint)  # type: ignore
        except Exception:
            pass
        return False

    def _solve_gradient_descent(self) -> float:
        """Fallback gradient descent for complex constraint systems."""
        step = 0.1
        for iteration in range(200):
            total_error = self._compute_total_error()
            if total_error < self.tolerance:
                return total_error

            gradients = self._compute_per_property_gradients()
            if not gradients:
                break

            grad_norm = math.sqrt(sum(g * g for _, _, g in gradients))
            if grad_norm < 1e-15:
                break

            # Line search
            best_error = total_error
            best_step = step
            for trial_factor in [1.0, 0.5, 0.25, 2.0]:
                trial_step = step * trial_factor
                self._apply_gradients(gradients, -trial_step / grad_norm)
                new_error = self._compute_total_error()
                if new_error < best_error:
                    best_error = new_error
                    best_step = trial_step
                # Restore
                self._apply_gradients(gradients, trial_step / grad_norm)

            # Apply best step
            self._apply_gradients(gradients, -best_step / grad_norm)
            step = min(best_step * 1.1, 1.0)

            if abs(best_error - total_error) < 1e-14:
                break

        return self._compute_total_error()

    def _compute_total_error(self) -> float:
        total = 0.0
        for constraint in self._constraints:
            try:
                err = constraint.evaluate(self)
                total += err * err
            except Exception:
                total += 1e6
        return total

    def _compute_per_property_gradients(
        self,
    ) -> list[tuple[CADObject, str, float]]:
        entities: dict[str, CADObject] = {}
        for constraint in self._constraints:
            for entity in constraint.entities:
                entities[str(entity.uid)] = entity

        if not entities:
            return []

        epsilon = 1e-6
        base_error = self._compute_total_error()
        gradients: list[tuple[CADObject, str, float]] = []

        for entity in entities.values():
            for prop_name in ("x", "y", "x1", "y1", "x2", "y2",
                              "cx", "cy", "radius"):
                prop = entity.get_property(prop_name)
                if prop is None or prop.readonly:
                    continue
                original = prop.value
                prop.value = original + epsilon
                new_error = self._compute_total_error()
                prop.value = original

                if isinstance(new_error, (int, float)) and isinstance(base_error, (int, float)):
                    grad = (new_error - base_error) / epsilon
                    if abs(grad) > 1e-12:
                        gradients.append((entity, prop_name, grad))

        return gradients

    def _apply_gradients(
        self,
        gradients: list[tuple[CADObject, str, float]],
        delta: float,
    ) -> None:
        for entity, prop_name, _grad in gradients:
            prop = entity.get_property(prop_name)
            if prop is not None and not prop.readonly:
                prop.value = prop.value + delta

    def get_constraints_by_kind(self, kind: ConstraintKind) -> list[Constraint]:
        return [c for c in self._constraints if c.kind == kind]

    def __repr__(self) -> str:
        return f"ConstraintSolver({len(self._constraints)} constraints)"
