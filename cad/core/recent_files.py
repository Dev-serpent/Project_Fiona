"""Recent files manager — persists recently-opened file paths to JSON."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class RecentFilesManager:
    """Manages a list of recently opened CAD files, persisted to ~/.config/fiona/recent.json.

    New files are inserted at the front. Duplicates are removed.
    The list is trimmed to ``max_files`` entries on each add.
    """

    def __init__(self, max_files: int = 5, config_path: str | None = None) -> None:
        self._max_files = max_files
        if config_path is None:
            config_dir = Path.home() / ".config" / "fiona"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = str(config_dir / "recent.json")
        self._config_path = config_path
        self._files: list[str] = []
        self._load()

    # ── Public API ────────────────────────────────────────────────────

    def add_file(self, path: str) -> None:
        """Add a file path to the recent list (insert at front, remove duplicates).

        Args:
            path: Absolute or relative path to the file. Stored as absolute.
        """
        path = os.path.abspath(path)
        if path in self._files:
            self._files.remove(path)
        self._files.insert(0, path)
        if len(self._files) > self._max_files:
            self._files = self._files[: self._max_files]
        self._save()

    def remove_file(self, path: str) -> None:
        """Remove a file path from the recent list.

        Args:
            path: File path to remove. Matching is done after abspath.
        """
        path = os.path.abspath(path)
        if path in self._files:
            self._files.remove(path)
            self._save()

    def get_files(self) -> list[str]:
        """Return the list of recent file paths (newest first)."""
        return list(self._files)

    def clear(self) -> None:
        """Clear all recent files."""
        self._files.clear()
        self._save()

    # ── Persistence ───────────────────────────────────────────────────

    def _load(self) -> None:
        """Load the recent files list from the JSON config file.

        If the file does not exist or contains invalid JSON, start with an
        empty list. This ensures graceful degradation on first run or
        corruption.
        """
        try:
            data = Path(self._config_path).read_text(encoding="utf-8")
            loaded = json.loads(data)
            if isinstance(loaded, list):
                self._files = [str(p) for p in loaded]
            else:
                self._files = []
        except (FileNotFoundError, json.JSONDecodeError):
            self._files = []

    def _save(self) -> None:
        """Persist the recent files list to the JSON config file."""
        Path(self._config_path).write_text(
            json.dumps(self._files, indent=2), encoding="utf-8"
        )

    # ── Container Protocol ────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._files)

    def __getitem__(self, index: int) -> str:
        return self._files[index]

    def __repr__(self) -> str:
        return f"RecentFilesManager({len(self._files)} files)"
