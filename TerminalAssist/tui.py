from __future__ import annotations

import curses
import os
import re
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from typing import Callable

from CmdTrace import read_trace
from FionaCore import ActionRouter, parse_voice_command, quick_transcribe, speak
from RecallVault import search_recall
from .dashboard import build_dashboard, get_mouse_info, terminal_assist_status

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CliAction:
    label: str
    command: tuple[str, ...]
    description: str
    external: bool = False


@dataclass(frozen=True)
class CliPage:
    title: str
    subtitle: str
    actions: tuple[CliAction, ...]


def detect_de() -> str:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    if "KDE" in desktop:
        return "KDE"
    if "GNOME" in desktop:
        return "GNOME"
    if "XFCE" in desktop:
        return "XFCE"
    return "UNKNOWN"


def get_quick_actions() -> tuple[CliAction, ...]:
    de = detect_de()
    actions = []
    if de == "KDE":
        actions.append(CliAction("Lock Screen", ("run-shell", "loginctl lock-session"), "Lock the current KDE session.", external=True))
        actions.append(CliAction("Logout", ("run-shell", "qdbus-qt5 org.kde.ksmserver /KSMServer logout 1 0 1"), "Logout of KDE.", external=True))
    elif de == "GNOME":
        actions.append(CliAction("Lock Screen", ("run-shell", "gnome-screensaver-command -l"), "Lock the GNOME session.", external=True))
        actions.append(CliAction("Logout", ("run-shell", "gnome-session-quit --logout --no-prompt"), "Logout of GNOME.", external=True))
    
    actions.append(CliAction("Suspend", ("run-shell", "systemctl suspend"), "Suspend the system to RAM.", external=True))
    actions.append(CliAction("Reboot", ("run-shell", "systemctl reboot"), "Reboot the system immediately.", external=True))
    actions.append(CliAction("Shutdown", ("run-shell", "systemctl poweroff"), "Power off the system immediately.", external=True))
    
    return tuple(actions)


def command_pages() -> tuple[CliPage, ...]:
    return (
        CliPage(
            "Dashboard",
            "Fiona system summary. Use left/right to slide pages.",
            (),
        ),
        CliPage(
            "Management",
            "System and project management tools.",
            (
                CliAction("System Monitor (btop)", ("btop",), "Launch the btop system monitor.", external=True),
                CliAction("Status dashboard", ("fat", "status", "--no-color"), "Show the text fAT status surface."),
                CliAction("Open editor", ("edit",), "Open the shared Fiona GUI editor.", external=True),
                CliAction("Host status", ("host", "status"), "Inspect host service config, keys, and checks."),
            ),
        ),
        CliPage(
            "Quick Actions",
            f"Session controls for {detect_de()}.",
            get_quick_actions(),
        ),
        CliPage(
            "QuikTieper",
            "Local keyboard/mouse/app access layer.",
            (
                CliAction("Open editor", ("edit",), "Open the shared Fiona GUI editor.", external=True),
                CliAction("List bindings", ("list",), "Print configured app launchers and shortcuts."),
                CliAction("Normalize commands", ("normalize-app-cmds",), "Standardize .desktop file launch strings."),
                CliAction("Assign keys", ("assign-keys",), "Auto-assign simultaneous chords to apps."),
                CliAction("Run listener", ("run",), "Start global keyboard listener in foreground.", external=True),
            ),
        ),
        CliPage(
            "CamComs",
            "Encrypted message transport and host receiver.",
            (
                CliAction("Smoke test", ("camcoms", "smoke-test"), "Run in-memory encrypt/decrypt validation."),
                CliAction("Key paths", ("camcoms", "paths"), "Print visible key/trust paths."),
                CliAction("Trusted senders", ("camcoms", "trust", "--list"), "List trusted sender public keys."),
                CliAction("Audit log", ("camcoms", "audit", "--limit", "20"), "Show recent receiver audit events."),
                CliAction("Receiver", ("camcoms", "receive"), "Start foreground CamComs receiver.", external=True),
            ),
        ),
        CliPage(
            "Host",
            "Unified host service lifecycle.",
            (
                CliAction("Init config", ("host", "init"), "Create default host config if missing."),
                CliAction("Status", ("host", "status", "--check-port"), "Run host readiness checks."),
                CliAction("Print service", ("host", "install-service", "--print"), "Preview user systemd unit."),
                CliAction("Logs", ("host", "logs", "--lines", "80"), "Show user service logs."),
                CliAction("Clear action trace", ("action", "clear"), "Delete the routed command history log."),
                CliAction("Run service", ("host", "run"), "Run host service in foreground.", external=True),
            ),
        ),
        CliPage(
            "Core",
            "Action routing, tracing, voice, macros, and RecallVault.",
            (
                CliAction("Action list", ("action", "list"), "List Fiona actions available through the router."),
                CliAction("Trace history", ("action", "history", "--limit", "20"), "Show recent routed command traces."),
                CliAction("Macro list", ("macro", "list"), "List saved Fiona action macros."),
                CliAction("Recall list", ("recall", "list"), "List saved RecallVault remembrance entries."),
                CliAction("Recall categories", ("recall", "categories"), "List unique categories in the vault."),
                CliAction("Clear RecallVault", ("recall", "clear"), "Delete all RecallVault remembrance entries."),
            ),
        ),
        CliPage(
            "Apps",
            "Standalone Fiona applications.",
            (
                CliAction("PhiConnect", ("phiconnect",), "Open encrypted chat GUI.", external=True),
                CliAction("DataClient", ("dataclient",), "Open research and MiniExcel GUI.", external=True),
                CliAction("Vsee", ("vsee",), "Open holography wireframe viewer.", external=True),
                CliAction("EyeControl status", ("eyecontrol", "status"), "Check optional camera tracker readiness."),
                CliAction("Agent status", ("agent", "status"), "Check LM Studio bridge status."),
            ),
        ),
        CliPage(
            "History",
            "Latest actions from the command trace.",
            tuple(
                CliAction(
                    f"{event.get('action', 'unknown')} ({event.get('source', 'local')})",
                    ("action", "history", "--limit", "1", "--name", str(event.get("action", ""))),
                    f"Result: {event.get('ok', False)} | Time: {event.get('elapsed_ms', 0)}ms",
                )
                for event in read_trace(limit=10)
            ),
        ),
        CliPage(
            "Recall",
            "Latest snippets from RecallVault.",
            tuple(
                CliAction(
                    entry.key,
                    ("recall", "search", entry.key),
                    f"[{entry.category}] {entry.value}",
                )
                for entry in search_recall()[-10:]
            ),
        ),
    )


