"""Plotting functions for SciPhi simulation results.

All public functions accept optional *output_path* and return either the
path (when saved), a ``data:image/png;base64,...`` string (when rendered to
memory), or an error message string when ``matplotlib`` is not available.
No function ever raises an import error from a missing ``matplotlib``.
"""

from __future__ import annotations

import base64
import io
import math
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from SciPhi.interfaces.solver import SimulationResult
    from SciPhi.kernel.report import InvestigationReport

# ---------------------------------------------------------------------------
# Colour palette (colorblind-friendly, perceptually uniform)
# ---------------------------------------------------------------------------

_PALETTE = [
    "#00bfff",  # deep-sky-blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # yellow-green
    "#17becf",  # teal
]


def _get_colors(n: int) -> list[str]:
    """Return *n* distinct colours for plotting.

    Args:
        n: Number of colours requested.

    Returns:
        A list of hex colour strings, cycling through a built-in palette when
        *n* exceeds the palette size.
    """
    if n <= len(_PALETTE):
        return _PALETTE[:n]
    # Cycle through the palette for large n.
    repeats = (n // len(_PALETTE)) + 1
    return (_PALETTE * repeats)[:n]


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _is_scalar_data(data: dict[str, Any]) -> bool:
    """Return ``True`` if every value in *data* is a scalar number."""
    return all(isinstance(v, (int, float)) for v in data.values())


def _is_time_series_data(data: dict[str, Any]) -> bool:
    """Return ``True`` if all values are lists of equal length (time series).

    A ``"time"`` or ``"t"`` key is treated as the time axis when present.
    """
    lists = [v for v in data.values() if isinstance(v, (list, tuple))]
    if not lists:
        return False
    lengths = {len(v) for v in lists}
    return len(lengths) == 1


def _is_grid_data(data: dict[str, Any]) -> bool:
    """Return ``True`` if a value contains a 2-D structure.

    Heuristic: at least one value is a list of lists, or all values are
    lists whose elements are themselves sequences.
    """
    for v in data.values():
        if not isinstance(v, (list, tuple)):
            continue
        if v and isinstance(v[0], (list, tuple)):
            return True
    return False


def _time_axis(
    data: dict[str, Any],
) -> list[float]:
    """Extract or synthesize a shared time axis from *data*.

    If a key ``"time"`` or ``"t"`` exists and is a list of numbers, use it.
    Otherwise return ``range(N)`` where *N* is the length of the first
    list-valued entry.
    """
    for key in ("time", "t"):
        val = data.get(key)
        if isinstance(val, (list, tuple)) and len(val) > 0:
            return list(val)
    # Synthesise an index axis.
    for v in data.values():
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return list(range(len(v)))
    return []


# ---------------------------------------------------------------------------
# Matplotlib lazy loader
# ---------------------------------------------------------------------------


def _get_matplotlib():
    """Lazy-import *matplotlib* and return the ``pyplot`` module.

    Returns:
        The ``matplotlib.pyplot`` module, or ``None`` if import fails.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ImportError:
        return None


def _dark_theme(plt) -> None:
    """Apply a dark-background theme to the current pyplot state."""
    try:
        plt.style.use("dark_background")
    except Exception:
        pass
    # Ensure figure background is truly dark.
    plt.rcParams.update(
        {
            "figure.facecolor": "#1a1a2e",
            "axes.facecolor": "#16213e",
            "axes.edgecolor": "#a0a0a0",
            "axes.labelcolor": "#e0e0e0",
            "axes.grid": True,
            "grid.color": "#2a2a4a",
            "grid.alpha": 0.5,
            "text.color": "#e0e0e0",
            "legend.facecolor": "#1a1a2e",
            "legend.edgecolor": "#3a3a5e",
            "xtick.color": "#a0a0a0",
            "ytick.color": "#a0a0a0",
        }
    )


def _save_or_encode(fig, output_path: str | None, plt) -> str | None:
    """Save *fig* to *output_path* or return a base64 data-URL string.

    Args:
        fig: A ``matplotlib.figure.Figure``.
        output_path: Optional file path.
        plt: The ``matplotlib.pyplot`` module.

    Returns:
        *output_path* if saving succeeded, or a ``data:image/png;base64,...``
        string, or ``None`` on failure.
    """
    if output_path:
        try:
            fig.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            return output_path
        except Exception:
            plt.close(fig)
            return None

    # Encode to PNG in memory.
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        plt.close(fig)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot_result(
    result: SimulationResult,
    title: str | None = None,
    output_path: str | None = None,
) -> str | None:
    """Plot simulation result data.

    Behaviour depends on the shape of ``result.data``:

    - **Time series** (all values are lists of equal length): line plot of
      each variable against a shared time / index axis.
    - **Scalar** (all values are single numbers): bar chart.
    - **2-D grid** (any value is a nested list): contour / heatmap of the
      first grid-like variable found.

    Args:
        result: The simulation result to plot.
        title: Optional title for the figure. Defaults to the solver id.
        output_path: If provided, the figure is saved to this path and the
            path is returned. Otherwise a ``data:image/png;base64,...`` data
            URL string is returned.
        **kwargs: Ignored (compatibility placeholder).

    Returns:
        *output_path* when saving, a base64 PNG data URL otherwise, or an
        error message string if ``matplotlib`` is not installed.

    Raises:
        No import-related exceptions are raised.  If ``matplotlib`` is
        missing a plain error string is returned instead.
    """
    plt = _get_matplotlib()
    if plt is None:
        return (
            "matplotlib is not available — install it with "
            "'pip install matplotlib' to enable plotting."
        )

    data = result.data
    _dark_theme(plt)

    resolved_title = title or f"Simulation: {result.solver_id} ({result.solver_method})"

    if not data:
        # Empty dataset → text-only figure.
        fig, ax = plt.subplots(figsize=(8, 4), facecolor="#1a1a2e")
        ax.text(
            0.5,
            0.5,
            "No data to plot.",
            ha="center",
            va="center",
            fontsize=14,
            color="#a0a0a0",
            transform=ax.transAxes,
        )
        ax.set_title(resolved_title, color="#e0e0e0", fontsize=13)
        ax.axis("off")
        return _save_or_encode(fig, output_path, plt)

    if _is_grid_data(data):
        return _plot_grid(data, resolved_title, output_path, plt)

    if _is_scalar_data(data):
        return _plot_scalar(data, resolved_title, output_path, plt)

    if _is_time_series_data(data):
        return _plot_time_series(data, resolved_title, output_path, plt)

    # Fallback: try time-series anyway.
    return _plot_time_series(data, resolved_title, output_path, plt)


def _plot_time_series(
    data: dict[str, Any],
    title: str,
    output_path: str | None,
    plt,
) -> str | None:
    """Render a time-series line plot."""
    from collections import OrderedDict

    t = _time_axis(data)
    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#1a1a2e")
    _dark_theme(plt)

    # Sort variables for deterministic legend order, skipping axis keys.
    axis_keys = {"time", "t", "x", "y", "z"}
    variables = [(k, v) for k, v in data.items() if k not in axis_keys]

    colors = _get_colors(len(variables))

    for (var_name, values), color in zip(variables, colors):
        if isinstance(values, (list, tuple)):
            ax.plot(t, values, label=var_name, color=color, linewidth=1.8)

    ax.set_title(title, color="#e0e0e0", fontsize=13)
    ax.set_xlabel("Time / Index", color="#e0e0e0")
    ax.set_ylabel("Value", color="#e0e0e0")
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    return _save_or_encode(fig, output_path, plt)


def _plot_scalar(
    data: dict[str, Any],
    title: str,
    output_path: str | None,
    plt,
) -> str | None:
    """Render a scalar bar chart."""
    labels = list(data.keys())
    values = [data[k] if isinstance(data[k], (int, float)) else 0 for k in labels]
    colors = _get_colors(len(labels))

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="#1a1a2e")
    _dark_theme(plt)

    bars = ax.bar(labels, values, color=colors, edgecolor="#3a3a5e", linewidth=0.6)
    ax.set_title(title, color="#e0e0e0", fontsize=13)
    ax.set_ylabel("Value", color="#e0e0e0")
    ax.tick_params(axis="x", rotation=45, labelsize=9)

    # Annotate bars with their values.
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{val:.3g}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#e0e0e0",
        )

    fig.tight_layout()
    return _save_or_encode(fig, output_path, plt)


def _plot_grid(
    data: dict[str, Any],
    title: str,
    output_path: str | None,
    plt,
) -> str | None:
    """Render a heatmap / contour of the first grid-like variable."""
    import numpy as np

    # Find the first grid-like variable.
    grid_var = None
    grid_data: list[list[float]] = []
    for var_name, values in data.items():
        if isinstance(values, (list, tuple)) and len(values) > 0:
            if isinstance(values[0], (list, tuple)):
                grid_var = var_name
                grid_data = [[float(vv) for vv in row] for row in values]
                break
    if grid_var is None:
        return _plot_time_series(data, title, output_path, plt)

    arr = np.array(grid_data)

    fig, ax = plt.subplots(figsize=(7, 6), facecolor="#1a1a2e")
    _dark_theme(plt)

    im = ax.imshow(arr, cmap="viridis", aspect="auto", origin="lower")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(grid_var, color="#e0e0e0")
    cbar.ax.yaxis.set_tick_params(color="#a0a0a0")
    plt.setp(plt.getp(cbar.ax.yticklabels), color="#a0a0a0")

    ax.set_title(title, color="#e0e0e0", fontsize=13)
    ax.set_xlabel("Column index", color="#e0e0e0")
    ax.set_ylabel("Row index", color="#e0e0e0")
    fig.tight_layout()
    return _save_or_encode(fig, output_path, plt)


# ---------------------------------------------------------------------------
# plot_report
# ---------------------------------------------------------------------------


def plot_report(
    report: InvestigationReport,
    output_path: str | None = None,
) -> str | None:
    """Generate a multi-panel figure from an investigation report.

    The figure has three panels arranged vertically:

    - **Top:** results plot (calls :func:`plot_result` internally if the
      report holds a simulation result).
    - **Middle:** validation summary — a colour-coded table of
      passed/failed checks.
    - **Bottom:** uncertainty and confidence visualisation.

    Args:
        report: The investigation report to visualise.
        output_path: If provided, the figure is saved to this path and the
            path is returned.

    Returns:
        *output_path* when saving, a base64 PNG data URL otherwise, or an
        error message string if ``matplotlib`` is not installed.
    """
    from SciPhi.interfaces.solver import SimulationResult

    plt = _get_matplotlib()
    if plt is None:
        return (
            "matplotlib is not available — install it with "
            "'pip install matplotlib' to enable plotting."
        )

    _dark_theme(plt)

    # Determine number of panels.
    has_uncertainty = report.uncertainty is not None
    n_panels = 2 + (1 if has_uncertainty else 0)

    fig, axes = plt.subplots(
        n_panels, 1, figsize=(10, 4 * n_panels), facecolor="#1a1a2e"
    )
    if n_panels == 1:
        axes = [axes]

    # -- Top panel: results ------------------------------------------------
    ax_results = axes[0]
    # Try to reconstruct a SimulationResult from the report's results dict.
    sim_data = report.results
    if sim_data and isinstance(sim_data, dict) and "data_summary" in sim_data:
        # We have a data summary but not the raw data — show summary bar chart.
        data_summary = sim_data.get("data_summary", {})
        if data_summary:
            var_names = list(data_summary.keys())
            means = []
            for vn in var_names:
                entry = data_summary[vn]
                if isinstance(entry, dict) and "mean" in entry:
                    means.append(entry["mean"])
                else:
                    means.append(0)
            colors = _get_colors(len(var_names))
            ax_results.bar(var_names, means, color=colors, edgecolor="#3a3a5e")
            ax_results.set_title(
                f"Results — {sim_data.get('status', 'unknown').title()}",
                color="#e0e0e0",
                fontsize=13,
            )
            ax_results.set_ylabel("Mean value", color="#e0e0e0")
            ax_results.tick_params(axis="x", rotation=45, labelsize=9)
        else:
            ax_results.text(
                0.5, 0.5, "No result data.",
                ha="center", va="center", color="#a0a0a0",
                transform=ax_results.transAxes,
            )
            ax_results.set_title("Results", color="#e0e0e0")
            ax_results.axis("off")
    else:
        ax_results.text(
            0.5, 0.5, "Analytical result — no numerical simulation.",
            ha="center", va="center", color="#a0a0a0",
            transform=ax_results.transAxes,
        )
        ax_results.set_title("Results", color="#e0e0e0")
        ax_results.axis("off")

    # -- Middle panel: validation summary -----------------------------------
    ax_val = axes[1]
    validation = report.validation
    checks = validation.checks if validation else []

    if checks:
        _draw_validation_table(ax_val, checks, plt)
    else:
        passed = validation.passed if validation else True
        status_colour = "#2ecc71" if passed else "#e74c3c"
        ax_val.text(
            0.5, 0.55,
            f"Validation: {'PASSED' if passed else 'FAILED'}",
            ha="center", va="center", fontsize=14,
            color=status_colour, transform=ax_val.transAxes,
        )
        ax_val.text(
            0.5, 0.35,
            validation.summary if validation else "No checks performed.",
            ha="center", va="center", fontsize=10,
            color="#a0a0a0", transform=ax_val.transAxes,
        )
        ax_val.set_title("Validation", color="#e0e0e0", fontsize=13)
        ax_val.axis("off")

    # -- Bottom panel: uncertainty / confidence -----------------------------
    if has_uncertainty and n_panels > 2:
        ax_unc = axes[2]
        _draw_uncertainty_panel(ax_unc, report.uncertainty, plt)

    fig.suptitle(
        f"Investigation Report: {report.query[:80]}",
        color="#e0e0e0",
        fontsize=14,
        y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return _save_or_encode(fig, output_path, plt)


def _draw_validation_table(
    ax, checks: list, plt,
) -> None:
    """Draw a colour-coded validation check table."""
    from matplotlib.colors import to_rgba, to_hex

    ax.set_title("Validation Checks", color="#e0e0e0", fontsize=13)
    ax.axis("off")

    n = len(checks)
    # Build a table grid.
    col_labels = ["Check", "Status", "Severity"]
    cell_text: list[list[str]] = []

    for chk in checks:
        status = "✔ Pass" if chk.passed else "✘ Fail"
        sev = chk.severity
        cell_text.append([chk.name, status, sev])

    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        cellLoc="left",
        loc="center",
        colWidths=[0.35, 0.15, 0.15],
    )

    # Style the table.
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    for i, chk in enumerate(checks):
        row_idx = i + 1  # skip header row
        passed = chk.passed
        if not passed and chk.severity == "error":
            colour = "#5a1a1a"  # dark red
        elif not passed:
            colour = "#5a4a1a"  # dark amber
        else:
            colour = "#1a3a1a"  # dark green
        for j in range(3):
            cell = table[row_idx, j]
            cell.set_facecolor(colour)
            cell.set_text_props(color="#e0e0e0")

    # Style header.
    for j in range(3):
        cell = table[0, j]
        cell.set_facecolor("#0f3460")
        cell.set_text_props(color="#e0e0e0", weight="bold")

    table.scale(1, 1.5)
    # Adjust layout so the table is properly visible.
    ax.set_position([0.05, 0.15, 0.9, 0.7])


def _draw_uncertainty_panel(
    ax, uncertainty, plt,
) -> None:
    """Draw the uncertainty and confidence visualisation.

    Shows a horizontal bar for overall confidence and individual source
    magnitudes.
    """
    from matplotlib.colors import to_rgba

    confidence = uncertainty.overall_confidence
    sources = uncertainty.sources if uncertainty.sources else []

    # -- Confidence gauge (simple horizontal bar) --
    ax.barh(
        ["Overall Confidence"],
        [confidence],
        color="#2ecc71" if confidence >= 0.7 else "#f39c12" if confidence >= 0.4 else "#e74c3c",
        edgecolor="#3a3a5e",
        height=0.5,
    )
    ax.set_xlim(0, 1)
    ax.text(
        confidence + 0.02, 0,
        f"{confidence:.0%}",
        va="center", fontsize=10, color="#e0e0e0",
    )

    # -- Source contributions (side-by-side bars) --
    if sources:
        names = [s.name for s in sources]
        mags = [s.magnitude for s in sources]
        colors = _get_colors(len(sources))
        y_offset = -0.8
        for name, mag, color in zip(names, mags, colors):
            ax.barh(
                [name],
                [mag],
                color=color,
                edgecolor="#3a3a5e",
                height=0.4,
                left=0,
            )
            ax.text(
                mag + 0.02, y_offset,
                f"{mag:.0%}",
                va="center", fontsize=9, color="#e0e0e0",
            )
            # Overwrite tick.
            ticks = list(ax.get_yticks())
            ax.set_yticks(list(ax.get_yticks()) + [y_offset])
            y_offset -= 0.7

    ax.set_title("Uncertainty & Confidence", color="#e0e0e0", fontsize=13)
    ax.set_xlabel("Magnitude", color="#e0e0e0")
    ax.axvline(0.5, color="#3a3a5e", linestyle="--", linewidth=0.8)
    ax.tick_params(colors="#a0a0a0")
    ax.set_facecolor("#16213e")

    # Recommendations as text.
    if uncertainty.recommendations:
        rec_text = "\n".join(f"• {r}" for r in uncertainty.recommendations[:3])
        ax.text(
            0.02, -0.15,
            f"Recommendations:\n{rec_text}",
            transform=ax.transAxes,
            fontsize=8, color="#a0a0a0", va="top",
        )


# ---------------------------------------------------------------------------
# plot_comparison
# ---------------------------------------------------------------------------


def plot_comparison(
    results: list[SimulationResult],
    labels: list[str],
    output_path: str | None = None,
) -> str | None:
    """Overlay multiple simulation results for comparison.

    All results must share the same variable structure (same keys in
    ``data``).  Each result is plotted as a separate line series with a
    distinct colour and label.

    Args:
        results: Collection of simulation results to compare.
        labels: Human-readable label for each result (must have the same
            length as *results*).
        output_path: If provided, the figure is saved to this path and the
            path is returned.

    Returns:
        *output_path* when saving, a base64 PNG data URL otherwise, or an
        error message string if ``matplotlib`` is not installed.

    Raises:
        ValueError: If the lengths of *results* and *labels* differ, or if
            the result data dictionaries have incompatible keys.
    """
    plt = _get_matplotlib()
    if plt is None:
        return (
            "matplotlib is not available — install it with "
            "'pip install matplotlib' to enable plotting."
        )

    if len(results) != len(labels):
        return (
            f"Length mismatch: {len(results)} results but "
            f"{len(labels)} labels."
        )

    if not results:
        return "No results to compare."

    # Verify all results have the same variable keys.
    first_keys = set(results[0].data.keys())
    for i, res in enumerate(results[1:], start=1):
        if set(res.data.keys()) != first_keys:
            return (
                f"Result {i} has incompatible variable keys: "
                f"{set(res.data.keys())} vs {first_keys}."
            )

    _dark_theme(plt)

    n_vars = len(first_keys - {"time", "t", "x", "y", "z"})
    axis_keys = {"time", "t", "x", "y", "z"}
    var_keys = [k for k in results[0].data if k not in axis_keys]

    if n_vars == 0:
        # Only axis-like keys present — fall back to all keys.
        var_keys = list(first_keys)

    # Determine if data is time-series (all results have comparable shapes).
    is_ts = all(
        isinstance(results[i].data.get(v, []), (list, tuple))
        for v in var_keys
        for i in range(len(results))
    )

    if is_ts:
        return _plot_comparison_time_series(
            results, labels, var_keys, output_path, plt,
        )

    # Fallback: side-by-side bar groups for scalar data.
    return _plot_comparison_scalar(
        results, labels, var_keys, output_path, plt,
    )


def _plot_comparison_time_series(
    results: list[SimulationResult],
    labels: list[str],
    var_keys: list[str],
    output_path: str | None,
    plt,
) -> str | None:
    """Overlay time-series data for multiple results.

    Creates one subplot per variable, each showing all results as
    overlaid lines.
    """
    n_vars = len(var_keys)
    fig, axes = plt.subplots(
        n_vars, 1, figsize=(10, 3 * n_vars), facecolor="#1a1a2e",
        squeeze=False,
    )
    _dark_theme(plt)

    colors = _get_colors(len(results))

    for idx, var_name in enumerate(var_keys):
        ax = axes[idx, 0]
        for ri, (res, label) in enumerate(zip(results, labels)):
            values = res.data.get(var_name, [])
            if not isinstance(values, (list, tuple)):
                continue
            t = _time_axis(res.data)
            if len(t) != len(values):
                t = list(range(len(values)))
            ax.plot(
                t, values,
                label=label,
                color=colors[ri % len(colors)],
                linewidth=1.6,
                alpha=0.85,
            )
        ax.set_title(var_name, color="#e0e0e0", fontsize=12)
        ax.set_xlabel("Time / Index", color="#e0e0e0")
        ax.set_ylabel("Value", color="#e0e0e0")
        ax.legend(loc="best", fontsize=8)

    fig.suptitle("Simulation Comparison", color="#e0e0e0", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return _save_or_encode(fig, output_path, plt)


def _plot_comparison_scalar(
    results: list[SimulationResult],
    labels: list[str],
    var_keys: list[str],
    output_path: str | None,
    plt,
) -> str | None:
    """Side-by-side grouped bar chart for scalar comparison."""
    import numpy as np

    n_groups = len(var_keys)
    n_results = len(results)

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="#1a1a2e")
    _dark_theme(plt)

    bar_width = 0.8 / n_results
    colors = _get_colors(n_results)

    for ri, (res, label) in enumerate(zip(results, labels)):
        offset = (ri - n_results / 2 + 0.5) * bar_width
        values = [res.data.get(v, 0) if isinstance(res.data.get(v), (int, float)) else 0 for v in var_keys]
        x = np.arange(n_groups) + offset
        ax.bar(
            x, values, bar_width,
            label=label,
            color=colors[ri % len(colors)],
            edgecolor="#3a3a5e",
            linewidth=0.5,
        )

    ax.set_xticks(np.arange(n_groups))
    ax.set_xticklabels(var_keys, rotation=45, ha="right", fontsize=9)
    ax.set_title("Simulation Comparison (Scalar)", color="#e0e0e0", fontsize=13)
    ax.set_ylabel("Value", color="#e0e0e0")
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    return _save_or_encode(fig, output_path, plt)
