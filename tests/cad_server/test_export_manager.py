"""Tests for the ExportManager and built-in export providers."""

from __future__ import annotations

import os
import tempfile

import pytest

from cad.core.document import Document
from cad.server._export_manager import (
    ExportManager,
    ObjExportProvider,
    StlExportProvider,
    SvgExportProvider,
)
from fiona.interfaces import ExportError, ExportResult


@pytest.fixture
def doc_with_box() -> Document:
    doc = Document("TestDoc")
    from cad.geometry.primitives import Box
    box = Box("TestBox")
    box.set_property("width", 10)
    box.set_property("height", 20)
    box.set_property("depth", 30)
    doc.add_object(box)
    return doc


@pytest.fixture
def export_manager() -> ExportManager:
    mgr = ExportManager()
    mgr.register(StlExportProvider())
    mgr.register(ObjExportProvider())
    mgr.register(SvgExportProvider())
    return mgr


class TestExportManagerRegistration:
    """Tests for provider registration."""

    def test_register_provider(self) -> None:
        mgr = ExportManager()
        mgr.register(StlExportProvider())
        assert mgr.get("stl") is not None

    def test_register_duplicate_raises(self) -> None:
        mgr = ExportManager()
        mgr.register(StlExportProvider())
        with pytest.raises(ValueError, match="already registered"):
            mgr.register(StlExportProvider())

    def test_register_case_insensitive_lookup(self) -> None:
        mgr = ExportManager()
        mgr.register(StlExportProvider())
        assert mgr.get("STL") is not None
        assert mgr.get("Stl") is not None

    def test_get_nonexistent(self) -> None:
        mgr = ExportManager()
        assert mgr.get("nonexistent") is None

    def test_list_formats(self) -> None:
        mgr = ExportManager()
        mgr.register(StlExportProvider())
        mgr.register(ObjExportProvider())
        formats = mgr.list_formats()
        assert len(formats) == 2
        names = {f["name"] for f in formats}
        assert names == {"stl", "obj"}

    def test_list_formats_empty(self) -> None:
        mgr = ExportManager()
        assert mgr.list_formats() == []


class TestExportManagerExport:
    """Tests for the export() method."""

    def test_export_stl(self, export_manager: ExportManager, doc_with_box: Document) -> None:
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            tmp_path = f.name
        try:
            result = export_manager.export("stl", doc_with_box, tmp_path)
            assert isinstance(result, ExportResult)
            assert result.format == "stl"
            assert os.path.getsize(tmp_path) > 0
            assert result.size_bytes > 0
            assert result.duration_ms >= 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_export_obj(self, export_manager: ExportManager, doc_with_box: Document) -> None:
        with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as f:
            tmp_path = f.name
        try:
            result = export_manager.export("obj", doc_with_box, tmp_path)
            assert result.format == "obj"
            assert os.path.getsize(tmp_path) > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_export_svg(self, export_manager: ExportManager, doc_with_box: Document) -> None:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            tmp_path = f.name
        try:
            result = export_manager.export("svg", doc_with_box, tmp_path)
            assert result.format == "svg"
            assert os.path.getsize(tmp_path) > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_export_unsupported_format(self, export_manager: ExportManager, doc_with_box: Document) -> None:
        with pytest.raises(ExportError, match="Unsupported"):
            export_manager.export("dxf", doc_with_box, "/tmp/out.dxf")

    def test_export_stl_creates_file(self, export_manager: ExportManager, doc_with_box: Document) -> None:
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            tmp_path = f.name
        try:
            export_manager.export("stl", doc_with_box, tmp_path)
            content = open(tmp_path).read()
            assert content.startswith("solid")
            assert "endsolid" in content
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_export_creates_parent_dir(self, export_manager: ExportManager, doc_with_box: Document) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "subdir", "model.stl")
            result = export_manager.export("stl", doc_with_box, nested)
            assert os.path.exists(nested)
            assert result.path == os.path.abspath(nested)

    def test_export_with_options(self, export_manager: ExportManager, doc_with_box: Document) -> None:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            tmp_path = f.name
        try:
            result = export_manager.export("svg", doc_with_box, tmp_path, width=400, height=300)
            assert result.format == "svg"
            assert result.size_bytes > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestExportProviders:
    """Tests for individual export providers."""

    def test_stl_provider_format_name(self) -> None:
        p = StlExportProvider()
        assert p.format_name() == "stl"

    def test_stl_provider_extensions(self) -> None:
        p = StlExportProvider()
        assert ".stl" in p.supported_extensions()

    def test_obj_provider_format_name(self) -> None:
        p = ObjExportProvider()
        assert p.format_name() == "obj"

    def test_obj_provider_extensions(self) -> None:
        p = ObjExportProvider()
        assert ".obj" in p.supported_extensions()

    def test_svg_provider_format_name(self) -> None:
        p = SvgExportProvider()
        assert p.format_name() == "svg"

    def test_svg_provider_extensions(self) -> None:
        p = SvgExportProvider()
        assert ".svg" in p.supported_extensions()

    def test_empty_document_export(self) -> None:
        mgr = ExportManager()
        mgr.register(StlExportProvider())
        doc = Document("Empty")
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            tmp_path = f.name
        try:
            result = mgr.export("stl", doc, tmp_path)
            assert result.size_bytes > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
