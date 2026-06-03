# QuikTieper

QuikTieper is Fiona's local access layer. It listens for simultaneous global key chords and runs configured actions.

## Config

Default config path:

```text
~/.config/fiona/bindings.json
```

## Basic Commands

```bash
python3 -m fiona.cli init
python3 -m fiona.cli list
python3 -m fiona.cli run
python3 -m fiona.cli edit
```

Installed-command equivalents:

```bash
fiona init
fiona list
fiona run
fiona edit
```

Explicit layer commands:

```bash
python3 -m fiona.cli quiktieper list
python3 -m fiona.cli quiktieper run
python3 -m fiona.cli quiktieper edit
```

## App Import

QuikTieper can discover installed Linux `.desktop` launchers and import them into the bindings file.

```bash
python3 -m fiona.cli import-apps --dry-run
python3 -m fiona.cli import-apps
```

Filtering behavior:

- skips obvious games, demos, helpers, uninstallers, and many settings panels
- skips most `K...` apps by default
- keeps practical KDE tools such as Konsole, Kate, KWrite, KCalc, KDE Connect, KDE System Settings, Kdenlive, KDevelop, KMail, KOrganizer, KRDC, and KSystemLog

Override flags:

```bash
python3 -m fiona.cli import-apps --include-all-k-apps
python3 -m fiona.cli import-apps --include-low-value-apps
```

## Key Assignment

Generated app launch chords use `alt` plus three distinct safer letters and avoid duplicate pressed-key sets.

```bash
python3 -m fiona.cli assign-keys --dry-run
python3 -m fiona.cli assign-keys
python3 -m fiona.cli assign-keys --reassign
```

## Command Normalization

`normalize-app-cmds` applies curated command presets for common workstation apps.

```bash
python3 -m fiona.cli normalize-app-cmds --dry-run
python3 -m fiona.cli normalize-app-cmds
```

## Capabilities

- app launching from chord bindings
- installed desktop application discovery
- app-specific shortcuts gated by active-window matching
- shell command execution
- pointer movement and click helpers
- allowlisted remote actions for CamComs instructions
- structured macro instructions with nested steps

## Example Bindings

- `alt + b + r + v` opens Brave
- `alt + v + s + c` opens VS Code
- `alt + t + e + r` opens terminal
