from __future__ import annotations

import curses
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from typing import Callable

from .dashboard import terminal_assist_status

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class CliAction:
    label: str
    command: tuple[str, ...]
    description: str
    external: bool = False


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CliPage:
    title: str
    subtitle: str
    actions: tuple[CliAction, ...]


def command_pages() -> tuple[CliPage, ...]:
    return (
        CliPage(
            "Overview",
            "Fiona command center. Use left/right to slide pages, enter to run.",
            (
                CliAction(
                    "Status dashboard",
                    ("fat", "status", "--no-color"),
                    "Show the btop-style fAT status surface.",
                ),
                CliAction("Host status", ("host", "status"), "Inspect host service config, keys, and checks."),
                CliAction("CamComs paths", ("camcoms", "paths"), "Show encryption key/trust locations."),
                CliAction("SeeOnDesk status", ("seeondesk", "status"), "Show current desktop-awareness snapshot."),
            ),
        ),
        CliPage(
            "QuikTieper",
            "Local keyboard/mouse/app access layer.",
            (
                CliAction("Open editor", ("edit",), "Open the shared Fiona GUI editor.", external=True),
                CliAction("List bindings", ("list",), "Print configured app launchers and shortcuts."),
                CliAction("Import apps dry-run", ("import-apps", "--dry-run"), "Preview Linux desktop app import."),
                CliAction("Assign keys dry-run", ("assign-keys", "--dry-run"), "Preview generated launch chords."),
                CliAction("Run listener", ("run",), "Start the foreground global chord listener.", external=True),
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
                CliAction("Run service", ("host", "run"), "Run host service in foreground.", external=True),
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
    )


def build_cli_preview(width: int = 96) -> str:
    pages = command_pages()
    status = terminal_assist_status()
    lines = [
        "fAT / Fiona CLI",
        "=" * min(width, 96),
        f"Zellij: {status['zellij_path'] or 'not found'}",
        f"Ready: {'yes' if status['ready'] else 'partial'}",
        "",
    ]
    for page in pages:
        lines.append(f"[{page.title}] {page.subtitle}")
        for index, action in enumerate(page.actions, 1):
            lines.append(f"  {index}. {action.label}: fiona {' '.join(action.command)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def run_terminal_cli(*, runner: Callable[[tuple[str, ...]], CommandResult] | None = None) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(build_cli_preview())
        return 0
    return curses.wrapper(lambda screen: _run_curses(screen, runner=runner or _run_command))


def _run_curses(screen: curses.window, *, runner: Callable[[tuple[str, ...]], CommandResult]) -> int:
    curses.curs_set(0)
    curses.use_default_colors()
    _init_colors()
    pages = command_pages()
    page_index = 0
    selected = 0
    message = "left/right: slide  up/down: select  enter: run  q: quit"

    while True:
        page = pages[page_index]
        selected = max(0, min(selected, len(page.actions) - 1))
        _draw(screen, pages=pages, page_index=page_index, selected=selected, message=message)
        key = screen.getch()
        if key in (ord("q"), ord("Q"), 27):
            return 0
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
            selected = (selected + 1) % len(page.actions)
            continue
        if key in (curses.KEY_UP, ord("k"), ord("K")):
            selected = (selected - 1) % len(page.actions)
            continue
        if key in (10, 13, curses.KEY_ENTER):
            action = page.actions[selected]
            _run_action(screen, action, runner)
            message = f"Loaded: fiona {' '.join(action.command)}"


def _run_action(screen: curses.window, action: CliAction, runner: Callable[[tuple[str, ...]], CommandResult]) -> None:
    if not action.external:
        result = runner(action.command)
        _show_command_output(screen, action, result)
        return

    curses.def_prog_mode()
    curses.endwin()
    try:
        print(f"\n$ fiona {' '.join(action.command)}\n")
        code = _run_command_external(action.command)
        print(f"\n[exit {code}] Press Enter to return to fAT.", end="", flush=True)
        input()
    finally:
        curses.reset_prog_mode()
        curses.curs_set(0)
        screen.clear()


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
    return subprocess.call([sys.executable, "-m", "fiona.cli", *command])


def format_command_output(result: CommandResult) -> tuple[str, ...]:
    lines = [f"$ fiona {' '.join(result.command)}", f"[exit {result.returncode}]", ""]
    if result.stdout.strip():
        lines.extend(strip_ansi(result.stdout.rstrip()).splitlines())
    if result.stderr.strip():
        if result.stdout.strip():
            lines.append("")
        lines.append("[stderr]")
        lines.extend(strip_ansi(result.stderr.rstrip()).splitlines())
    if len(lines) == 3:
        lines.append("(no output)")
    return tuple(lines)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _show_command_output(screen: curses.window, action: CliAction, result: CommandResult) -> None:
    lines = format_command_output(result)
    scroll = 0
    message = "up/down: scroll  page up/down: jump  q/esc/backspace/enter: return"
    while True:
        _draw_output(screen, action=action, lines=lines, scroll=scroll, message=message)
        key = screen.getch()
        if key in (ord("q"), ord("Q"), 27, 10, 13, curses.KEY_ENTER, curses.KEY_BACKSPACE, 127, 8):
            screen.clear()
            return
        height, _width = screen.getmaxyx()
        page_size = max(1, height - 8)
        max_scroll = max(0, len(lines) - page_size)
        if key in (curses.KEY_DOWN, ord("j"), ord("J")):
            scroll = min(max_scroll, scroll + 1)
        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            scroll = max(0, scroll - 1)
        elif key in (curses.KEY_NPAGE, ord(" ")):
            scroll = min(max_scroll, scroll + page_size)
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - page_size)


def _init_colors() -> None:
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_BLUE, -1)
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)
    curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(6, curses.COLOR_WHITE, -1)


