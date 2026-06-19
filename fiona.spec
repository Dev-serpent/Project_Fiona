# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Fiona — bundles the entire project into a single
executable.

Building
--------::

    pip install pyinstaller
    pyinstaller fiona.spec

The output lands in ``dist/fiona/``.

Cross-platform notes
--------------------
* On **Windows** → produces ``dist/fiona/fiona.exe``
* On **Linux**   → produces ``dist/fiona/fiona`` (ELF binary)
* On **macOS**   → produces ``dist/fiona/fiona`` (Mach-O binary)

Windows .exe builds from Linux
-------------------------------
To cross-compile a Windows .exe on Linux:

1. Install Python for Windows under Wine:
   wine pip install pyinstaller fiona-requirements.txt

2. Run PyInstaller under Wine:
   wine python -m PyInstaller fiona.spec

Or build natively on a Windows machine where the full dependency chain
(pynput Win32 backends, SAPI5 TTS, WinRT notifications) is available.

Icon
----
Place a ``logo.ico`` (Windows) or ``logo.png`` (Linux/macOS) in the project
root and uncomment the ``icon=`` line in the EXE() stanza below.
"""

import platform
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
_os = platform.system()

if _os == "Windows":
    # pynput Win32 backends (auto-detected at runtime, must be explicit)
    hidden_imports += [
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # Windows TTS (SAPI5)
        "pyttsx3.drivers",
        "pyttsx3.drivers.sapi5",
        # Windows notifications (WinRT)
        "plyer.platforms.win.notification",
    ]
elif _os == "Linux":
    # pynput X11 / Wayland backends (auto-detected at runtime)
    hidden_imports += [
        "pynput.keyboard._xorg",
        "pynput.mouse._xorg",
        # Linux notifications
        "plyer.platforms.linux.notification",
        # pyttsx3 speech-dispatcher / espeak backends
        "pyttsx3.drivers",
        "pyttsx3.drivers.espeak",
        "pyttsx3.drivers.dummy",
    ]
elif _os == "Darwin":
    hidden_imports += [
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        "plyer.platforms.macosx.notification",
        "pyttsx3.drivers",
        "pyttsx3.drivers.nsss",
    ]

# Cross-platform backends always needed
hidden_imports += [
    "cryptography.hazmat.backends.openssl",
    # pystray (system tray icon; platform backends loaded at runtime)
    "pystray",
]

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------
datas: list[tuple[str, str]] = [
    # ESP32 payload template (firmware sketch)
    ("CamComs/esp32payload", "CamComs/esp32payload"),
]

# Optional third-party data files (safe to collect even if not installed)
for mod_name in ("mediapipe", "faster_whisper", "sounddevice", "PIL"):
    try:
        datas.extend(collect_data_files(mod_name))
    except Exception:
        pass  # module not installed — skip

# ---------------------------------------------------------------------------
# Runtime hooks (run before the script starts)
# ---------------------------------------------------------------------------
runtime_hooks: list[str] = []

# ---------------------------------------------------------------------------
# Exclude unnecessary modules (reduces bundle size)
# ---------------------------------------------------------------------------
excludes = [
    "pyinstaller",
    "tkinter.test",
    # unittest/test removal can break PyInstaller internal hooks on some
    # Python versions; keep them if you see import errors.
    "unittest",
    "test",
    "pip",
    "_pytest",
    "pytest",
    "http.cookiejar",
    "http.cookies",
    "turtle",
    "turtledemo",
    "zoneinfo",
    # Distutils / setuptools excluded via comment below — they are needed
    # by PyInstaller's pre_safe_import_module hooks, so do NOT add them
    # to this list.
    # "distutils",
    # "setuptools",
]

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
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# Icon selection
# ---------------------------------------------------------------------------
icon_path = None
for candidate in ("logo.ico", "logo.png", "logo.svg"):
    p = Path(candidate)
    if p.exists():
        icon_path = str(p.resolve())
        break

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
    # console=True so subprocess-based CLI actions work correctly.
    # Set to False for a windowed-only build if the GUI is the sole surface.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
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
