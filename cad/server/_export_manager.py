"""Export manager with pluggable provider pattern.

Built-in providers for STL, OBJ, and SVG are registered by default
when using :func:`build_export_manager`.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from cad.core.document import Document
from fiona.interfaces import ExportError, ExportResult, IExportProvider


class ExportManager:
    """Registry of :class:`IExportProvider` instances.

    Providers are looked up by ``format_name()``.  The manager
    delegates export calls to the matching provider.

    Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._providers: dict[str, IExportProvider] = {}

    def register(self, provider: IExportProvider) -> None:
        """Register an export provider.

        Args:
            provider: An :class:`IExportProvider` instance.

        Raises:
            ValueError: A provider with the same ``format_name()``
                is already registered.
        """
        fmt = provider.format_name()
        with self._lock:
            if fmt in self._providers:
                raise ValueError(
                    f"Export format already registered: {fmt!r}"
                )
            self._providers[fmt] = provider

    def get(self, fmt: str) -> IExportProvider | None:
        """Look up a provider by format name.

        Args:
            fmt: Format identifier (e.g. ``'stl'``, ``'obj'``).

        Returns:
            The matching provider, or *None*.
        """
        with self._lock:
            return self._providers.get(fmt.lower())

    def list_formats(self) -> list[dict[str, Any]]:
        """Return metadata for every registered format.

        Returns:
            A list of dicts with keys ``name`` and ``extensions``.
        """
        with self._lock:
            return [
                {
                    "name": provider.format_name(),
                    "extensions": provider.supported_extensions(),
                }
                for provider in self._providers.values()
            ]

    def export(
        self,
        fmt: str,
        doc: Document,
        path: str,
        **options: Any,
    ) -> ExportResult:
        """Export *doc* to *path* in the specified format.

        Args:
            fmt: Format identifier (e.g. ``'stl'``).
            doc: The document to export.
            path: Destination filesystem path.
            **options: Format-specific options.

        Returns:
            An :class:`ExportResult` with metadata.

        Raises:
            ExportError: The format is not registered or the
                export operation failed.
        """
        provider = self.get(fmt)
        if provider is None:
            raise ExportError(f"Unsupported export format: {fmt!r}")

        resolved = Path(path).expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)

        return provider.export(doc, str(resolved), **options)


# ---------------------------------------------------------------------------
# Built-in export providers
# ---------------------------------------------------------------------------


class StlExportProvider(IExportProvider):
    """STL (ASCII) export provider."""

    def format_name(self) -> str:
        return "stl"

    def supported_extensions(self) -> list[str]:
        return [".stl", ".STL"]

    def export(
        self,
        doc: Document,
        path: str,
        **options: Any,
    ) -> ExportResult:
        from cad.io.export_stl import export_stl

        start = time.perf_counter()
        try:
            export_stl(doc, path, solid_name=options.get("solid_name", "CADModel"))
        except Exception as exc:
            raise ExportError(f"STL export failed: {exc}") from exc
        elapsed = (time.perf_counter() - start) * 1000
        size_bytes = Path(path).stat().st_size
        return ExportResult(
            path=path,
            format="stl",
            size_bytes=size_bytes,
            duration_ms=elapsed,
            warnings=[],
        )


class ObjExportProvider(IExportProvider):
    """Wavefront OBJ export provider."""

    def format_name(self) -> str:
        return "obj"

    def supported_extensions(self) -> list[str]:
        return [".obj", ".OBJ"]

    def export(
        self,
        doc: Document,
        path: str,
        **options: Any,
    ) -> ExportResult:
        from cad.io.export_obj import export_obj

        start = time.perf_counter()
        try:
            export_obj(doc, path)
        except Exception as exc:
            raise ExportError(f"OBJ export failed: {exc}") from exc
        elapsed = (time.perf_counter() - start) * 1000
        size_bytes = Path(path).stat().st_size
        return ExportResult(
            path=path,
            format="obj",
            size_bytes=size_bytes,
            duration_ms=elapsed,
            warnings=[],
        )


class SvgExportProvider(IExportProvider):
    """SVG export provider."""

    def format_name(self) -> str:
        return "svg"

    def supported_extensions(self) -> list[str]:
        return [".svg", ".SVG"]

    def export(
        self,
        doc: Document,
        path: str,
        **options: Any,
    ) -> ExportResult:
        from cad.io.export_svg import export_svg

        width = options.get("width", 800)
        height = options.get("height", 600)
        start = time.perf_counter()
        try:
            export_svg(doc, path, width=width, height=height)
        except Exception as exc:
            raise ExportError(f"SVG export failed: {exc}") from exc
        elapsed = (time.perf_counter() - start) * 1000
        size_bytes = Path(path).stat().st_size
        return ExportResult(
            path=path,
            format="svg",
            size_bytes=size_bytes,
            duration_ms=elapsed,
            warnings=[],
        )
