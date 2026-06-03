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

## Useful System Tools

- `bash`
- `kdotool`
- `ydotool`
- `ydotoold`
- `tk` / `tkinter`
- optional fallback tools: `xprop`, `xdotool`

## Debug Logs

Primary debug log:

```text
~/.config/fiona/debug.log
```

Fallback debug log:

```text
/tmp/fiona-debug.log
```

Logs may contain key press/release traces, binding match/skip reasons, active-window detection results, pointer backend failures, and shell command launch events.

## Permission Notes

`ydotoold` may need privileged startup depending on the machine setup.

Fiona may attempt daemon startup using:

```text
pkexec ydotoold
sudo -n ydotoold
ydotoold
```
