#!/usr/bin/env python3
"""Validate or execute CodexTestBridge against the separate fixture CFE."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_ROOT = ROOT.parent / "codex-test-bridge"
sys.path.insert(0, str(BRIDGE_ROOT))
sys.path.insert(0, str(BRIDGE_ROOT / "scripts"))

from ui_conformance import build_conformance_report, load_conformance_scenarios
from ui_suite import run_ui_suite, save_ui_suite_junit
from ui_worker import load_worker_config, write_atomic_json
from run_ui_from_test_database import (  # noqa: E402
    database_environment,
    select_database,
    temporary_environment,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the native 1C UI action conformance matrix")
    parser.add_argument("worker_config", nargs="?", help="UI worker JSON config; omit with --validate-only")
    parser.add_argument("--registry", default="", help="Private test-databases JSON path")
    parser.add_argument("--database", default="", help="Registered test database selector")
    parser.add_argument("--platform", default="", help="1cv8 executable for registry mode")
    parser.add_argument("--scenario-dir", default=str(ROOT / "scenarios" / "ui-conformance"))
    parser.add_argument("--artifact-dir", default="artifacts/ui-conformance")
    parser.add_argument("--report", default="")
    parser.add_argument("--junit", default="")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)
    registry_mode = bool(args.registry or args.database or args.platform)
    if registry_mode and not all((args.registry, args.database, args.platform)):
        parser.error("--registry, --database and --platform must be provided together")
    if registry_mode and args.worker_config:
        parser.error("worker_config and registry mode are mutually exclusive")
    if not args.validate_only and not args.worker_config and not registry_mode:
        parser.error("worker_config or registry mode is required unless --validate-only is used")

    scenarios = load_conformance_scenarios([args.scenario_dir])
    if args.validate_only:
        matrix = build_conformance_report(scenarios)
        print(json.dumps(matrix["summary"], ensure_ascii=False, indent=2))
        return 0 if matrix["ok"] else 1

    environment: dict[str, str] = {}
    worker_config_path = args.worker_config
    if registry_mode:
        registry = json.loads(Path(args.registry).read_text(encoding="utf-8-sig"))
        database = select_database(registry, args.database)
        environment = database_environment(database, args.platform)
        worker_config_path = str(BRIDGE_ROOT / "ui-worker.cross-db.credentials.example.json")
    with temporary_environment(environment):
        result = run_ui_suite(
            load_worker_config(worker_config_path),
            [scenario["path"] for scenario in scenarios],
            args.artifact_dir,
            fail_fast=args.fail_fast,
        )
    matrix = build_conformance_report(scenarios, result)
    result["conformance"] = matrix
    report_path = Path(args.report).resolve() if args.report else Path(args.artifact_dir).resolve() / "conformance-report.json"
    write_atomic_json(report_path, result)
    if args.junit:
        save_ui_suite_junit(result, args.junit)
    print(json.dumps({"ok": result.get("ok") and matrix["ok"], "report": str(report_path), **matrix["summary"]}, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") and matrix["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
