from __future__ import annotations

import argparse
from pathlib import Path

from quiktieper.config import DEFAULT_CONFIG_PATH, ensure_config, load_config
from quiktieper.launcher import Binding


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quiktieper",
        description="Launch apps using simultaneous key chords.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the bindings JSON file.",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("init", help="Create the default config if it does not exist.")
    subparsers.add_parser("list", help="List configured app chords.")
    subparsers.add_parser("edit", help="Open the GUI config editor.")
    subparsers.add_parser("run", help="Start the global listener.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    command = args.command or "run"
    if command == "init":
        config_path = ensure_config(args.config)
        print(f"Config ready at {config_path}")
        return

    config = load_config(args.config)
    bindings = [
        Binding(
            name=item["name"],
            keys=frozenset(key.lower() for key in item["keys"]),
            command=item.get("cmd") or item["command"],
            cooldown_seconds=float(item.get("cooldown_seconds", 0.8)),
        )
        for item in config.get("bindings", [])
    ]

    if command == "list":
        for binding in bindings:
            chord = " + ".join(sorted(binding.keys))
            print(f"{binding.name}: {chord} -> {binding.command}")
        return

    if command == "edit":
        from quiktieper.gui import launch_editor

        launch_editor(args.config)
        return

    from quiktieper.listener import ChordListener

    print(f"Listening for {len(bindings)} app chords from {args.config}")
    ChordListener(bindings).run()


if __name__ == "__main__":
    main()
