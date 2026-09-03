#!/usr/bin/env python3
"""Run several UI scenarios in one warm TestClient/TestManager lifecycle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ui_worker import prepare_native_ui_scenario, run_ui_worker


def run_ui_batch(config: dict[str, Any], scenario_paths: list[str | Path], artifact_dir: str | Path) -> dict[str, Any]:
    if not scenario_paths:
        raise ValueError("At least one UI scenario is required")
    artifacts = Path(artifact_dir).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    combined: dict[str, Any] = {"name": "warm UI batch", "steps": []}
    ranges = []
    for path_value in scenario_paths:
        path = Path(path_value).resolve()
        scenario = prepare_native_ui_scenario(json.loads(path.read_text(encoding="utf-8-sig")))
        start = len(combined["steps"]) + 1
        combined["steps"].extend(scenario["steps"])
        ranges.append({"scenario": str(path), "firstStep": start, "lastStep": len(combined["steps"])})
    compiled = artifacts / "warm-batch.ui.json"
    compiled.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = run_ui_worker(config, compiled, artifacts)
    report["batch"] = {"warm": True, "scenarios": ranges}
    return report