def _draw(
    screen: curses.window,
    *,
    pages: tuple[CliPage, ...],
    page_index: int,
    selected: int,
    message: str,
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    if height < 16 or width < 58:
        _safe_addstr(screen, 0, 0, "fAT needs a larger terminal.", curses.color_pair(4) | curses.A_BOLD)
        screen.refresh()
        return

    _draw_header(screen, width, page_index=page_index, pages=pages)
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
    if height < 12 or width < 58:
        _safe_addstr(screen, 0, 0, "fAT output needs a larger terminal.", curses.color_pair(4) | curses.A_BOLD)
        screen.refresh()
        return

    title = f" fAT output / {action.label} "
    _safe_addstr(screen, 0, 0, "━" * width, curses.color_pair(2))
    _safe_addstr(screen, 0, max(0, (width - len(title)) // 2), title, curses.color_pair(1) | curses.A_BOLD)
    panel_y = 2
    panel_x = 1
    panel_h = height - 5
    panel_w = width - 2
    _box(screen, panel_y, panel_x, panel_h, panel_w, curses.color_pair(1))
    visible_h = max(1, panel_h - 2)
    visible_lines = lines[scroll : scroll + visible_h]
    for index, line in enumerate(visible_lines):
        attr = curses.color_pair(3) if index + scroll < 2 else curses.color_pair(6)
        _safe_addstr(screen, panel_y + 1 + index, panel_x + 2, line[: panel_w - 4], attr)
    position = f"{min(len(lines), scroll + visible_h)}/{len(lines)}"
    _safe_addstr(screen, height - 2, 0, "━" * width, curses.color_pair(2))
    _safe_addstr(screen, height - 1, 2, f"{message}  {position}"[: width - 4], curses.color_pair(1))
    screen.refresh()


def _draw_header(screen: curses.window, width: int, *, page_index: int, pages: tuple[CliPage, ...]) -> None:
    title = " fAT / Fiona CLI "
    _safe_addstr(screen, 0, 0, "━" * width, curses.color_pair(2))
    _safe_addstr(screen, 0, max(0, (width - len(title)) // 2), title, curses.color_pair(1) | curses.A_BOLD)
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
    border_color = curses.color_pair(1 if active else 2)
    _box(screen, y, x, height, width, border_color)
    title_attr = curses.color_pair(3 if active else 2) | curses.A_BOLD
    _safe_addstr(screen, y, x + 2, f" {page.title} ", title_attr)
    for offset, line in enumerate(textwrap.wrap(page.subtitle, max(10, width - 4))[:2]):
        _safe_addstr(screen, y + 2 + offset, x + 2, line, curses.color_pair(6 if active else 2))
    start_y = y + 5
    for index, action in enumerate(page.actions[: max(0, height - 7)]):
        row_y = start_y + index
        prefix = "▶" if index == selected else " "
        mode = " ↗" if action.external else ""
        label = f"{prefix} {index + 1}. {action.label}{mode}"
        attr = curses.color_pair(5) | curses.A_BOLD if index == selected else curses.color_pair(6 if active else 2)
        _safe_addstr(screen, row_y, x + 2, label[: width - 4].ljust(width - 4), attr)
    detail_y = y + height - 3
    if active and 0 <= selected < len(page.actions):
        detail = page.actions[selected].description
        _safe_addstr(screen, detail_y, x + 2, detail[: width - 4], curses.color_pair(4))


def _draw_footer(screen: curses.window, height: int, width: int, message: str) -> None:
    _safe_addstr(screen, height - 2, 0, "━" * width, curses.color_pair(2))
    _safe_addstr(screen, height - 1, 2, message[: width - 4], curses.color_pair(1))


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