def build_cli_preview(width: int = 96) -> str:
    pages = command_pages()
    rendered = [f"fAT / Fiona CLI │ {len(pages)} sliding pages │ width={width}", ""]
    for i, page in enumerate(pages):
        rendered.append(f"[{page.title}] - {page.subtitle}")
        for action in page.actions:
            ext = " ↗" if action.external else ""
            rendered.append(f"  • fiona {' '.join(action.command)}{ext}")
        rendered.append("")
    return "\n".join(rendered)


def run_terminal_cli(runner: Callable[[tuple[str, ...]], CommandResult] | None = None) -> int:
    if not sys.stdout.isatty():
        print(build_cli_preview())
        return 0
    return curses.wrapper(lambda screen: _run_curses(screen, runner=runner or _run_command))


def _run_curses(screen: curses.window, *, runner: Callable[[tuple[str, ...]], CommandResult]) -> int:
    curses.curs_set(0)
    curses.use_default_colors()
    screen.timeout(100)
    _init_colors()
    
    page_index = 0
    selected = 0
    query = ""
    message = "l/r: slide  u/d: select  /: search  v: voice  enter: run  q: quit"
    last_refresh = 0.0
    status = terminal_assist_status()

    while True:
        now = time.time()
        if now - last_refresh >= 1.0:
            status = terminal_assist_status()
            last_refresh = now
        
        mouse = get_mouse_info()
        status["mouse_x"] = mouse["x"]
        status["mouse_y"] = mouse["y"]
            
        pages = command_pages()
        if query:
            all_actions = []
            for p in pages:
                for a in p.actions:
                    if query.lower() in a.label.lower() or query.lower() in a.description.lower():
                        all_actions.append(a)
            display_page = CliPage("Search Results", f"Found {len(all_actions)} actions matching '{query}'", tuple(all_actions))
            selected = max(0, min(selected, len(display_page.actions) - 1))
            _draw(screen, pages=pages, page_index=-1, selected=selected, message=message, status=status, search_page=display_page, query=query)
            page = display_page
        else:
            page = pages[page_index]
            selected = max(0, min(selected, len(page.actions) - 1))
            _draw(screen, pages=pages, page_index=page_index, selected=selected, message=message, status=status)

        key = screen.getch()
        if key == -1: continue
        
        if key in (ord("q"), ord("Q"), 27):
            if query:
                query = ""
                selected = 0
                message = "Search cleared."
                continue
            return 0
        if key == ord("/"):
            query = ""
            selected = 0
            message = "Type to search actions... (Esc to cancel)"
            _draw(screen, pages=pages, page_index=-1, selected=0, message=message, status=status, query=query)
            curses.curs_set(1)
            query = _get_search_query(screen, height=screen.getmaxyx()[0] - 1, pages=pages, page_index=page_index, selected=selected, status=status)
            curses.curs_set(0)
            message = f"Search results for '{query}'" if query else "left/right: slide  up/down: select  /: search  enter: run  q: quit"
            continue
        if not query:
            if key in (curses.KEY_RIGHT, ord("l"), ord("L"), ord("\t")):
                page_index = (page_index + 1) % len(pages)
                selected = 0
                message = f"Slid to {pages[page_index].title}"
                continue
            if key in (curses.KEY_LEFT, ord("h"), ord("H")):
                page_index = (page_index - 1) % len(pages)
                selected = 0
                message = f"Slid to {pages[page_index].title}"
                continue
        if key in (curses.KEY_DOWN, ord("j"), ord("J")):
            if page.actions:
                selected = (selected + 1) % len(page.actions)
            continue
        if key in (curses.KEY_UP, ord("k"), ord("K")):
            if page.actions:
                selected = (selected - 1) % len(page.actions)
            continue
        if key in (ord("v"), ord("V")):
            message = "Voice: [LISTENING for 3s]..."
            _draw(screen, pages=pages, page_index=page_index, selected=selected, message=message, status=status)
            try:
                # One-shot 3s listen
                phrase = quick_transcribe(phrase_seconds=3.0)
                if phrase:
                    message = f"Voice: \"{phrase}\""
                    parsed = parse_voice_command(phrase)
                    if parsed:
                        message = f"Voice: {parsed.action} triggered."
                        _draw(screen, pages=pages, page_index=page_index, selected=selected, message=message, status=status)
                        ActionRouter().run(parsed.action, source="voice", permission_profile="local")
                        speak(f"Triggered {parsed.action}")
                    else:
                        message = f"Voice: Could not map \"{phrase}\""
                else:
                    message = "Voice: No speech detected."
            except Exception as e:
                message = f"Voice error: {e}"
            continue
        if key in (10, 13, curses.KEY_ENTER):
            if page.actions:
                action = page.actions[selected]
                _run_action(screen, action, runner)
                message = f"Loaded: fiona {' '.join(action.command)}"


