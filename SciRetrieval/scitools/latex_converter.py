"""LatexConverter tool — converts between LaTeX expressions and plain text.

Uses ``sympy`` when available for robust LaTeX parsing; falls back to
regex-based conversion for common LaTeX patterns.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fiona.tools.interfaces import ITool
from fiona.tools.models import ToolCategory, ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional sympy import
# ---------------------------------------------------------------------------
try:
    import sympy

    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False

# ---------------------------------------------------------------------------
# Regex-based LaTeX -> text conversion patterns
# ---------------------------------------------------------------------------
# Ordered list of (pattern, replacement) for forward conversion.
_LATEX_TO_TEXT_PATTERNS: list[tuple[str, str]] = [
    # Fractions
    (r"\\frac\{([^}]*)\}\{([^}]*)\}", r"\1/\2"),
    # Superscripts
    (r"\^\{([^}]*)\}", r"^{\1}"),
    (r"\^(\w)", r"^{\1}"),
    # Subscripts
    (r"\_\{([^}]*)\}", r"_{\1}"),
    (r"\_(\w)", r"_{\1}"),
    # Greek letters
    (r"\\alpha", "α"),
    (r"\\beta", "β"),
    (r"\\gamma", "γ"),
    (r"\\delta", "δ"),
    (r"\\epsilon", "ε"),
    (r"\\zeta", "ζ"),
    (r"\\eta", "η"),
    (r"\\theta", "θ"),
    (r"\\iota", "ι"),
    (r"\\kappa", "κ"),
    (r"\\lambda", "λ"),
    (r"\\mu", "μ"),
    (r"\\nu", "ν"),
    (r"\\xi", "ξ"),
    (r"\\omicron", "ο"),
    (r"\\pi", "π"),
    (r"\\rho", "ρ"),
    (r"\\sigma", "σ"),
    (r"\\tau", "τ"),
    (r"\\upsilon", "υ"),
    (r"\\phi", "φ"),
    (r"\\chi", "χ"),
    (r"\\psi", "ψ"),
    (r"\\omega", "ω"),
    (r"\\Gamma", "Γ"),
    (r"\\Delta", "Δ"),
    (r"\\Theta", "Θ"),
    (r"\\Lambda", "Λ"),
    (r"\\Xi", "Ξ"),
    (r"\\Pi", "Π"),
    (r"\\Sigma", "Σ"),
    (r"\\Phi", "Φ"),
    (r"\\Psi", "Ψ"),
    (r"\\Omega", "Ω"),
    # Operators
    (r"\\times", "×"),
    (r"\\cdot", "·"),
    (r"\\div", "÷"),
    (r"\\pm", "±"),
    (r"\\mp", "∓"),
    (r"\\sum", "∑"),
    (r"\\int", "∫"),
    (r"\\prod", "∏"),
    (r"\\partial", "∂"),
    (r"\\nabla", "∇"),
    (r"\\infty", "∞"),
    (r"\\forall", "∀"),
    (r"\\exists", "∃"),
    (r"\\emptyset", "∅"),
    (r"\\subset", "⊂"),
    (r"\\supset", "⊃"),
    (r"\\subseteq", "⊆"),
    (r"\\supseteq", "⊇"),
    (r"\\cup", "∪"),
    (r"\\cap", "∩"),
    (r"\\in", "∈"),
    (r"\\notin", "∉"),
    (r"\\rightarrow", "→"),
    (r"\\leftarrow", "←"),
    (r"\\Rightarrow", "⇒"),
    (r"\\Leftarrow", "⇐"),
    (r"\\approx", "≈"),
    (r"\\neq", "≠"),
    (r"\\leq", "≤"),
    (r"\\geq", "≥"),
    (r"\\sqrt\{([^}]*)\}", r"√(\1)"),
    (r"\\sqrt", "√"),
    # Remove remaining braces used for grouping
    (r"\{", ""),
    (r"\}", ""),
    # Clean up extra spaces around operators
    (r"\s*([+\-=×·÷±])\s*", r" \1 "),
    (r"\s{2,}", " "),
]

# Regex-based text -> LaTeX conversion patterns
_TEXT_TO_LATEX_PATTERNS: list[tuple[str, str]] = [
    # Fractions (a/b -> \frac{a}{b}) — simple cases only
    (r"(\d+)\s*/\s*(\d+)", r"\\frac{\1}{\2}"),
    (r"([a-zA-Zα-ωΑ-Ω])\s*/\s*([a-zA-Zα-ωΑ-Ω])", r"\\frac{\1}{\2}"),
    # Replace unicode operators with LaTeX commands
    ("×", r"\\times "),
    ("·", r"\\cdot "),
    ("÷", r"\\div "),
    ("±", r"\\pm "),
    ("∑", r"\\sum "),
    ("∫", r"\\int "),
    ("∏", r"\\prod "),
    ("∂", r"\\partial "),
    ("∇", r"\\nabla "),
    ("∞", r"\\infty "),
    ("→", r"\\rightarrow "),
    ("←", r"\\leftarrow "),
    ("⇒", r"\\Rightarrow "),
    ("⇐", r"\\Leftarrow "),
    ("≈", r"\\approx "),
    ("≠", r"\\neq "),
    ("≤", r"\\leq "),
    ("≥", r"\\geq "),
    ("∈", r"\\in "),
    ("∉", r"\\notin "),
    ("⊂", r"\\subset "),
    ("⊃", r"\\supset "),
    ("⊆", r"\\subseteq "),
    ("⊇", r"\\supseteq "),
    ("∪", r"\\cup "),
    ("∩", r"\\cap "),
    ("∅", r"\\emptyset "),
    ("∀", r"\\forall "),
    ("∃", r"\\exists "),
    ("√", r"\\sqrt"),
    # Greek letters (unicode -> latex)
    ("α", r"\\alpha"),
    ("β", r"\\beta"),
    ("γ", r"\\gamma"),
    ("δ", r"\\delta"),
    ("ε", r"\\epsilon"),
    ("ζ", r"\\zeta"),
    ("η", r"\\eta"),
    ("θ", r"\\theta"),
    ("ι", r"\\iota"),
    ("κ", r"\\kappa"),
    ("λ", r"\\lambda"),
    ("μ", r"\\mu"),
    ("ν", r"\\nu"),
    ("ξ", r"\\xi"),
    ("ο", r"\\omicron"),
    ("π", r"\\pi"),
    ("ρ", r"\\rho"),
    ("σ", r"\\sigma"),
    ("τ", r"\\tau"),
    ("υ", r"\\upsilon"),
    ("φ", r"\\phi"),
    ("χ", r"\\chi"),
    ("ψ", r"\\psi"),
    ("ω", r"\\omega"),
    # Exponents: a^b
    (r"(\w)\s*\^\s*\{?(\w+)\}?", r"\1^{\2}"),
    # Subscripts: a_b
    (r"(\w)\s*_\s*\{?(\w+)\}?", r"\1_{\2}"),
    # Clean up extra spaces
    (r"\s{2,}", " "),
]


def _latex_to_text_regex(expr: str) -> str:
    """Convert LaTeX to plain text using regex substitutions."""
    result = expr.strip()
    for pattern, replacement in _LATEX_TO_TEXT_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result.strip()


def _text_to_latex_regex(expr: str) -> str:
    """Convert plain text to LaTeX using regex substitutions."""
    result = expr.strip()
    for pattern, replacement in _TEXT_TO_LATEX_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result.strip()


def _latex_to_text_sympy(expr: str) -> str:
    """Convert LaTeX to text using sympy's parsing."""
    # sympy's latex parsing can handle many patterns
    try:
        parsed = sympy.parsing.latex.parse_latex(expr)
        return str(parsed)
    except Exception:
        # Fall back to regex
        return _latex_to_text_regex(expr)


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


