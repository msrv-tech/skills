#!/usr/bin/env python3
"""Update CodexTestBridge in every server infobase from a private JSON registry."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPATIBILITY_PATTERN = re.compile(r"Version8_3_(\d+)$", re.IGNORECASE)


class UpdateError(RuntimeError):
    pass


def load_registry(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig") as source:
        root = json.load(source)
    databases = root.get("databases") if isinstance(root, dict) else None
    if not isinstance(databases, list) or not databases:
        raise UpdateError("Registry must contain a non-empty databases array")
    if any(not isinstance(database, dict) for database in databases):
        raise UpdateError("Every registry database entry must be a JSON object")
    return databases


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_compatibility_mode(database: dict[str, Any]) -> str:
    explicit = database.get("BridgeCompatibilityMode")
    if isinstance(explicit, str) and explicit:
        return explicit
    project_path = database.get("path")
    if not isinstance(project_path, str) or not project_path:
        raise UpdateError("Database entry has no project path for compatibility detection")
    project = Path(project_path)
    candidates = (
        project / "xml" / "Configuration.xml",
        project / "src" / "Configuration.xml",
        project / "Configuration.xml",
    )
    configuration = next((candidate for candidate in candidates if candidate.is_file()), None)
    if configuration is None:
        raise UpdateError("Configuration.xml was not found; set BridgeCompatibilityMode in the private registry")
    try:
        root = ET.parse(configuration).getroot()
    except (ET.ParseError, OSError) as exc:
        raise UpdateError("Configuration.xml cannot be read") from exc
    for element in root.iter():
        if local_name(element.tag) == "CompatibilityMode" and element.text:
            return element.text.strip()
    raise UpdateError("CompatibilityMode was not found in Configuration.xml")


def cfe_variant(compatibility_mode: str) -> str:
    normalized = compatibility_mode.strip()
    if normalized.lower() in {"dontuse", "notuse", ""}:
        return "full"
    match = COMPATIBILITY_PATTERN.fullmatch(normalized)
    if not match:
        raise UpdateError("Unsupported compatibility mode value")
    return "full" if int(match.group(1)) >= 12 else "legacy"


def bridge_url(database: dict[str, Any]) -> str:
    bridge = database.get("Bridge")
    value = bridge.get("BaseUrl") if isinstance(bridge, dict) else None
    if not isinstance(value, str) or not value:
        raise UpdateError("Database entry has no Bridge.BaseUrl")
    return value.rstrip("/")


def request_bridge(database: dict[str, Any], method: str, suffix: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    username = database.get("User", "")
    password = database.get("Password", "")
    if username:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=True).encode("ascii")
    request = urllib.request.Request(bridge_url(database) + suffix, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
    )
    with opener.open(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8-sig"))
    if not isinstance(result, dict):
        raise UpdateError("Bridge returned a non-object JSON response")
    return result


def verify_bridge(database: dict[str, Any], timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            get_result = request_bridge(database, "GET", "/health")
            post_result = request_bridge(database, "POST", "/command", {"command": "health"})
            if get_result.get("ok", True) and post_result.get("ok", True):
                return
            last_error = UpdateError("Bridge health response is not successful")
        except Exception as exc:  # publication can restart briefly after CFE update
            last_error = exc
        time.sleep(2)
    raise UpdateError("Bridge health verification timed out") from last_error


def count_bootstrap_users(database: dict[str, Any]) -> int:
    code = (
        'n=0;For Each x In InfoBaseUsers.GetUsers() Do '
        'If Left(x.Name,14)="ctb_bootstrap_" Then n=n+1;EndIf;EndDo;'
        'РезультатВыполнения=n;'
    )
    result = request_bridge(database, "POST", "/command", {"command": "ExecuteBSL", "code": code, "params": []})
    value = result.get("result")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UpdateError("Cannot audit temporary bootstrap users")
    return int(value)


def assert_no_bootstrap_users(database: dict[str, Any]) -> None:
    if count_bootstrap_users(database) != 0:
        raise UpdateError("Temporary bootstrap users exist; stop concurrent installers and clean them explicitly")


def validate_install_fields(database: dict[str, Any]) -> None:
    for field in ("Srvr", "Ref"):
        if not isinstance(database.get(field), str) or not database[field]:
            raise UpdateError(f"Database entry has no {field}; only server infobases are supported")


def install_database(
    database: dict[str, Any], platform: Path, cfe: Path, timeout: float,
) -> None:
    validate_install_fields(database)
    password_environment = "CODEX_CTB_MASS_UPDATE_PASSWORD"
    environment = os.environ.copy()
    environment[password_environment] = str(database.get("Password", ""))
    with tempfile.TemporaryDirectory(prefix="ctb-mass-update-") as temporary:
        log_path = Path(temporary) / "designer.log"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "install_cfe_with_bridge_bootstrap.py"),
            "--allow-bootstrap-user",
            "--bridge-base-url", bridge_url(database),
            "--bridge-user", str(database.get("User", "")),
            "--bridge-password-env", password_environment,
            "--platform", str(platform),
            "--server", database["Srvr"],
            "--database", database["Ref"],
            "--cfe", str(cfe),
            "--log", str(log_path),
            "--timeout", str(timeout),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout + 60,
        )
        if completed.returncode != 0:
            raise UpdateError("Hidden CFE installation failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update CodexTestBridge in all test databases from a private registry")
    parser.add_argument("--registry", default=os.environ.get("CODEX_1C_TEST_DATABASES", ""), help="Private test-databases JSON path")
    parser.add_argument("--platform", default=os.environ.get("CODEX_1C_EXECUTABLE", ""), help="1cv8 executable used by hidden Designer")
    parser.add_argument("--full-cfe", default=str(ROOT / "codex-test-bridge.cfe"))
    parser.add_argument("--legacy-cfe", default=str(ROOT / "codex-test-bridge-legacy.cfe"))
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--install-attempts", type=int, default=3, help="Retries for transient Designer or publication failures")
    parser.add_argument("--dry-run", action="store_true", help="Detect variants without modifying infobases")
    parser.add_argument("--allow-bootstrap-user", action="store_true", required=True)
    args = parser.parse_args(argv)
    if not args.registry:
        parser.error("--registry or CODEX_1C_TEST_DATABASES is required")
    if not args.platform and not args.dry_run:
        parser.error("--platform or CODEX_1C_EXECUTABLE is required")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    if args.install_attempts < 1 or args.install_attempts > 10:
        parser.error("--install-attempts must be between 1 and 10")

    databases = load_registry(args.registry)
    cfe_files = {"full": Path(args.full_cfe).resolve(), "legacy": Path(args.legacy_cfe).resolve()}
    if not args.dry_run:
        for variant, cfe in cfe_files.items():
            if not cfe.is_file():
                raise UpdateError(f"{variant} CFE file does not exist")

    failures = 0
    totals = {"full": 0, "legacy": 0}
    for index, database in enumerate(databases, 1):
        label = f"database {index}/{len(databases)}"
        try:
            mode = read_compatibility_mode(database)
            variant = cfe_variant(mode)
            totals[variant] += 1
            print(f"[{label}] compatibility={mode}, variant={variant}", flush=True)
            if args.dry_run:
                continue
            assert_no_bootstrap_users(database)
            for attempt in range(1, args.install_attempts + 1):
                print(f"[{label}] installing, attempt {attempt}/{args.install_attempts}", flush=True)
                try:
                    install_database(database, Path(args.platform).resolve(), cfe_files[variant], args.timeout)
                    break
                except Exception:
                    if attempt >= args.install_attempts:
                        raise
                    print(f"[{label}] transient installation failure; waiting before retry", flush=True)
                    try:
                        verify_bridge(database)
                    except Exception:
                        time.sleep(5)
            print(f"[{label}] verifying GET and POST health", flush=True)
            verify_bridge(database)
            assert_no_bootstrap_users(database)
            print(f"[{label}] passed", flush=True)
        except Exception as exc:
            failures += 1
            print(f"[{label}] failed: {type(exc).__name__}: {exc}", flush=True)

    print(
        f"Summary: total={len(databases)}, full={totals['full']}, legacy={totals['legacy']}, "
        f"passed={len(databases) - failures}, failed={failures}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
