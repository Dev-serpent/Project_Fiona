# EyeControl

EyeControl is Fiona's optional camera-based eye-controlled mouse tracker. The tracker now lives at `EyeControl/Eye_Controlled_Mouse_Tracker.py` and is wrapped as a package so normal Fiona imports, CLI help, docs builds, and tests do not require camera access.

## Status

```bash
python3 -m fiona.cli eyecontrol status
```

The status command checks optional dependencies without opening a camera: `requests`, `cv2`, `numpy`, `mediapipe`, and `pyautogui`.

## Install Optional Dependencies

```bash
pip install -e ".[eyecontrol]"
```

## Run

IP camera snapshot URL:

```bash
python3 -m fiona.cli eyecontrol run --url http://192.168.0.103:8080/shot.jpg
```

Local OpenCV camera:

```bash
python3 -m fiona.cli eyecontrol run --camera-index 0
```

Safer pointer-only test mode:

```bash
python3 -m fiona.cli eyecontrol run --camera-index 0 --no-click
```

## Runtime Mechanics

```text
camera frame
  -> OpenCV decode/capture
  -> horizontal flip
  -> RGB conversion
  -> MediaPipe face mesh
  -> iris landmark tracking
  -> screen coordinate mapping
  -> PyAutoGUI pointer move
  -> optional blink-click detection
  -> OpenCV preview window
```

The camera loop exits when the OpenCV preview window receives `Esc`.

## Current Limits

- requires a real camera or IP camera feed
- requires optional vision/input packages
- not yet integrated into the shared GUI
- not yet connected to SeeOnDesk context or QuikTieper permissions
- blink-clicking should be tested with `--no-click` first
