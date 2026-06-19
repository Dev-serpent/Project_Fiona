# Voice

Voice is Fiona's speech interface subsystem. It provides wake-word detection, push-to-talk, and audio/visual feedback.

## Wake Word Engine

The `WakeWordEngine` detects a spoken wake word and triggers registered callbacks.

**Supported backends** (auto-detected in priority order):

| Backend | Library | Quality |
|---------|---------|---------|
| Picovoice | `pvporcupine` | Best (offline, fast) |
| Snowboy | `snowboy` | Good |
| MyCroft Precise | `mycroft_precise` | Good |

Gracefully degrades if no backend is installed — logs a warning and allows manual trigger via push-to-talk.

## Push-to-Talk

The `PushToTalk` class implements a global hotkey listener using `pynput`.

- Default hotkey: `Ctrl+Space`
- Fires `on_press` and `on_release` callbacks
- Gracefully disables itself if `pynput` is not available

## Feedback Engine

The `FeedbackEngine` provides three feedback channels:

| Channel | Mechanism | Fallback |
|---------|-----------|----------|
| Audio | Plays `.wav`/`.mp3`/`.ogg` via `aplay` or `paplay` | Silent if no sound file |
| Desktop notification | `notify-send` with urgency levels | Silent if unavailable |
| Status bar | Text output (GUI status area) | Always available |

Convenience methods:

```python
feedback.acknowledge()   # "Listening..." sound + notification
feedback.success(msg)    # Success sound + notification
feedback.error(msg)      # Error sound + critical notification
```

Sound files are stored in `~/.config/fiona/sounds/`.

## GUI Tab

The **Voice** tab in the shared editor (`fiona edit`) provides:

**Voice Control** section:
- Wake word engine status (Available / Unavailable)
- Start/Stop listening toggle
- Wake word text entry (default "fiona")
- Manual trigger button ("Hey Fiona")

**Feedback** section:
- Test sound buttons (Ack, Error, Success)
- Test Notification button
- Urgency selector (low / normal / critical)

**Push to Talk** section:
- Status indicator (Available / Unavailable)
- Hotkey display (Ctrl+Space)
- Start/Stop listener toggle

## CLI Commands

```bash
fiona voice wake-test      # Test wake word detection
fiona voice feedback-test  # Test audio/notification feedback
```

## Dependencies

Optional runtime dependencies (not required for base installation):

```bash
pip install pvporcupine     # Best wake word detection
pip install snowboy         # Alternative wake word detection
# pynput is a core dependency (already installed)
```

## Graceful Degradation

All Voice components follow Fiona's graceful degradation pattern:

- If no wake word library is installed → engine reports "Unavailable", works via manual trigger only
- If `pynput` is missing → push-to-talk reports "Unavailable"
- If no sound files exist → `play_sound()` returns `False` without error
- If `notify-send` is missing → notifications silently fail
