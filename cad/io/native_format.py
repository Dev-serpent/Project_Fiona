"""Native .cad file format — JSON-based serialization of full documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cad.core.document import Document


class CadSerializer:
    """Serializes and deserializes CAD documents to/from the native .cad format.

    The native format is a JSON structure containing:
    - Document metadata
    - All objects with their properties
    - Dependency graph
    - Sketches, constraints, assemblies
    """

    @staticmethod
    def serialize(doc: Document, indent: int = 2) -> str:
        """Serialize a document to JSON string."""
        data = doc.to_dict()
        data["format_version"] = "1.0"
        return json.dumps(data, indent=indent, default=str)

    @staticmethod
    def serialize_to_file(doc: Document, path: str | Path) -> None:
        """Serialize a document to a .cad file."""
        content = CadSerializer.serialize(doc)
        Path(path).write_text(content, encoding="utf-8")

    @staticmethod
    def deserialize(data: str) -> Document:
        """Deserialize a document from JSON string."""
        raw = json.loads(data)
        doc = Document(raw.get("name", "Untitled"))
        doc._metadata = raw.get("metadata", {})

        # Rebuild objects (simplified — full reconstruction needs
        # type registry and property mapping)
        for obj_data in raw.get("objects", []):
            obj_type = obj_data.get("type", "")
            obj_name = obj_data.get("name", "Unknown")
            # In production, use a type registry to reconstruct
            from cad.geometry.primitives import Box, Cylinder, Sphere
            type_map = {
                "Box": Box, "Cylinder": Cylinder,
                "Sphere": Sphere,
            }
            cls = type_map.get(obj_type)
            if cls:
                obj = cls(obj_name)
                for prop_name, prop_data in obj_data.get("properties", {}).items():
                    prop = obj.get_property(prop_name)
                    if prop:
                        prop.value = prop_data.get("value")
                doc.add_object(obj)

        return doc

    @staticmethod
    def deserialize_from_file(path: str | Path) -> Document:
        """Deserialize a document from a .cad file."""
        data = Path(path).read_text(encoding="utf-8")
        return CadSerializer.deserialize(data)
