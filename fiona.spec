# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Fiona — bundles the entire project into a single
Windows executable (``fiona.exe``).

Building
--------
::

    pip install pyinstaller
    pyinstaller fiona.spec

The output lands in ``dist/fiona/``.

Notes
-----
* ``console=True`` so that subprocess-based CLI actions work correctly.
  Set to ``False`` for a windowed-only build if the GUI is the sole surface.
* ``pynput`` Win32 drivers are collected explicitly because PyInstaller
  cannot always auto-detect optional platform backends.
* Optional dependencies (``mediapipe``, ``faster-whisper``, ``sounddevice``)
  are included only if installed; the spec collects their data files safely.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# Collect all first-party Python modules
# ---------------------------------------------------------------------------
FIRST_PARTY_PACKAGES = (
    "QuikTieper",
    "CamComs",
    "Vsee",
    "Agent",
    "PhiConnect",
    "SeeOnDesk",
    "DataClient",
    "EyeControl",
    "TerminalAssist",
    "FionaCore",
    "CmdTrace",
    "RecallVault",
    "Voice",
    "fiona",
)

hidden_imports: list[str] = []
for pkg in FIRST_PARTY_PACKAGES:
    hidden_imports.extend(collect_submodules(pkg))

# ---------------------------------------------------------------------------
# Platform-specific hidden imports
# ---------------------------------------------------------------------------
hidden_imports += [
    # pynput Win32 backends (auto-detected at runtime, must be explicit)
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    # Windows TTS (SAPI5)
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    # Windows notifications
    "plyer.platforms.win.notification",
    # cryptography backends
    "cryptography.hazmat.backends.openssl",
]

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------
datas: list[tuple[str, str]] = [
    # ESP32 payload template (firmware sketch)
    ("CamComs/esp32payload", "CamComs/esp32payload"),
]

# Optional third-party data files (safe to collect even if not installed)
for mod_name in ("mediapipe", "faster_whisper", "sounddevice"):
    try:
        datas.extend(collect_data_files(mod_name))
    except Exception:
        pass  # module not installed — skip

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["fiona/cli.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pyinstaller",
        "tkinter.test",
        "unittest",
        "test",
        "distutils",
        "setuptools",
        "pip",
        "_pytest",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="fiona",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="logo.ico",  # Uncomment and provide a .ico file for a custom icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="fiona",
)
