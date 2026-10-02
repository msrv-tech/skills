#!/usr/bin/env python3
"""Install the fixture CFE into one explicitly selected registered test database."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_ROOT = ROOT.parent / "codex-test-bridge"
sys.path.insert(0, str(BRIDGE_ROOT / "scripts"))

from run_ui_from_test_database import select_database  # noqa: E402
from update_all_test_databases import request_bridge, sanitized_process_error  # noqa: E402


class FixtureInstallError(RuntimeError):
    pass


def verify_fixture(database: dict, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = request_bridge(
                database,
                "POST",
                "/command",
                {"command": "metadata", "sections": ["catalogs", "documents"]},
            )
            catalogs = {item.get("name") for item in result.get("catalogs", [])}
            documents = {item.get("name") for item in result.get("documents", [])}
            if "CodexUIFixtureCatalog" in catalogs and "CodexUIFixtureDocument" in documents:
                return
            last_error = FixtureInstallError("fixture metadata is not visible through Bridge")
        except Exception as exc:
            last_error = exc
        time.sleep(2)
    raise FixtureInstallError("fixture verification timed out") from last_error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Codex UI fixtures into one registered test database")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--cfe", default=str(ROOT / "codex-ui-test-fixtures.cfe"))
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args(argv)

    registry = json.loads(Path(args.registry).read_text(encoding="utf-8-sig"))
    database = select_database(registry, args.database)
    cfe = Path(args.cfe).resolve()
    if not cfe.is_file() or cfe.stat().st_size == 0:
        raise FixtureInstallError("fixture CFE does not exist or is empty")
    password_environment = "CODEX_CTF_REGISTERED_USER_PASSWORD"
    environment = os.environ.copy()
    environment[password_environment] = str(database.get("Password", ""))
    with tempfile.TemporaryDirectory(prefix="ctf-registered-user-update-") as temporary:
        log_path = Path(temporary) / "designer.log"
        command = [
            sys.executable,
            str(BRIDGE_ROOT / "scripts" / "install_cfe_designer_hidden.py"),
            "--platform", str(Path(args.platform).resolve()),
            "--server", str(database["Srvr"]),
            "--database", str(database["Ref"]),
            "--user", str(database["User"]),
            "--password-env", password_environment,
            "--extension", "CodexUITestFixtures",
            "--cfe", str(cfe),
            "--log", str(log_path),
            "--timeout", str(args.timeout),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=args.timeout + 60,
        )
        if completed.returncode != 0:
            raise FixtureInstallError(sanitized_process_error(completed, database))
    verify_fixture(database, min(args.timeout, 120))
    print("CodexUITestFixtures installed and verified in the selected registered test database")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
