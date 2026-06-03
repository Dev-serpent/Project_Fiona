# Installation

Clone the repository, create or activate a Python environment, and install Fiona in editable mode.

## Virtualenv

```bash
git clone <repo-url> Fiona
cd Fiona
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Conda

```bash
conda create -n fiona python=3.13
conda activate fiona
git clone <repo-url> Fiona
cd Fiona
pip install -e .
```

The current development environment has used a Conda environment named `quiktieper`:

```bash
source ~/Applications/miniconda3/etc/profile.d/conda.sh
conda activate quiktieper
cd /home/Dhruv/Documents/Projects/Fiona
pip install -e .
```

## Python Dependencies

Declared in `pyproject.toml`:

- `cryptography`
- `pynput`
- `numpy`
- `pandas`
- `requests`

LM Studio is optional. Fiona talks to LM Studio only when the Agent bridge is used.

## System Tools

Runtime tools used by local control:

- `ydotool` for pointer/keyboard automation
- `ydotoold` for daemon-backed Wayland automation
- `kdotool` for KDE/Wayland active-window checks
- `xdotool` and `xprop` as fallback/legacy paths
- `tk` / `tkinter` for GUI windows

## Console Script

After installation, this should work:

```bash
fiona --help
```

If `fiona` prints `command not found`, use the module form from the repository root:

```bash
python3 -m fiona.cli --help
```
