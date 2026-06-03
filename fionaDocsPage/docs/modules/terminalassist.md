# TerminalAssist

TerminalAssist is Fiona Terminal Assistance (`fAT`). It provides a btop-inspired terminal dashboard, a sliding Fiona command center, and a Zellij workspace helper.

## Commands

Open the sliding command center:

```bash
python3 -m fiona.cli cli
python3 -m fiona.cli fat tui
```

Preview the command center without entering curses mode:

```bash
python3 -m fiona.cli cli --preview
```

Show the dashboard:

```bash
python3 -m fiona.cli fat
python3 -m fiona.cli fat status
```

Print readiness as JSON:

```bash
python3 -m fiona.cli fat json
```

Print or write the Zellij layout:

```bash
python3 -m fiona.cli fat layout --print
python3 -m fiona.cli fat layout --out /tmp/fiona-fat.kdl
```

Launch Zellij with the generated layout:

```bash
python3 -m fiona.cli fat run
```

## Dashboard

The dashboard uses box-drawn panels and a cyan/blue/green palette inspired by terminal monitors such as btop.

Current panels:

- system interpreter and Zellij path
- Fiona readiness checks
- useful fAT commands

## Sliding Command Center

The command center is a curses UI that avoids memorizing the full Fiona command grid.

Controls:

```text
left/right or h/l: slide pages
up/down or k/j: select action
enter: run selected Fiona command
q or Esc: quit
```

One-shot commands load in an internal output panel. Output controls:

```text
up/down: scroll line by line
page up/page down or space: jump
enter, backspace, q, or Esc: return to the command center
```

Interactive or long-running actions are marked with `↗`. Those still run externally because GUI apps, listeners, receivers, and host-service runs need to own the active terminal/session.

Current pages:

- Overview
- QuikTieper
- CamComs
- Host
- Apps

## Zellij Workspace

The generated Zellij layout opens panes for:

- `fiona fat status`
- `fiona host status`
- `fiona camcoms paths`
- `fiona seeondesk status`

This keeps fAT useful as a terminal control surface without replacing the normal Fiona CLI.

## Current Limits

- no search/filter palette yet
- no pane for long-running `fiona run` by default
- no automatic service control from the dashboard yet
- `fiona fat run` requires Zellij to be installed and should be launched intentionally from a real terminal
