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

LM Studio has been removed from the project — Fiona's Agent bridge now uses **Ollama** for local inference. Support for LM Studio was replaced in favor of the Ollama OpenAI-compatible API.

**Optional extras:**

- `playwright` for browser automation via the BrowserAutomation module: install with `pip install -e ".[browser]"`.
- `aiohttp` for the web frontend (`fionaLocalPages/` server). Install manually if not resolved by the main dependencies.
- EyeControl dependencies (`mediapipe`, `opencv-python`, `pyautogui`): install with `pip install -e ".[eyecontrol]"`.

## System Tools

Runtime tools used by local control:

- `ydotool` for pointer/keyboard automation
- `ydotoold` for daemon-backed Wayland automation
- `kdotool` for KDE/Wayland active-window checks
- `xdotool` and `xprop` as fallback/legacy paths
- `tk` / `tkinter` for GUI windows

If you plan to use browser automation, also install Playwright browsers:

```bash
playwright install
```

## Web Frontend

The `fionaLocalPages/` SPA web dashboard has no additional build step — it is served as static files by an aiohttp Python server.

Ensure `aiohttp` is installed:

```bash
pip install aiohttp
```

Start the web frontend:

```bash
python3 fionaLocalPages/server/app.py
```

Open [http://localhost:8765](http://localhost:8765) in your browser.

Optional flags:

```bash
python3 fionaLocalPages/server/app.py --port 8080 --host 0.0.0.0 --debug
```

## Console Script

After installation, this should work:

```bash
fiona --help
```

If `fiona` prints `command not found`, use the module form from the repository root:

```bash
python3 -m fiona.cli --help
```

## Usage Examples

Once installed, try these commands:

```bash
fiona action list                # List all registered actions
fiona action run my-action       # Run a specific action
fiona browser start              # Start the Playwright browser automation
fiona browser navigate --url https://example.com
fiona voice parse "open browser" # Parse a voice phrase into an action
fiona voice listen               # Listen to microphone and execute detected action
fiona camcoms smoke-test         # Run the encryption smoke test
fiona recall remember my-key my-value --category notes
```
