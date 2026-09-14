"""Warm UI suite with server bridge hooks between UI scenarios."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Callable

from hybrid_runner import _definition
from scenario_runner import ScenarioRunner, TOKEN, read_path, substitute
from ui_suite import save_ui_suite_junit
from ui_worker import UiWorkerError, bridge_command, run_ui_worker


def run_hybrid_suite(definition: dict[str, Any], definition_path: str | Path, worker_config: dict[str, Any], artifact_dir: str | Path) -> dict[str, Any]:
    if not isinstance(definition, dict) or not isinstance(definition.get("scenarios"), list) or not definition["scenarios"]:
        raise UiWorkerError("Hybrid suite requires a non-empty scenarios array")
    base, artifacts = Path(definition_path).resolve().parent, Path(artifact_dir).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    items, contexts, created, shared_context = [], {}, {}, {}
    for index, raw in enumerate(definition["scenarios"], 1):
        if not isinstance(raw, dict) or "ui" not in raw:
            raise UiWorkerError(f"Hybrid suite scenario {index} requires ui")
        scenario = _definition(raw["ui"], base)
        if scenario is None: raise UiWorkerError(f"Hybrid suite scenario {index} has invalid ui")
        items.append({"id": raw.get("id", f"scenario-{index}"), "source": str(definition_path), "scenario": scenario, "before": _definition(raw.get("before"), base), "after": _definition(raw.get("after"), base), "finally": _definition(raw.get("finally"), base)})
    hook_config = dict(worker_config)
    bridge_url = str(hook_config.get("bridgeBaseUrl", ""))
    for alias, environment_name in hook_config.get("environmentPlaceholders", {}).items():
        bridge_url = bridge_url.replace("{" + str(alias) + "}", os.environ.get(str(environment_name), ""))
    hook_config["bridgeBaseUrl"] = bridge_url
    server = ScenarioRunner(lambda payload: bridge_command(hook_config, payload))
    def substitute_shared(value: Any, context: dict[str, Any]) -> Any:
        """Resolve prior-scenario values, preserving aliases made in this stage."""
        if isinstance(value, dict): return {key: substitute_shared(item, context) for key, item in value.items()}
        if isinstance(value, list): return [substitute_shared(item, context) for item in value]
        if not isinstance(value, str): return value
        whole = TOKEN.fullmatch(value)
        if whole:
            try: return read_path(context, whole.group(1))
            except Exception: return value
        def replace(match: Any) -> str:
            try: return str(read_path(context, match.group(1)))
            except Exception: return match.group(0)
        return TOKEN.sub(replace, value)
    def run_phase(item: dict[str, Any], phase: str) -> dict[str, Any]:
        item_id = str(item["id"])
        stage = item.get(phase)
        context = dict(shared_context)
        context.update(contexts.setdefault(item_id, {}))
        if stage is None: return {"ok": True, "scenario": substitute(item["scenario"], context)}
        stage = substitute_shared(copy.deepcopy(stage), context)
        result = server.run(stage, defer_cleanup=phase == "before")
        if phase in {"before", "after"}:
            outputs = result.get("outputs", {})
            contexts[item_id].update(outputs)
            shared_context.update(outputs)
            context.update(outputs)
        if phase == "before":
            created[item_id] = result.get("createdObjects", [])
        if phase == "finally": result["createdCleanup"] = server.cleanup_created(created.get(item_id, []))
        # Resolve aliases produced by this phase, but retain placeholders that
        # deliberately belong to later segments.  ``substitute`` is strict and
        # therefore turns those valid forward references into a hook failure.
        return {
            "ok": bool(result.get("ok")),
            "scenario": substitute_shared(copy.deepcopy(item["scenario"]), context),
            "result": result,
            "error": result.get("error"),
        }

    suite_path = artifacts / "hybrid-suite.ui.json"
    suite_path.write_text(json.dumps({"name": definition.get("name", "hybrid-suite"), "failFast": bool(definition.get("failFast", False)), "scenarios": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    def hook(request: dict[str, Any]) -> dict[str, Any]:
        return run_phase(items[int(request["scenarioIndex"]) - 1], request["phase"])
    result = run_ui_worker(worker_config, suite_path, artifacts, server_hook_handler=hook)
    manager = result.get("managerResult") if isinstance(result.get("managerResult"), dict) else {}
    result["scenarios"] = manager.get("scenarios", [])
    result["suite"] = {"warm": True, "hybrid": True, "requested": len(items), "failFast": bool(definition.get("failFast", False))}
    result["ok"] = bool(result.get("ok")) and len(result["scenarios"]) == len(items) and all(x.get("ok") for x in result["scenarios"])
    return result

def save_hybrid_suite_junit(result: dict[str, Any], path: str | Path) -> None:
    save_ui_suite_junit(result, path)