class LatexConverter(ITool):
    """Converts between LaTeX expressions and plain text representations.

    Forward direction (default): ``\\frac{1}{2}`` → ``1/2``.
    Reverse direction: ``1/2`` → ``\\frac{1}{2}``.

    Uses ``sympy`` when available for robust parsing; falls back to
    regex-based conversion for common LaTeX patterns.
    """

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="latex_to_text",
            description=(
                "Convert a LaTeX expression to plain text or vice versa. "
                "Forward (default): LaTeX -> text, e.g. "
                "'\\frac{1}{2}' becomes '1/2'. "
                "Reverse: text -> LaTeX, e.g. '1/2' -> '\\frac{1}{2}'."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": (
                            "The LaTeX expression or plain text to convert."
                        ),
                    },
                    "reverse": {
                        "type": "boolean",
                        "description": (
                            "If True, convert plain text to LaTeX instead "
                            "of LaTeX to text."
                        ),
                        "default": False,
                    },
                },
                "required": ["expression"],
            },
            category=ToolCategory.FORMATTING,
        )

    async def run(
        self, context: ToolContext, **kwargs: object
    ) -> ToolResult:
        """Execute the LaTeX conversion.

        Args:
            context: Execution context with logger.
            **kwargs: Must contain ``expression`` (str).  Optional:
                ``reverse`` (bool, default False).

        Returns:
            :class:`ToolResult` with the converted expression.
        """
        expression = kwargs.get("expression")
        if not expression:
            return ToolResult(
                success=False,
                content="",
                error="Missing required argument: 'expression'",
            )

        expr_str = str(expression).strip()
        if not expr_str:
            return ToolResult(
                success=False,
                content="",
                error="Expression is empty",
            )

        reverse = bool(kwargs.get("reverse", False))

        try:
            if reverse:
                # Text -> LaTeX
                if HAS_SYMPY:
                    # Sympy doesn't have a straightforward text->latex parser,
                    # so we always use regex for the reverse direction.
                    result = _text_to_latex_regex(expr_str)
                else:
                    result = _text_to_latex_regex(expr_str)
            else:
                # LaTeX -> Text
                if HAS_SYMPY:
                    result = _latex_to_text_sympy(expr_str)
                else:
                    result = _latex_to_text_regex(expr_str)

            context.logger.debug(
                "latex_converter: %s -> %s", expr_str, result
            )
            return ToolResult(
                success=True,
                content=result,
                metadata={
                    "direction": "latex_to_text" if not reverse else "text_to_latex",
                    "used_sympy": HAS_SYMPY,
                },
            )
        except Exception as exc:
            context.logger.warning("latex_converter failed: %s", exc)
            return ToolResult(
                success=False,
                content="",
                error=f"Conversion failed: {exc}",
            )
