# Developer Note

The full developer journal remains in the repository root:

```text
DEVELOPERNOTE.md
```

This MkDocs page is a public, navigable summary of the same information.

## Runtime Setup

The project has been run from the `quiktieper` Conda environment during development:

```bash
source ~/Applications/miniconda3/etc/profile.d/conda.sh
conda activate quiktieper
cd /home/Dhruv/Documents/Projects/Fiona
```

After dependency changes, install the project in editable mode:

```bash
pip install -e .
```

## Required Python Packages

- Python 3.11+
- `pynput`
- `cryptography`
- `numpy`
- `pandas`
- `requests`
- `aiohttp` — async HTTP server/client for fionaLocalPages and WebSocket/SSE support

## Optional Runtime Packages

- `pvporcupine` — best wake word detection
- `snowboy` — alternative wake word detection
- `pystray` + `Pillow` — system tray icon
- `opencv-python` + `mediapipe` + `pyautogui` — EyeControl camera tracker (via `.[eyecontrol]`)
- `playwright` — browser automation subsystem (BrowserAutomation); install via `playwright install` after pip
- `fionaLocalPages` — web SPA frontend dashboard (requires aiohttp)

## Useful System Tools

- `bash`
- `kdotool`
- `ydotool`
- `ydotoold`
- `tk` / `tkinter`
- `aplay` / `paplay` — audio feedback
- `notify-send` — desktop notifications
- `espeak` / `festival` — speech synthesis
- `scrot` / `gnome-screenshot` — screen capture
- optional fallback tools: `xprop`, `xdotool`, `wmctrl`

## Debug Logs

Primary debug log:

```text
~/.config/fiona/debug.log
```

Fallback debug log:

```text
/tmp/fiona-debug.log
```

Logs may contain key press/release traces, binding match/skip reasons, active-window detection results, pointer backend failures, shell command launch events, ACL resolution results, and pairing request activity.

## Permission Notes

`ydotoold` may need privileged startup depending on the machine setup.

Fiona may attempt daemon startup using:

```text
pkexec ydotoold
sudo -n ydotoold
ydotoold
```

Private key files are automatically saved with `0o600` permissions. This is enforced in `CamComs.paths.ensure_private_permissions()` and called from trust save, identity key rotation, and service health checks.

## Key Storage Paths

```text
~/.config/fiona/identity.json          # Host private identity
~/.config/fiona/identity.pub           # Host public key bundle
~/.config/fiona/trusted/               # Trusted sender directory
~/.config/fiona/sounds/                # Feedback sound files
~/.config/fiona/bindings.json          # QuikTieper binding config
~/.config/fiona/config.json            # Host service config
~/.config/fiona/cmdtrace.jsonl         # Action trace log
~/.config/fiona/debug.log              # Debug log
~/.config/fiona/camcoms/               # Legacy CamComs key paths
~/.config/fiona/phiconnect/            # PhiConnect identity and chat logs
```
