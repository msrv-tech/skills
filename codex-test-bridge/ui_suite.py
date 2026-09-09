"""Warm, separately reported UI suites."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from scenario_runner import save_junit_report
from ui_worker import UiWorkerError, run_ui_worker


def collect_ui_scenarios(values: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    for value in values:
        path = Path(value).resolve()
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.ui.json")))
        else:
            raise UiWorkerError(f"UI scenario path does not exist: {path}")
    unique = list(dict.fromkeys(files))
    if not unique:
        raise UiWorkerError("No *.ui.json scenarios were found")
    return unique


def _junit_shape(result: dict[str, Any]) -> dict[str, Any]:
    scenarios = []
    for item in result.get("scenarios", []):
        scenarios.append({
            "source": item.get("source", item.get("scenarioId", "ui scenario")),
            "name": item.get("name", item.get("scenarioId", "ui scenario")),
            "ok": item.get("ok", False),
            "durationMs": sum(step.get("durationMs", 0) for step in item.get("steps", []) if isinstance(step, dict)),
            "error": {"type": "ScenarioFailure", "message": str(item.get("error") or next((step.get("error") for step in item.get("steps", []) if isinstance(step, dict) and step.get("status") == "failed"), "UI scenario failed"))},
            "steps": item.get("steps", []),
        })
    return {"ok": result.get("ok", False), "scenarios": scenarios, "total": len(scenarios), "failed": len([item for item in scenarios if not item["ok"]]), "durationMs": result.get("durationMs", 0)}


def run_ui_suite(
    config: dict[str, Any], scenario_paths: list[str | Path], artifact_dir: str | Path, *, fail_fast: bool = False,
) -> dict[str, Any]:
    paths = collect_ui_scenarios(scenario_paths)
    artifacts = Path(artifact_dir).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    suite = {
        "name": "ui-suite",
        "failFast": fail_fast,
        "scenarios": [
            {"id": f"scenario-{index}", "source": str(path), "scenario": json.loads(path.read_text(encoding="utf-8-sig"))}
            for index, path in enumerate(paths, start=1)
        ],
    }
    suite_path = artifacts / "ui-suite.json"
    suite_path.write_text(json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    started = time.monotonic()
    worker_result = run_ui_worker(config, suite_path, artifacts)
    manager_result = worker_result.get("managerResult") if isinstance(worker_result.get("managerResult"), dict) else {}
    scenarios = manager_result.get("scenarios", []) if isinstance(manager_result.get("scenarios"), list) else []
    result = dict(worker_result)
    result["suite"] = {"warm": True, "requested": len(paths), "failFast": fail_fast}
    result["scenarios"] = scenarios
    result["ok"] = bool(worker_result.get("ok")) and len(scenarios) == len(paths) and all(item.get("ok") for item in scenarios)
    result["status"] = "passed" if result["ok"] else "failed"
    result["durationMs"] = round((time.monotonic() - started) * 1000)
    return result


def save_ui_suite_junit(result: dict[str, Any], path: str | Path) -> None:
    save_junit_report(_junit_shape(result), path)
