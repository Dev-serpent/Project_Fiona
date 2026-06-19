from __future__ import annotations

import os
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def capture_screen(output_path: str | Path) -> bool:
    """
    Capture the entire screen and save to output_path.
    Prioritizes spectacle on KDE, then grim on Wayland, then scrot.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    # KDE specific
    if "KDE" in desktop and shutil.which("spectacle"):
        # -b: background, -n: non-interactive, -o: output
        if _run(["spectacle", "-b", "-n", "-o", str(output_path)]):
            return True

    # Wayland generic
    if session_type == "wayland":
        if shutil.which("grim"):
            if _run(["grim", str(output_path)]):
                return True
    
    # Fallback to scrot
    if shutil.which("scrot"):
        if _run(["scrot", "-o", str(output_path)]):
            return True
    
    # Try gnome-screenshot
    if shutil.which("gnome-screenshot"):
        if _run(["gnome-screenshot", "-f", str(output_path)]):
            return True

    return False


def capture_window(window_id: str, output_path: str | Path) -> bool:
    """
    Capture a specific window by ID.

    Tries kdotool to activate the target window first, then captures the
    now-focused window via ``scrot -u``.  Falls back to capturing the
    currently focused window if kdotool fails.

    .. note::
       The ``window_id`` parameter is best-effort on X11.  If kdotool is
       not available the function captures the focused window regardless
       of *window_id*.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try to bring the target window into focus for capture
    if shutil.which("kdotool"):
        try:
            subprocess.run(
                ["kdotool", "activate", window_id],
                capture_output=True, timeout=3,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.debug("kdotool activate %s failed", window_id)

    # Capture the now-focused window (or current focused window as fallback)
    if shutil.which("scrot"):
        return _run(["scrot", "-u", "-o", str(output_path)])

    # Try gnome-screenshot with window flag
    if shutil.which("gnome-screenshot"):
        return _run(["gnome-screenshot", "-w", "-f", str(output_path)])

    logger.warning("No screen capture tool found (scrot or gnome-screenshot)")
    return False


def analyze_screen(prompt: str, image_path: str | Path | None = None) -> str:
    """
    Capture the screen and ask the local agent to analyze it.
    If image_path is not provided, it captures a temporary screenshot.
    """
    from Agent.ollama import OllamaClient
    
    temp_image = False
    if image_path is None:
        image_path = Path("/tmp/fiona_analysis.png")
        if not capture_screen(image_path):
            return "Error: Failed to capture screen for analysis."
        temp_image = True
    
    try:
        client = OllamaClient()
        result = client.ask(prompt, image_path=image_path)
        return result
    except Exception as exc:
        return f"Error during vision analysis: {exc}"
    finally:
        if temp_image and Path(image_path).exists():
            Path(image_path).unlink()


def _run(args: list[str]) -> bool:
    try:
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
