#!/usr/bin/env python3
"""Run the Bridge web-client compilation smoke against a registered test database."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT.parent


class WebSmokeError(RuntimeError):
    pass


def load_registry(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as source:
        root = json.load(source)
    databases = root.get("databases") if isinstance(root, dict) else None
    if not isinstance(databases, list):
        raise WebSmokeError("Registry must contain a databases array")
    return [item for item in databases if isinstance(item, dict)]


def database_aliases(database: dict[str, Any]) -> set[str]:
    bridge = database.get("Bridge") if isinstance(database.get("Bridge"), dict) else {}
    project_name = Path(str(database.get("path", ""))).name
    return {
        str(database.get("Ref", "")).casefold(),
        project_name.casefold(),
        str(bridge.get("AppName", "")).casefold(),
    } - {""}


def select_database(databases: list[dict[str, Any]], requested: str) -> dict[str, Any]:
    matches = [database for database in databases if requested.casefold() in database_aliases(database)]
    if len(matches) != 1:
        raise WebSmokeError("Database selection must match exactly one registered test database")
    return matches[0]


def registered_web_url(database: dict[str, Any]) -> str:
    bridge = database.get("Bridge") if isinstance(database.get("Bridge"), dict) else {}
    explicit = bridge.get("WebUrl")
    if isinstance(explicit, str) and explicit:
        return explicit.rstrip("/")
    base_url = bridge.get("BaseUrl")
    suffix = "/hs/codex-test"
    if not isinstance(base_url, str) or not base_url.rstrip("/").endswith(suffix):
        raise WebSmokeError("Registered Bridge.BaseUrl cannot be mapped to its web publication")
    return base_url.rstrip("/")[: -len(suffix)]


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Bridge startup in the 1C web client")
    parser.add_argument("--registry", required=True, help="Path returned by test-databases resolver")
    parser.add_argument("--database", required=True, help="Registered Ref, project name, or Bridge.AppName")
    parser.add_argument("--node", default="node", help="Node.js executable")
    parser.add_argument("--browser", default="", help="Optional Chromium/Chrome executable")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        database = select_database(load_registry(Path(args.registry).resolve()), args.database)
        username = database.get("User")
        if not isinstance(username, str) or not username:
            raise WebSmokeError("Registered test database has no User")
        password = database.get("Password", "")
        if not isinstance(password, str):
            raise WebSmokeError("Registered test database Password must be a string")
        runner = SKILLS_ROOT / "ui-testing" / "scripts" / "web-run.mjs"
        scenario = ROOT / "examples" / "web-client-compile-smoke.js"
        if not runner.is_file() or not scenario.is_file():
            raise WebSmokeError("ui-testing runner or web smoke scenario is missing")

        environment = os.environ.copy()
        environment["CODEX_1C_USERNAME"] = username
        environment["CODEX_1C_PASSWORD"] = password
        if args.browser:
            environment["PLAYWRIGHT_EXECUTABLE_PATH"] = str(Path(args.browser).resolve())
        completed = subprocess.run(
            [args.node, str(runner), "run", registered_web_url(database), str(scenario)],
            cwd=SKILLS_ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
        )
        return completed.returncode
    except (OSError, ValueError, WebSmokeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
