"""Executable conformance matrix for native 1C UI actions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ui_action_catalog import action_rows, load_ui_action_catalog
from ui_suite import collect_ui_scenarios
from ui_worker import UiWorkerError, prepare_native_ui_scenario


def _step_path(step: dict[str, Any], path: str) -> Any:
    if path == "assertion":
        return next((name for name in ("expected", "contains", "notEmpty") if name in step), None)
    value: Any = step
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches_variant(step: dict[str, Any], match: dict[str, Any]) -> bool:
    return all(_step_path(step, path) == expected for path, expected in match.items())


def load_conformance_scenarios(values: list[str | Path]) -> list[dict[str, Any]]:
    scenarios = []
    for path in collect_ui_scenarios(values):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        prepared = prepare_native_ui_scenario(data)
        cases = prepared.get("conformanceCases")
        if not isinstance(cases, list) or not cases or not all(isinstance(case, str) and case for case in cases):
            raise UiWorkerError(f"Conformance scenario has no conformanceCases: {path}")
        scenarios.append({"path": path.resolve(), "data": prepared, "cases": cases})
    return scenarios


def validate_conformance_coverage(scenarios: list[dict[str, Any]]) -> dict[str, Path]:
    catalog = load_ui_action_catalog()
    known_cases = set(catalog["caseIds"])
    case_sources: dict[str, Path] = {}
    for scenario in scenarios:
        for case in scenario["cases"]:
            if case not in known_cases:
                raise UiWorkerError(f"Unknown conformance case {case}: {scenario['path']}")
            if case in case_sources:
                raise UiWorkerError(f"Conformance case {case} is declared by more than one scenario")
            case_sources[case] = scenario["path"]
    required_cases = {
        case
        for action in catalog["actions"]
        if action["coverage"] == "fixture"
        for case in action["cases"]
    }
    missing = sorted(required_cases - set(case_sources))
    if missing:
        raise UiWorkerError(f"Fixture conformance cases are missing: {', '.join(missing)}")

    # A scenario cannot claim a case without actually invoking every fixture
    # action assigned to that case. This keeps the matrix executable instead
    # of turning conformanceCases into an unchecked annotation.
    for action in catalog["actions"]:
        if action["coverage"] != "fixture":
            continue
        declared_by = [
            scenario for scenario in scenarios
            if set(scenario["cases"]) & set(action["cases"])
        ]
        invoked = {
            step.get("action")
            for scenario in declared_by
            for step in scenario["data"].get("steps", [])
            if isinstance(step, dict)
        }
        if action["name"] not in invoked:
            raise UiWorkerError(
                f"Fixture action {action['name']} is not invoked by its conformance cases"
            )
        action_steps = [
            step
            for scenario in declared_by
            for step in scenario["data"].get("steps", [])
            if isinstance(step, dict) and step.get("action") == action["name"]
        ]
        for variant in action.get("variants", []):
            if not any(_matches_variant(step, variant["match"]) for step in action_steps):
                raise UiWorkerError(
                    f"Fixture action {action['name']} variant {variant['id']} is not invoked"
                )
    return case_sources


def build_conformance_report(
    scenarios: list[dict[str, Any]], suite_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_sources = validate_conformance_coverage(scenarios)
    scenario_status: dict[Path, str] = {}
    if suite_result is not None:
        for result in suite_result.get("scenarios", []):
            source = result.get("source")
            if isinstance(source, str) and source:
                scenario_status[Path(source).resolve()] = "passed" if result.get("ok") else "failed"

    cases = []
    for case, source in sorted(case_sources.items()):
        cases.append({
            "id": case,
            "source": str(source),
            "status": scenario_status.get(source, "ready" if suite_result is None else "not-run"),
        })
    case_status = {case["id"]: case["status"] for case in cases}
    actions = []
    for name, action in action_rows().items():
        coverage = action["coverage"]
        if coverage == "fixture":
            statuses = [case_status.get(case, "missing") for case in action["cases"]]
            if suite_result is None:
                status = "ready" if all(value == "ready" for value in statuses) else "missing"
            else:
                status = "passed" if all(value == "passed" for value in statuses) else "failed"
        elif coverage == "alias":
            status = next((item["status"] for item in actions if item["action"] == action.get("aliasOf")), "alias")
        else:
            status = "not-run"
        actions.append({
            "action": name,
            "visibility": action["visibility"],
            "scope": action["scope"],
            "elementTypes": action["elementTypes"],
            "backendElementTypes": action.get("backendElementTypes", {}),
            "backends": action["backends"],
            "coverage": coverage,
            "cases": action["cases"],
            "variants": action.get("variants", []),
            "status": status,
        })
    fixture_actions = [action for action in actions if action["coverage"] == "fixture"]
    public_actions = [action for action in actions if action["visibility"] == "public"]
    return {
        "ok": all(action["status"] in {"ready", "passed"} for action in public_actions),
        "catalogVersion": load_ui_action_catalog()["version"],
        "summary": {
            "actions": len(actions),
            "publicActions": len(public_actions),
            "fixtureActions": len(fixture_actions),
            "passed": len([action for action in public_actions if action["status"] == "passed"]),
            "ready": len([action for action in public_actions if action["status"] == "ready"]),
            "failed": len([action for action in public_actions if action["status"] not in {"ready", "passed"}]),
            "aliases": len([action for action in actions if action["visibility"] == "alias"]),
            "internalActions": len([action for action in actions if action["visibility"] == "internal"]),
            "variants": sum(len(action["variants"]) for action in actions),
        },
        "cases": cases,
        "actions": actions,
    }
