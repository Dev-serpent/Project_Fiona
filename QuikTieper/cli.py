from __future__ import annotations

import argparse
import os
from pathlib import Path

from QuikTieper.bindings import parse_bindings
from QuikTieper.app_command_presets import apply_app_command_presets
from QuikTieper.config import DEFAULT_CONFIG_PATH, ensure_config, load_config, save_config
from QuikTieper.desktop_apps import discover_desktop_apps, merge_desktop_apps
from QuikTieper.key_assignment import assign_missing_launch_keys
from QuikTieper.launcher import ensure_ydotoold_running


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fiona",
        description="Launch apps and focused-app shortcuts using simultaneous key chords.",
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
    assign_keys = subparsers.add_parser("assign-keys", help="Assign generated launch chords to apps missing keys.")
    assign_keys.add_argument("--dry-run", action="store_true", help="Show how many launch keys would be assigned.")
    assign_keys.add_argument(
        "--reassign",
        action="store_true",
        help="Regenerate launch keys for imported apps while preserving the default hand-written apps.",
    )
    import_apps = subparsers.add_parser("import-apps", help="Import installed desktop applications into the config.")
    import_apps.add_argument("--dry-run", action="store_true", help="Show how many apps would be added without saving.")
    import_apps.add_argument(
        "--include-all-k-apps",
        action="store_true",
        help="Include all apps whose names start with K instead of keeping only the curated K-app allowlist.",
    )
    import_apps.add_argument(
        "--include-low-value-apps",
        action="store_true",
        help="Include games, education apps, settings panels, helpers, and other entries normally filtered out.",
    )
    normalize_apps = subparsers.add_parser(
        "normalize-app-cmds",
        help="Apply Fiona's curated app command presets to configured app launchers.",
    )
    normalize_apps.add_argument("--dry-run", action="store_true", help="Show command changes without saving.")
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
    if command == "import-apps":
        desktop_apps = discover_desktop_apps(
            skip_unapproved_k_apps=not args.include_all_k_apps,
            skip_low_value_apps=not args.include_low_value_apps,
        )
        merged, added = merge_desktop_apps(config, desktop_apps)
        if args.dry_run:
            print(f"Discovered {len(desktop_apps)} desktop apps; would add {added} new app entries to {args.config}")
            return
        save_config(merged, args.config)
        print(f"Imported {added} desktop apps into {args.config}")
        print("Imported apps have no launch keys by default; assign chords in the GUI before using the listener.")
        return

    if command == "assign-keys":
        assigned, changed = assign_missing_launch_keys(config, reassign=args.reassign)
        if args.dry_run:
            action = "reassign" if args.reassign else "assign"
            print(f"Would {action} launch keys for {changed} app entries in {args.config}")
            return
        save_config(assigned, args.config)
        action = "Reassigned" if args.reassign else "Assigned"
        print(f"{action} launch keys for {changed} app entries in {args.config}")
        return

    if command == "normalize-app-cmds":
        normalized, changes, added, assigned_keys = apply_app_command_presets(config)
        if args.dry_run:
            print(
                f"Would apply {len(changes)} app command changes, add {added} missing app entries, "
                f"and assign launch keys to {assigned_keys} app entries in {args.config}"
            )
            for change in changes:
                old = change["old"] or "<missing>"
                print(f"{change['app']}: {old} -> {change['new']}")
            return
        save_config(normalized, args.config)
        print(
            f"Applied {len(changes)} app command changes, added {added} missing app entries, "
            f"and assigned launch keys to {assigned_keys} app entries in {args.config}"
        )
        return

    bindings = parse_bindings(config.get("apps", []))

    # On Wayland, bootstrap ydotoold up front so auth happens at app start
    # instead of during the first click action.
    if os.environ.get("WAYLAND_DISPLAY"):
        ensure_ydotoold_running()

    if command == "list":
        for app in config.get("apps", []):
            launch = app["launch"]
            launch_keys = " + ".join(sorted(key.lower() for key in launch.get("keys", [])))
            print(f"{app['name']} launch: {launch_keys or 'unassigned'} -> {launch.get('cmd', '')}")
            for shortcut in app.get("shortcuts", []):
                shortcut_keys = " + ".join(sorted(key.lower() for key in shortcut.get("keys", [])))
                print(f"{app['name']} shortcut {shortcut['name']}: {shortcut_keys or 'unassigned'} -> {shortcut.get('cmd', '')}")
        return

    if command == "edit":
        from QuikTieper.gui import launch_editor

        launch_editor(args.config)
        return

    from QuikTieper.listener import ChordListener

    print(f"Listening for {len(bindings)} launch and shortcut chords from {args.config}")
    ChordListener(bindings).run()


if __name__ == "__main__":
    main()
