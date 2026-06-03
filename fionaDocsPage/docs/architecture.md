# Architecture

Fiona is the umbrella package. It exposes nine sibling subsystems.

## Subsystems

- `QuikTieper`: local access layer for keyboard chords, app launching, shortcuts, pointer movement, clicks, and remote action execution.
- `CamComs`: communication layer for encoded/encrypted messages and host receiver behavior.
- `Vsee`: 3D coordinate hologram viewer for point/edge wireframe shapes.
- `Agent`: local LM Studio bridge for the future agent layer.
- `PhiConnect`: standalone encrypted computer-to-computer chat using CamComs crypto.
- `SeeOnDesk`: desktop-awareness layer for identifying the current session and focused app/window.
- `DataClient`: standalone research/data collection app, MiniExcel, conversion tools, and CSV export.
- `EyeControl`: optional camera-based eye-controlled mouse tracker.
- `TerminalAssist`: btop-style terminal dashboard and Zellij workspace helper.

## Project Layout

```text
fiona/                 umbrella package and CLI entrypoint
QuikTieper/            local access/action layer
CamComs/               communication/encryption/host service layer
CamComs/esp32payload/  ESP32 sender payload template
Vsee/                  3D point/edge hologram model
Agent/                 local LM Studio client
PhiConnect/            encrypted computer-to-computer chat app
SeeOnDesk/             desktop awareness and active-window identification
DataClient/            research/data collection app
EyeControl/            optional eye-controlled mouse tracker
TerminalAssist/        terminal dashboard and Zellij layout helper
scripts/               local launch wrappers
tests/                 Python tests
DEVELOPERNOTE.md       detailed project notes and verification log
pyproject.toml         package metadata and Python dependencies
```

## Communication Shape

CamComs currently focuses on:

```text
ESP32 sender -> encoded encrypted HTTP POST -> Fiona host receiver
```

PhiConnect uses the same cryptographic primitives for computer-to-computer chat:

```text
Fiona peer -> encrypted chat envelope -> PhiConnect receiver
```

## CLI Shape

```text
fiona quiktieper ...
fiona host ...
fiona camcoms ...
fiona agent ...
fiona seeondesk ...
fiona dataclient ...
fiona eyecontrol ...
fiona fat ...
fiona vsee
fiona phiconnect
```

Shortcuts also exist for QuikTieper:

```text
fiona edit
fiona run
fiona list
```
