"""Parametric value system — expressions, dependencies, automatic recomputation."""

from __future__ import annotations

import re
from typing import Any, Callable


_EXPR_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


class ParametricError(Exception):
    """Raised when a parametric expression cannot be evaluated."""


class Parameter:
    """A named parameter that can reference other parameters via expressions.

    Examples:
        radius = Parameter("radius", 10.0)
        height = Parameter("height", 25.0)
        volume = Parameter("volume", "{{radius}}**2 * 3.14159 * {{height}}")
    """

    def __init__(self, name: str, value: Any = None, expression: str | None = None) -> None:
        self.name = name
        self._value = value
        self._expression = expression
        self._dirty = True
        self._dependents: list[Parameter] = []
        self._resolver: Callable[[str], Any] | None = None

    @property
    def value(self) -> Any:
        if self._dirty and self._expression:
            self._evaluate()
        return self._value

    @value.setter
    def value(self, v: Any) -> None:
        self._value = v
        self._expression = None
        self._mark_dirty()

    @property
    def expression(self) -> str | None:
        return self._expression

    @expression.setter
    def expression(self, expr: str | None) -> None:
        self._expression = expr
        self._mark_dirty()

    def bind(self, resolver: Callable[[str], Any]) -> None:
        self._resolver = resolver

    def _evaluate(self) -> None:
        if not self._expression:
            return
        try:
            resolved = self._expression
            if self._resolver:
                def resolve_var(m: re.Match) -> str:
                    name = m.group(1).strip()
                    val = self._resolver(name)
                    return str(val)
                resolved = _EXPR_PATTERN.sub(resolve_var, resolved)
            self._value = eval(resolved, {"__builtins__": {}}, self._safe_env())
            self._dirty = False
        except Exception as exc:
            raise ParametricError(f"Failed to evaluate '{self._expression}': {exc}") from exc

    def _safe_env(self) -> dict[str, Any]:
        import math
        return {
            "abs": abs, "min": min, "max": max,
            "sum": sum, "round": round,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "radians": math.radians, "degrees": math.degrees,
            "sqrt": math.sqrt, "pi": math.pi,
            "pow": pow,
        }

    def _mark_dirty(self) -> None:
        self._dirty = True
        for dep in self._dependents:
            dep._mark_dirty()

    def add_dependent(self, param: Parameter) -> None:
        self._dependents.append(param)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self._value,
            "expression": self._expression,
        }


class ParametricValue:
    """A descriptor-style parametric value that auto-resolves on access."""

    def __init__(self, default: Any = None, expression: str | None = None):
        self.default = default
        self.expression = expression
        self._values: dict[int, Any] = {}

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return self._values.get(id(obj), self.default)

    def __set__(self, obj: Any, value: Any) -> None:
        self._values[id(obj)] = value
