#!/usr/bin/env python3
"""Update CodexTestBridge in every server infobase from a private JSON registry."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
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
SKILLS_ROOT = ROOT.parent
LOCAL_SKILLS = (
    "access-and-navigation",
    "codex-test-bridge",
    "configuration",
    "database",
    "extension",
    "external-artifacts",
    "forms",
    "layouts",
    "metadata",
    "reports",
    "test-databases",
    "ui-testing",
    "web-publication",
)
LOCAL_COMPONENTS = (*LOCAL_SKILLS, "common")
LEGACY_SKILL_DIRECTORIES = (
    "cf-add-object", "cf-edit", "cf-info", "cf-init", "cf-new-project", "cf-validate",
    "cfe-borrow", "cfe-diff", "cfe-full-cycle", "cfe-init", "cfe-patch-method", "cfe-validate",
    "db-create", "db-dump-cf", "db-dump-xml", "db-list", "db-load-cf", "db-load-git",
    "db-load-xml", "db-run", "db-update", "repo-update",
    "epf", "epf-bsp-add-command", "epf-bsp-init", "epf-build", "epf-dump", "epf-full-cycle",
    "epf-init", "epf-validate", "erf", "erf-init",
    "form-add", "form-compile", "form-edit", "form-info", "form-patterns", "form-remove", "form-validate",
    "help-add", "ibcmd-1c-builds", "inspect", "interface-edit", "interface-validate",
    "meta-compile", "meta-edit", "meta-info", "meta-remove", "meta-validate",
    "mxl", "mxl-compile", "mxl-decompile", "mxl-info", "mxl-validate", "playwright-test",
    "query-optimization", "role-compile", "role-info", "role-validate",
    "skd-compile", "skd-decompile", "skd-edit", "skd-info", "skd-validate",
    "subsystem", "subsystem-compile", "subsystem-edit", "subsystem-info", "subsystem-validate",
    "template-add", "template-remove", "validate",
    "web-info", "web-publish", "web-session", "web-stop", "web-test", "web-unpublish",
)
COMPATIBILITY_PATTERN = re.compile(r"Version8_3_(\d+)$", re.IGNORECASE)
BRIDGE_VERSION_PATTERN = re.compile(r'Вставить\("bridgeVersion",\s*"([^"]+)"\)')


class UpdateError(RuntimeError):
    pass


def default_codex_skills_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "skills"


def default_cursor_skills_dir() -> Path:
    return Path.home() / ".cursor" / "skills"


def _ignore_local_skill_artifacts(_directory: str, names: list[str]) -> set[str]:
    ignored = {".browser-session.json", ".git", ".mypy_cache", ".pytest_cache", "__pycache__", "node_modules"}
    return {name for name in names if name in ignored or name.endswith((".pyc", ".pyo"))}


def _remove_generated_local_artifacts(destination: Path) -> None:
    for directory_name in ("__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"):
        for directory in destination.rglob(directory_name):
            if directory.is_dir():
                shutil.rmtree(directory)
    for generated in destination.rglob("*"):
        if generated.is_file() and (generated.name == ".browser-session.json" or generated.suffix in {".pyc", ".pyo"}):
            generated.unlink()


def sync_local_skills(
    source_skills_root: Path,
    destinations: dict[str, Path],
    *,
    dry_run: bool = False,
) -> list[str]:
    """Install the canonical domain set and remove obsolete skill entrypoints."""
    sources = {component: source_skills_root / component for component in LOCAL_COMPONENTS}
    missing = [component for component, source in sources.items() if not source.is_dir()]
    if missing:
        raise UpdateError(f"Local skill source is incomplete: {', '.join(missing)}")

    synced: list[str] = []
    for agent, destination_root in destinations.items():
        destination_root = destination_root.expanduser().resolve()
        if not dry_run:
            destination_root.mkdir(parents=True, exist_ok=True)
            for legacy_name in LEGACY_SKILL_DIRECTORIES:
                legacy = destination_root / legacy_name
                if legacy.is_dir():
                    shutil.rmtree(legacy)
                elif legacy.exists():
                    legacy.unlink()
        for component, source in sources.items():
            destination = destination_root / component
            if source.resolve() == destination.resolve():
                continue
            if not dry_run:
                # Canonical components are mirrored so deleted files cannot survive
                # an update. Keep test-databases as an overlay because it may contain
                # a private registry that must never be replaced by repository data.
                if component != "test-databases" and (destination.exists() or destination.is_symlink()):
                    if destination.is_symlink() or destination.is_file():
                        destination.unlink()
                    else:
                        shutil.rmtree(destination)
                shutil.copytree(
                    source,
                    destination,
                    dirs_exist_ok=True,
                    copy_function=shutil.copy2,
                    ignore=_ignore_local_skill_artifacts,
                )
                _remove_generated_local_artifacts(destination)
        synced.append(agent)
    return synced


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
    return "full" if int(match.group(1)) >= 13 else "legacy"


def source_bridge_version() -> str:
    module = ROOT / "src" / "HTTPServices" / "CodexTestBridge" / "Ext" / "Module.bsl"
    match = BRIDGE_VERSION_PATTERN.search(module.read_text(encoding="utf-8-sig"))
    if match is None:
        raise UpdateError("Bridge version was not found in the source module")
    return match.group(1)


def unsupported_database_reason(database: dict[str, Any]) -> str | None:
    if not all(isinstance(database.get(field), str) and database[field] for field in ("Srvr", "Ref")):
        return "not a server infobase"
    bridge = database.get("Bridge")
    if not isinstance(bridge, dict) or not isinstance(bridge.get("BaseUrl"), str) or not bridge["BaseUrl"]:
        return "Bridge.BaseUrl is not configured"
    return None


def validate_registered_credentials(database: dict[str, Any]) -> None:
    if not isinstance(database.get("User"), str) or not database["User"]:
        raise UpdateError("Database entry has no registered User")
    if "Password" in database and not isinstance(database["Password"], str):
        raise UpdateError("Database entry Password must be a string")


def sanitized_process_error(completed: subprocess.CompletedProcess[str], database: dict[str, Any]) -> str:
    lines = (completed.stderr or completed.stdout or "").strip().splitlines()
    detail = lines[-1] if lines else "no child-process diagnostics"
    sensitive_values = [
        database.get("User"), database.get("Password"), database.get("Srvr"), database.get("Ref"),
        (database.get("Bridge") or {}).get("BaseUrl") if isinstance(database.get("Bridge"), dict) else None,
    ]
    for value in sensitive_values:
        if isinstance(value, str) and value:
            detail = detail.replace(value, "<redacted>")
    return detail[:1000]


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


def verify_bridge(database: dict[str, Any], expected_version: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            get_result = request_bridge(database, "GET", "/health")
            post_result = request_bridge(database, "POST", "/command", {"command": "health"})
            capabilities = request_bridge(database, "POST", "/command", {"command": "capabilities"})
            if not get_result.get("ok", True) or not post_result.get("ok", True):
                last_error = UpdateError("Bridge health response is not successful")
            elif capabilities.get("bridgeVersion") != expected_version:
                last_error = UpdateError("Installed bridge version does not match the requested artifact")
            else:
                return
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


def install_database(
    database: dict[str, Any], platform: Path, cfe: Path, timeout: float,
) -> None:
    if unsupported_database_reason(database) is not None:
        raise UpdateError("Only server infobases with Bridge.BaseUrl can be installed")
    validate_registered_credentials(database)
    username = database["User"]
    password_environment = "CODEX_CTB_REGISTERED_USER_PASSWORD"
    environment = os.environ.copy()
    environment[password_environment] = database.get("Password", "")
    with tempfile.TemporaryDirectory(prefix="ctb-registered-user-update-") as temporary:
        log_path = Path(temporary) / "designer.log"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "install_cfe_designer_hidden.py"),
            "--platform", str(platform),
            "--server", database["Srvr"],
            "--database", database["Ref"],
            "--user", username,
            "--password-env", password_environment,
            "--extension", "CodexTestBridge",
            "--cfe", str(cfe),
            "--log", str(log_path),
            "--timeout", str(timeout),
        ]
        completed = subprocess.run(
            command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=timeout + 60,
        )
        if completed.returncode != 0:
            raise UpdateError(
                f"Registered-user CFE installation failed: {sanitized_process_error(completed, database)}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update CodexTestBridge in all test databases from a private registry")
    parser.add_argument("--registry", default=os.environ.get("CODEX_1C_TEST_DATABASES", ""), help="Private test-databases JSON path")
    parser.add_argument("--platform", default=os.environ.get("CODEX_1C_EXECUTABLE", ""), help="1cv8 executable used by hidden Designer")
    parser.add_argument("--full-cfe", default=str(ROOT / "codex-test-bridge.cfe"))
    parser.add_argument("--legacy-cfe", default=str(ROOT / "codex-test-bridge-legacy.cfe"))
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--install-attempts", type=int, default=3, help="Retries for transient Designer or publication failures")
    parser.add_argument("--database", action="append", default=[], help="Only update matching Ref, project folder, or Bridge.AppName; repeatable")
    parser.add_argument("--dry-run", action="store_true", help="Detect variants without modifying infobases")
    parser.add_argument("--expected-version", default=source_bridge_version(), help="Bridge version required after installation")
    parser.add_argument("--codex-skills-dir", default=str(default_codex_skills_dir()), help="Local Codex skills directory")
    parser.add_argument("--cursor-skills-dir", default=str(default_cursor_skills_dir()), help="Local Cursor skills directory")
    parser.add_argument("--skip-local-skills-sync", action="store_true", help="Do not update local Codex and Cursor skills")
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
    if args.database:
        requested = {value.casefold() for value in args.database}
        databases = [database for database in databases if requested.intersection({
            str(database.get("Ref", "")).casefold(),
            Path(str(database.get("path", ""))).name.casefold(),
            str((database.get("Bridge") or {}).get("AppName", "")).casefold(),
        })]
        if not databases:
            raise UpdateError("No registry databases matched --database")
    cfe_files = {"full": Path(args.full_cfe).resolve(), "legacy": Path(args.legacy_cfe).resolve()}
    if not args.dry_run:
        for variant, cfe in cfe_files.items():
            if not cfe.is_file():
                raise UpdateError(f"{variant} CFE file does not exist")

    if not args.skip_local_skills_sync:
        agents = sync_local_skills(
            SKILLS_ROOT,
            {
                "Codex": Path(args.codex_skills_dir),
                "Cursor": Path(args.cursor_skills_dir),
            },
            dry_run=args.dry_run,
        )
        action = "ready" if args.dry_run else "updated"
        print(f"[local skills] {action}: {', '.join(agents)}", flush=True)

    failures = 0
    skipped = 0
    passed = 0
    totals = {"full": 0, "legacy": 0}
    for index, database in enumerate(databases, 1):
        label = f"database {index}/{len(databases)}"
        unsupported_reason = unsupported_database_reason(database)
        if unsupported_reason is not None:
            skipped += 1
            print(f"[{label}] skipped: {unsupported_reason}", flush=True)
            continue
        try:
            validate_registered_credentials(database)
            mode = read_compatibility_mode(database)
            variant = cfe_variant(mode)
            totals[variant] += 1
            print(f"[{label}] compatibility={mode}, variant={variant}", flush=True)
            if args.dry_run:
                passed += 1
                print(f"[{label}] ready", flush=True)
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
                    time.sleep(5)
            print(f"[{label}] verifying GET and POST health", flush=True)
            verify_bridge(database, args.expected_version)
            assert_no_bootstrap_users(database)
            passed += 1
            print(f"[{label}] passed", flush=True)
        except Exception as exc:
            failures += 1
            print(f"[{label}] failed: {type(exc).__name__}: {exc}", flush=True)

    print(
        f"Summary: total={len(databases)}, full={totals['full']}, legacy={totals['legacy']}, "
        f"passed={passed}, skipped={skipped}, failed={failures}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
