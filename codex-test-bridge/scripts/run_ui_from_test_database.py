#!/usr/bin/env python3
"""Run native 1C UI tests using an existing user from the private database registry."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui_batch import run_ui_batch  # noqa: E402
from ui_worker import load_worker_config, run_ui_worker  # noqa: E402


REQUIRED_FIELDS = ("Srvr", "Ref", "User", "Password")


def select_database(registry: dict, selector: str) -> dict:
    wanted = selector.casefold()
    matches = []
    for database in registry.get("databases", []):
        bridge = database.get("Bridge") or {}
        candidates = {
            str(database.get("Ref", "")).casefold(),
            Path(str(database.get("path", ""))).name.casefold(),
            str(bridge.get("AppName", "")).casefold(),
        }
        if wanted in candidates:
            matches.append(database)
    if not matches:
        raise ValueError(f"Test database was not found: {selector}")
    if len(matches) != 1:
        raise ValueError(f"Test database selector is ambiguous: {selector}")
    database = matches[0]
    missing = [name for name in REQUIRED_FIELDS if name not in database]
    bridge = database.get("Bridge") or {}
    if not bridge.get("BaseUrl"):
        missing.append("Bridge.BaseUrl")
    if missing:
        raise ValueError("Test database entry is incomplete: " + ", ".join(missing))
    return database


@contextmanager
def temporary_environment(values: dict[str, str]):
    previous = {name: os.environ.get(name) for name in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run UI tests with an existing user from private test-databases.json"
    )
    parser.add_argument("--registry", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument(
        "--worker-config",
        default=str(ROOT / "ui-worker.cross-db.credentials.example.json"),
    )
    parser.add_argument("--scenario", action="append", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    registry = json.loads(Path(args.registry).read_text(encoding="utf-8-sig"))
    database = select_database(registry, args.database)
    connection = f"{database['Srvr']}\\{database['Ref']}"
    bridge_url = str(database["Bridge"]["BaseUrl"])
    environment = {
        "CODEX_1C_EXECUTABLE": str(Path(args.platform).resolve()),
        "CODEX_1C_CLIENT_SERVER_CONNECTION": connection,
        "CODEX_1C_MANAGER_SERVER_CONNECTION": connection,
        "CODEX_1C_MANAGER_BRIDGE_URL": bridge_url,
        "CODEX_1C_CLIENT_USERNAME": str(database["User"]),
        "CODEX_1C_MANAGER_USERNAME": str(database["User"]),
        "CODEX_1C_CLIENT_PASSWORD": str(database["Password"]),
        "CODEX_1C_MANAGER_PASSWORD": str(database["Password"]),
    }

    with temporary_environment(environment):
        worker_config = load_worker_config(args.worker_config)
        if len(args.scenario) == 1:
            report = run_ui_worker(worker_config, args.scenario[0], args.artifact_dir)
        else:
            report = run_ui_batch(worker_config, args.scenario, args.artifact_dir)

    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
