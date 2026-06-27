"""
SciPhi CLI — command-line interface for scientific investigation.

Registered as ``fiona sciphi <command>`` in ``fiona/cli.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from SciPhi import __version__
from SciPhi.kernel.opsim import OpsimKernel
from SciPhi.models import get_default_model_registry
from SciPhi.solvers import get_default_solver_registry


def _build_parser() -> argparse.ArgumentParser:
    """Build the SciPhi argument parser."""
    parser = argparse.ArgumentParser(
        prog="fiona sciphi",
        description="SciPhi — scientific investigation and simulation engine.",
    )
    parser.add_argument(
        "--version", action="version", version=f"SciPhi v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="sciphi_command", required=True)

    # ── research ────────────────────────────────────────────────────
    research = subparsers.add_parser(
        "research", help="Run a full scientific investigation (Opsim pipeline)."
    )
    research.add_argument("query", type=str, help="Scientific question to investigate")
    research.add_argument(
        "--json", action="store_true", help="Output raw JSON report"
    )

    # ── simulate ────────────────────────────────────────────────────
    simulate = subparsers.add_parser(
        "simulate", help="Run a specific model with parameters."
    )
    simulate.add_argument("model_id", type=str, help="Model identifier")
    simulate.add_argument(
        "--params", type=str, default="{}", help="JSON dict of parameter overrides"
    )

    # ── validate ────────────────────────────────────────────────────
    validate = subparsers.add_parser(
        "validate",
        help="Validate an existing simulation result (load from JSON file).",
    )
    validate.add_argument("result_file", type=str, help="Path to result JSON file")

    # ── list-models ─────────────────────────────────────────────────
    list_models = subparsers.add_parser(
        "list-models", help="List available scientific models."
    )
    list_models.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Filter by domain (physics, chemistry, biology, ...)",
    )

    # ── list-solvers ────────────────────────────────────────────────
    subparsers.add_parser("list-solvers", help="List available solvers.")

    return parser


def _format_report(report: Any) -> str:
    """Format an InvestigationReport as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"  SciPhi Investigation Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Query: {report.query}")
    lines.append(f"Timestamp: {report.timestamp}")
    lines.append("")
    lines.append("── Executive Summary ──")
    lines.append(report.executive_summary)
    lines.append("")

    if report.methodology:
        lines.append("── Methodology ──")
        for key, value in report.methodology.items():
            lines.append(f"  {key}: {value}")
        lines.append("")

    if report.results:
        lines.append("── Results ──")
        for key, value in report.results.items():
            if isinstance(value, list) and len(value) > 10:
                lines.append(f"  {key}: [{len(value)} data points]")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("")

    if report.validation:
        v = report.validation
        lines.append(f"── Validation ({'PASSED' if v.passed else 'FAILED'}) ──")
        for check in v.checks:
            status = "✓" if check.passed else "✗"
            lines.append(f"  {status} {check.name}: {check.detail}")
        lines.append("")

    if report.uncertainty:
        u = report.uncertainty
        lines.append(
            f"── Uncertainty (confidence: {u.overall_confidence:.1%}) ──"
        )
        for source in u.sources:
            lines.append(f"  • {source.name} ({source.type}): {source.description}")
        if u.recommendations:
            lines.append("  Recommendations:")
            for rec in u.recommendations:
                lines.append(f"    - {rec}")
        lines.append("")

    if report.limitations:
        lines.append("── Limitations ──")
        for lim in report.limitations:
            lines.append(f"  • {lim}")
        lines.append("")

    if report.provenance_id:
        lines.append(f"Provenance ID: {report.provenance_id}")

    return "\n".join(lines)


async def _run_research(args: argparse.Namespace) -> None:
    """Run the full Opsim pipeline."""
    kernel = OpsimKernel(
        model_registry=get_default_model_registry(),
        solver_registry=get_default_solver_registry(),
    )
    report = await kernel.investigate(args.query)
    if args.json:
        print(json.dumps(report, default=str, indent=2))
    else:
        print(_format_report(report))


async def _run_simulate(args: argparse.Namespace) -> None:
    """Run a specific model by ID."""
    kernel = OpsimKernel(
        model_registry=get_default_model_registry(),
        solver_registry=get_default_solver_registry(),
    )
    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as e:
        print(f"Error: invalid --params JSON: {e}", file=sys.stderr)
        sys.exit(1)
    result = await kernel.simulate(args.model_id, params)
    print(json.dumps(result, default=str, indent=2))


async def _run_validate(args: argparse.Namespace) -> None:
    """Validate a simulation result from a JSON file."""
    import json

    from SciPhi.interfaces.solver import SimulationResult

    try:
        with open(args.result_file) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading result file: {e}", file=sys.stderr)
        sys.exit(1)

    # Reconstruct SimulationResult from dict (basic reconstruction)
    result = SimulationResult(**data)

    kernel = OpsimKernel(
        model_registry=get_default_model_registry(),
        solver_registry=get_default_solver_registry(),
    )
    report = await kernel.validate(result)
    print(f"Validation {'PASSED' if report.passed else 'FAILED'}")
    for check in report.checks:
        status = "✓" if check.passed else "✗"
        print(f"  {status} {check.name}: {check.detail}")


def _run_list_models(args: argparse.Namespace) -> None:
    """List available models."""
    registry = get_default_model_registry()
    domain_filter = args.domain.lower() if args.domain else None
    for model_id, model in registry.items():
        if domain_filter and model.domain.name.lower() != domain_filter:
            continue
        print(f"  {model_id}")
        print(f"    Domain: {model.domain.name}")
        print(f"    Form:   {model.mathematical_form.name}")
        print(f"    Eqs:    {len(model.equations)}")
        print(f"    Vars:   {len(model.variables)}")
        print(f"    Params: {len(model.parameters)}")
        print()


def _run_list_solvers() -> None:
    """List available solvers."""
    registry = get_default_solver_registry()
    for solver_id, solver in registry.items():
        caps = solver.capabilities
        print(f"  {solver_id}")
        forms = ", ".join(f.name for f in caps.forms)
        methods = ", ".join(caps.methods)
        print(f"    Forms:   {forms}")
        print(f"    Methods: {methods}")
        print(f"    Order:   {caps.order}")
        print(f"    Error estimation: {caps.error_estimation}")
        print()


def main(args: list[str] | None = None) -> None:
    """SciPhi CLI entry point."""
    parser = _build_parser()
    parsed = parser.parse_args(args)

    if parsed.sciphi_command == "research":
        asyncio.run(_run_research(parsed))
    elif parsed.sciphi_command == "simulate":
        asyncio.run(_run_simulate(parsed))
    elif parsed.sciphi_command == "validate":
        asyncio.run(_run_validate(parsed))
    elif parsed.sciphi_command == "list-models":
        _run_list_models(parsed)
    elif parsed.sciphi_command == "list-solvers":
        _run_list_solvers()


if __name__ == "__main__":
    main()
