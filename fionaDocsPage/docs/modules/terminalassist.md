# TerminalAssist

TerminalAssist is Fiona Terminal Assistance (`fAT`). It provides a high-fidelity, btop-inspired terminal dashboard, a real-time sliding command center, and a system status API.

## Commands

Open the sliding command center:

```bash
fiona cli
# or
fiona fat tui
```

Preview the command center without entering curses mode:

```bash
fiona cli --preview
```

Show the redesigned dashboard:

```bash
fiona fat status
```

Print machine-readable system status (JSON API):

```bash
fiona api
# or shortcut
fiona fat api
```

## Dashboard

The dashboard is a high-density system monitor inspired by `btop`. It features live resource tracking and project environment checks.

Live metrics include:
- **System**: Hostname, Kernel, Uptime, User, OS, Architecture.
- **CPU**: Model, Usage %, Per-core usage, Speed, and Temperature.
- **Memory**: RAM (Used/Total) and Swap usage.
- **Disk**: Root partition usage and I/O activity (Read/Write).
- **Network**: IP address, Interface, Traffic (RX/TX), and Signal strength (if Wi-Fi).
- **GPU**: Utilization and Temperature (NVIDIA/Intel/AMD).
- **Power**: Battery percentage and charging state (for laptops).
- **Security**: Firewall status and available system updates.

## Real-Time Command Center

The command center is a fullscreen curses UI with a non-blocking 1-second auto-refresh engine.

Controls:

```text
left/right or h/l: slide pages
up/down or k/j:    select action
/:                live search across all actions
enter:            run selected action
q or Esc:         quit (or clear search)
```

### Quick Actions Page
The TUI includes a **Quick Actions** page that detects your current Desktop Environment (KDE, GNOME, XFCE) and provides session controls:
- **Lock Screen**
- **Logout**
- **Suspend**
- **Reboot**
- **Shutdown**

### Search and Navigation
Press `/` to enter search mode. As you type, the TUI filters all available actions across all pages in real-time.

### Dynamic Pages
The TUI includes dynamic data-driven pages:
- **History**: Displays the 10 most recent actions from the `CmdTrace` log.
- **Recall**: Displays the 10 most recent snippets from the `RecallVault`.

### Output Capture
One-shot commands load in an internal output panel. Output controls:

```text
up/down: scroll line by line
page up/page down or space: jump
enter, backspace, q, or Esc: return to the command center
```

Interactive or long-running actions (marked with `↗`) such as `btop` or GUI apps launch externally in the foreground.

## Management Page
The TUI includes a **Management** page for quick access to system tools:
- **System Monitor (btop)**: Direct shortcut to launch btop.
- **Status dashboard**: Text-based system summary.
- **Host status**: Detailed host service checks.
- **Open editor**: Fiona GUI configuration editor.

## Zellij Workspace
fAT can generate and launch a multi-pane Zellij workspace:

```bash
fiona fat run
```

## Current Limits

- no automatic service control from the dashboard yet
- `fiona fat run` requires Zellij to be installed and should be launched intentionally from a real terminal
