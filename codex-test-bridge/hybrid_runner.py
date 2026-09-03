#!/usr/bin/env python3
"""Server arrange/assert plus native UI act, with guaranteed created-object cleanup."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scenario_runner import ScenarioRunner, load_scenario, substitute
from ui_worker import run_ui_worker


class HybridScenarioError(RuntimeError):
    pass


def _definition(value: Any, base: Path) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        return load_scenario((base / value).resolve())
    raise HybridScenarioError("Hybrid stages must be inline objects or relative JSON paths")


def run_hybrid_scenario(
    definition: dict[str, Any], definition_path: str | Path,
    send_command: Callable[[dict[str, Any]], dict[str, Any]],
    worker_config: dict[str, Any], artifact_dir: str | Path,
) -> dict[str, Any]:
    if not isinstance(definition, dict) or "ui" not in definition:
        raise HybridScenarioError("Hybrid scenario requires ui stage")
    started = datetime.now(timezone.utc)
    base = Path(definition_path).resolve().parent
    artifacts = Path(artifact_dir).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    server = ScenarioRunner(send_command)
    arrange = assertion = ui = None
    cleanup: list[dict[str, Any]] = []
    context: dict[str, Any] = {}
    error = None
    created: list[dict[str, str]] = []
    try:
        arrange_definition = _definition(definition.get("arrange"), base)
        if arrange_definition:
            arrange = server.run(arrange_definition, defer_cleanup=True)
            created = arrange.get("createdObjects", [])
            if not arrange.get("ok"):
                raise HybridScenarioError("Arrange stage failed")
            context.update(arrange.get("outputs", {}))
        ui_definition = _definition(definition["ui"], base)
        assert ui_definition is not None
        ui_definition = substitute(ui_definition, context)
        compiled_ui = artifacts / "compiled.ui.json"
        compiled_ui.write_text(json.dumps(ui_definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ui = run_ui_worker(worker_config, compiled_ui, artifacts / "ui")
        if not ui.get("ok"):
            raise HybridScenarioError("UI stage failed")
        assertion_definition = _definition(definition.get("assert"), base)
        if assertion_definition:
            assertion_definition = substitute(assertion_definition, context)
            assertion = server.run(assertion_definition)
            if not assertion.get("ok"):
                raise HybridScenarioError("Server assert stage failed")
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        cleanup_definition = _definition(definition.get("cleanup"), base)
        if cleanup_definition:
            cleanup_definition = substitute(cleanup_definition, context)
            cleanup.append(server.run(cleanup_definition))
        cleanup.extend(server.cleanup_created(created))
    finished = datetime.now(timezone.utc)
    cleanup_ok = all(item.get("ok", False) for item in cleanup)
    ok = error is None and cleanup_ok
    result = {
        "schemaVersion": 1, "ok": ok, "name": definition.get("name", "unnamed"),
        "status": "passed" if ok else ("cleanupFailed" if error is None else "failed"),
        "startedAt": started.isoformat(), "finishedAt": finished.isoformat(),
        "durationMs": round((finished - started).total_seconds() * 1000),
        "arrange": arrange, "ui": ui, "assert": assertion, "cleanup": cleanup,
    }
    if error:
        result["error"] = error
    return result