def _get_search_query(screen: curses.window, height: int, *, pages: tuple[CliPage, ...], page_index: int, selected: int, status: dict[str, Any]) -> str:
    query = ""
    screen.timeout(100)
    last_refresh = time.time()
    
    while True:
        now = time.time()
        if now - last_refresh >= 1.0:
            _draw(screen, pages=pages, page_index=-1, selected=0, message="Type to search... (Esc to cancel)", query=query, status=status)
            last_refresh = now
            
        _safe_addstr(screen, height, 2, f"Search: {query}".ljust(screen.getmaxyx()[1] - 4), curses.color_pair(4) | curses.A_BOLD)
        screen.refresh()
        
        key = screen.getch()
        if key == -1:
            mouse = get_mouse_info()
            status["mouse_x"] = mouse["x"]
            status["mouse_y"] = mouse["y"]
            continue
        if key in (10, 13, curses.KEY_ENTER):
            return query
        if key in (27,):
            return ""
        if key in (curses.KEY_BACKSPACE, 127, 8):
            query = query[:-1]
        elif 32 <= key <= 126:
            query += chr(key)


def _draw(
    screen: curses.window,
    *,
    pages: tuple[CliPage, ...],
    page_index: int,
    selected: int,
    message: str,
    status: dict[str, Any],
    search_page: CliPage | None = None,
    query: str = "",
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    if height < 16 or width < 58:
        _safe_addstr(screen, 0, 0, "fAT needs a larger terminal.", curses.color_pair(4) | curses.A_BOLD)
        screen.refresh()
        return

    _draw_header(screen, width, page_index=page_index, pages=pages, query=query)
    
    if search_page:
        _draw_panel(screen, 3, 1, height - 6, width - 2, search_page, selected=selected, active=True)
    elif page_index == 0:
        dashboard_text = build_dashboard(color=False, width=width - 2, height=height - 3, status=status)
        lines = dashboard_text.splitlines()
        for i, line in enumerate(lines):
            attr = curses.color_pair(6)
            if i == 1 or i == 3 or i == 5 or i == len(lines)-1: attr = curses.color_pair(2)
            elif i == 0: attr = curses.color_pair(1) | curses.A_BOLD
            elif "──" in line: attr = curses.color_pair(6) | curses.A_BOLD
            if "█" in line or "░" in line: attr = curses.color_pair(3)
            _safe_addstr(screen, 1 + i, 1, line, attr)

        if height >= 42 and width >= 44:
            mm_w, mm_h = 40, 22
            mm_x = (width - mm_w) // 2
            mm_y = height - mm_h - 2
            mx, my = int(status.get("mouse_x", 0)), int(status.get("mouse_y", 0))
            
            # Map 1280x720 -> 40x22
            rel_x = int((mx / 1280) * (mm_w - 2))
            rel_y = int((my / 720) * (mm_h - 2))
            rel_x, rel_y = max(0, min(mm_w - 3, rel_x)), max(0, min(mm_h - 3, rel_y))
            
            _box(screen, mm_y, mm_x, mm_h, mm_w, curses.color_pair(2))
            _safe_addstr(screen, mm_y, mm_x + 2, " SPATIAL MINIMAP ", curses.color_pair(1) | curses.A_BOLD)
            _safe_addstr(screen, mm_y + 1 + rel_y, mm_x + 1 + rel_x, "+", curses.color_pair(4) | curses.A_BOLD)
            coords = f" {mx}, {my} "
            _safe_addstr(screen, mm_y + mm_h - 1, mm_x + mm_w - len(coords) - 2, coords, curses.color_pair(6))
    else:
        page = pages[page_index]
        next_page = pages[(page_index + 1) % len(pages)]
        main_width = max(36, int(width * 0.66))
        side_width = width - main_width - 3
        _draw_panel(screen, 3, 1, height - 6, main_width, page, selected=selected, active=True)
        _draw_panel(screen, 3, main_width + 2, height - 6, side_width, next_page, selected=-1, active=False)
    
    _draw_footer(screen, height, width, message)
    screen.refresh()


def _draw_output(
    screen: curses.window,
    *,
    action: CliAction,
    lines: tuple[str, ...],
    scroll: int,
    message: str,
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    _draw_header(screen, width, page_index=-1, pages=())
    
    out_h = height - 6
    _box(screen, 3, 1, out_h, width - 2, curses.color_pair(2))
    title = f" Output: fiona {' '.join(action.command)} "
    _safe_addstr(screen, 3, 3, title, curses.color_pair(1) | curses.A_BOLD)
    
    visible_lines = lines[scroll : scroll + out_h - 2]
    for i, line in enumerate(visible_lines):
        _safe_addstr(screen, 4 + i, 3, line, curses.color_pair(6))
        
    _draw_footer(screen, height, width, message)
    screen.refresh()


def _run_action(screen: curses.window, action: CliAction, runner: Callable[[tuple[str, ...]], CommandResult]) -> None:
    if not action.external:
        result = runner(action.command)
        _show_command_output(screen, action, result)
        return
    
    curses.def_shell_mode()
    screen.clear()
    screen.refresh()
    _run_command_external(action.command)
    screen.clear()
    curses.reset_shell_mode()
    screen.refresh()


def _run_command(command: tuple[str, ...]) -> CommandResult:
    completed = subprocess.run(
        [sys.executable, "-m", "fiona.cli", *command],
        check=False,
        text=True,
        capture_output=True,
    )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _run_command_external(command: tuple[str, ...]) -> int:
    from FionaCore.shell_safety import safe_os_system, ShellCommandError
    cmd_str = f"'{sys.executable}' -m fiona.cli {' '.join(command)}"
    try:
        return safe_os_system(cmd_str)
    except ShellCommandError as e:
        print(f"Command blocked: {e}", file=sys.stderr)
        return 127


def format_command_output(result: CommandResult) -> tuple[str, ...]:
    lines = [f"$ fiona {' '.join(result.command)}", f"[exit {result.returncode}]", ""]
    if result.stdout.strip():
        lines.extend(result.stdout.splitlines())
    if result.stderr.strip():
        lines.append("")
        lines.append("[stderr]")
        lines.extend(result.stderr.splitlines())
    return tuple(lines)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _init_colors() -> None:
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_BLUE, -1)
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)
    curses.init_pair(5, curses.COLOR_RED, -1)
    curses.init_pair(6, curses.COLOR_WHITE, -1)


def _draw_header(screen: curses.window, width: int, *, page_index: int, pages: tuple[CliPage, ...], query: str = "") -> None:
    title = " fAT / Fiona CLI "
    if query:
        title = f" fAT Search: {query} "
    _safe_addstr(screen, 0, 0, "━" * width, curses.color_pair(2))
    _safe_addstr(screen, 0, max(0, (width - len(title)) // 2), title, curses.color_pair(1) | curses.A_BOLD)
    if not query and pages:
        tabs = "  ".join(f"{'●' if i == page_index else '○'} {page.title}" for i, page in enumerate(pages))
        _safe_addstr(screen, 1, 2, tabs[: width - 4], curses.color_pair(6))


def _draw_panel(
    screen: curses.window,
    y: int,
    x: int,
    height: int,
    width: int,
    page: CliPage,
    *,
    selected: int,
    active: bool,
) -> None:
    attr = curses.color_pair(2) if active else curses.color_pair(2) | curses.A_DIM
    _box(screen, y, x, height, width, attr)
    
    title = f" {page.title} "
    _safe_addstr(screen, y, x + 2, title, curses.color_pair(1) | (curses.A_BOLD if active else curses.A_DIM))
    
    _safe_addstr(screen, y + 1, x + 2, page.subtitle[: width - 4], curses.color_pair(6) | curses.A_DIM)
    
    for i, action in enumerate(page.actions):
        row_y = y + 3 + i
        if row_y >= y + height - 1:
            break
        
        prefix = " > " if i == selected and active else "   "
        row_attr = curses.color_pair(3) if i == selected and active else curses.color_pair(6)
        if not active:
            row_attr |= curses.A_DIM
            
        ext = " ↗" if action.external else ""
        label = f"{prefix}{action.label}{ext}"
        _safe_addstr(screen, row_y, x + 1, label[: width - 2], row_attr | (curses.A_BOLD if i == selected and active else 0))


def _draw_footer(screen: curses.window, height: int, width: int, message: str) -> None:
    _safe_addstr(screen, height - 2, 0, "━" * width, curses.color_pair(2))
    _safe_addstr(screen, height - 1, 2, message[: width - 4], curses.color_pair(4))


def _show_command_output(screen: curses.window, action: CliAction, result: CommandResult) -> None:
    lines = format_command_output(result)
    scroll = 0
    message = "up/down: scroll  page up/down: jump  q/esc/backspace/enter: return"
    screen.timeout(1000)
    
    while True:
        _draw_output(screen, action=action, lines=lines, scroll=scroll, message=message)
        key = screen.getch()
        if key == -1: continue
        if key in (ord("q"), ord("Q"), 27, 10, 13, curses.KEY_ENTER, curses.KEY_BACKSPACE, 127, 8):
            screen.clear()
            return
        h, _ = screen.getmaxyx()
        page_size = max(1, h - 8)
        max_scroll = max(0, len(lines) - page_size)
        if key in (curses.KEY_DOWN, ord("j"), ord("J")):
            scroll = min(max_scroll, scroll + 1)
        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            scroll = max(0, scroll - 1)
        elif key in (curses.KEY_NPAGE, ord(" ")):
            scroll = min(max_scroll, scroll + page_size)
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - page_size)


def _box(screen: curses.window, y: int, x: int, height: int, width: int, attr: int) -> None:
    screen.attron(attr)
    try:
        screen.addstr(y, x, "┏" + "━" * (width - 2) + "┓")
        for row in range(y + 1, y + height - 1):
            screen.addstr(row, x, "┃")
            screen.addstr(row, x + width - 1, "┃")
        screen.addstr(y + height - 1, x, "┗" + "━" * (width - 2) + "┛")
    finally:
        screen.attroff(attr)


def _safe_addstr(screen: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = screen.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    clipped = text[: max(0, width - x - 1)]
    if clipped:
        screen.addstr(y, max(0, x), clipped, attr)
