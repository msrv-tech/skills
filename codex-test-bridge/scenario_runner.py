#!/usr/bin/env python3
"""Headless declarative test runner for CodexTestBridge."""

from __future__ import annotations

import copy
import json
import re
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


TOKEN = re.compile(r"\$\{([^}]+)}")
ALIAS = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
ASSERTION_OPERATORS = {
    "eq", "ne", "gt", "gte", "lt", "lte", "contains", "matches",
    "exists", "empty", "notEmpty",
}


class ScenarioError(RuntimeError):
    pass


class StepFailure(ScenarioError):
    def __init__(self, message: str, result: dict[str, Any]):
        super().__init__(message)
        self.result = result


def read_path(value: Any, path: str) -> Any:
    current = value
    if not path:
        return current
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ScenarioError(f"Path not found: {path} (failed at {part})")
    return current


def substitute(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: substitute(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, context) for item in value]
    if not isinstance(value, str):
        return value

    match = TOKEN.fullmatch(value)
    if match:
        return read_path(context, match.group(1))

    def replace(match: re.Match[str]) -> str:
        resolved = read_path(context, match.group(1))
        if isinstance(resolved, (dict, list)):
            return json.dumps(resolved, ensure_ascii=False)
        return str(resolved)

    return TOKEN.sub(replace, value)


def check_assertion(actual: Any, operator: str, expected: Any = None) -> bool:
    operators: dict[str, Callable[[Any, Any], bool]] = {
        "eq": lambda a, e: a == e,
        "ne": lambda a, e: a != e,
        "gt": lambda a, e: a > e,
        "gte": lambda a, e: a >= e,
        "lt": lambda a, e: a < e,
        "lte": lambda a, e: a <= e,
        "contains": lambda a, e: e in a,
        "matches": lambda a, e: re.search(str(e), str(a)) is not None,
        "exists": lambda a, e: a is not None,
        "empty": lambda a, e: len(a) == 0,
        "notEmpty": lambda a, e: len(a) > 0,
    }
    if operator not in operators:
        raise ScenarioError(f"Unsupported assertion operator: {operator}")
    return operators[operator](actual, expected)


@dataclass
class CreatedObject:
    kind: str
    name: str
    uuid: str


class ScenarioRunner:
    def __init__(self, send_command: Callable[[dict[str, Any]], dict[str, Any]], sleep: Callable[[float], None] = time.sleep):
        self.send_command = send_command
        self.sleep = sleep

    def run(self, scenario: dict[str, Any], defer_cleanup: bool = False) -> dict[str, Any]:
        validate_scenario(scenario)
        started = datetime.now(timezone.utc)
        run_id = str(uuid.uuid4())
        context: dict[str, Any] = {"run": {"id": run_id}}
        created: list[CreatedObject] = []
        results: list[dict[str, Any]] = []
        status = "passed"
        error: dict[str, Any] | None = None

        try:
            for index, raw_step in enumerate(scenario.get("steps", []), start=1):
                try:
                    result = self._run_step(index, raw_step, context)
                    actual_request = result.pop("_actualRequest")
                    results.append(result)
                except StepFailure as exc:
                    actual_request = exc.result.pop("_actualRequest")
                    results.append(exc.result)
                    tracked = self._created_object(actual_request, exc.result.get("response", {}))
                    if tracked:
                        created.append(tracked)
                    raise
                if result.get("saveAs"):
                    context[result["saveAs"]] = result["response"]
                tracked = self._created_object(actual_request, result["response"])
                if tracked:
                    created.append(tracked)
        except Exception as exc:
            status = "failed"
            error = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            cleanup = self._cleanup(created) if scenario.get("cleanup", True) and not defer_cleanup else []
            cleanup.extend(self._run_finally(scenario.get("finally", []), context))

        cleanup_ok = all(item.get("ok", False) for item in cleanup)
        if not cleanup_ok and status == "passed":
            status = "cleanupFailed"
            error = {"type": "CleanupError", "message": "One or more cleanup commands failed"}

        finished = datetime.now(timezone.utc)
        report = {
            "schemaVersion": 1,
            "ok": status == "passed",
            "runId": run_id,
            "name": scenario.get("name", "unnamed"),
            "status": status,
            "startedAt": started.isoformat(),
            "finishedAt": finished.isoformat(),
            "durationMs": round((finished - started).total_seconds() * 1000),
            "steps": results,
            "cleanup": cleanup,
            "outputs": {key: value for key, value in context.items() if key != "run"},
            "createdObjects": [item.__dict__ for item in created] if defer_cleanup else [],
        }
        if error:
            report["error"] = error
        return report

    def cleanup_created(self, items: list[dict[str, str]]) -> list[dict[str, Any]]:
        return self._cleanup([CreatedObject(item["kind"], item["name"], item["uuid"]) for item in items])

    def _run_step(self, index: int, raw_step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        step = substitute(copy.deepcopy(raw_step), context)
        request = step.get("request")
        if not isinstance(request, dict) or not request.get("command"):
            raise ScenarioError(f"Step {index}: request.command is required")

        retry = step.get("retry", {})
        attempts = max(1, int(retry.get("attempts", 1)))
        delay = max(0, float(retry.get("delaySeconds", 1)))
        response: dict[str, Any] = {}
        assertion_error = ""

        for attempt in range(1, attempts + 1):
            try:
                response = self.send_command(request)
                if not response.get("ok", True):
                    assertion_error = f"Bridge error: {response.get('error', response)}"
                else:
                    assertion_error = self._assertions(step.get("assert", []), response, context)
            except Exception as exc:
                response = {}
                assertion_error = f"Transport error: {type(exc).__name__}: {exc}"
            if not assertion_error:
                break
            if attempt < attempts:
                self.sleep(delay)

        result = {
            "index": index,
            "name": step.get("name", f"step-{index}"),
            "status": "passed" if not assertion_error else "failed",
            "attempts": attempt,
            "request": redact_paths(request, step.get("redactRequest", [])),
            "_actualRequest": request,
            "response": response,
        }
        if step.get("saveAs"):
            result["saveAs"] = step["saveAs"]
        if assertion_error:
            result["error"] = assertion_error
            raise StepFailure(f"Step {index} ({result['name']}): {assertion_error}", result)
        return result

    def _assertions(self, assertions: list[dict[str, Any]], response: dict[str, Any], context: dict[str, Any]) -> str:
        assertion_context = dict(context)
        assertion_context["response"] = response
        for assertion in assertions:
            path = assertion.get("path", "")
            operator = assertion.get("operator", "eq")
            expected = substitute(assertion.get("expected"), assertion_context)
            try:
                actual = read_path(response, path)
                passed = check_assertion(actual, operator, expected)
            except Exception as exc:
                return str(exc)
            if not passed:
                return f"assert {path} {operator} failed: expected={expected!r}, actual={actual!r}"
        return ""

    @staticmethod
    def _created_object(request: dict[str, Any], response: dict[str, Any]) -> CreatedObject | None:
        if request.get("command", "").lower() not in {"writeobject", "createcatalogitem", "createdocument"}:
            return None
        if request.get("uuid") or not response.get("ref", {}).get("uuid"):
            return None
        kind = request.get("kind") or ("catalog" if request.get("catalog") else "document")
        name = request.get("name") or request.get("catalog") or request.get("document")
        return CreatedObject(kind, name, response["ref"]["uuid"])

    def _cleanup(self, created: list[CreatedObject]) -> list[dict[str, Any]]:
        results = []
        for item in reversed(created):
            request = {
                "command": "DeleteObject",
                "kind": item.kind,
                "name": item.name,
                "uuid": item.uuid,
                "deletionMark": True,
            }
            try:
                response = self.send_command(request)
                results.append({"request": request, "response": response, "ok": response.get("ok", True)})
            except Exception as exc:
                results.append({"request": request, "ok": False, "error": str(exc)})
        return results

    def _run_finally(self, commands: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for raw_item in reversed(commands):
            item = substitute(copy.deepcopy(raw_item), context)
            request = item.get("request", item)
            redacted_request = redact_paths(request, item.get("redactRequest", [])) if "request" in item else request
            try:
                response = self.send_command(request)
                results.append({"request": redacted_request, "response": response, "ok": response.get("ok", True)})
            except Exception as exc:
                results.append({"request": redacted_request, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return results


def redact_paths(value: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    for path in paths:
        parts = path.split(".")
        current: Any = result
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if isinstance(current, dict) and parts[-1] in current:
            current[parts[-1]] = "***"
    return result


def validate_scenario(scenario: dict[str, Any]) -> None:
    if not isinstance(scenario, dict):
        raise ScenarioError("Scenario must be a JSON object")
    steps = scenario.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ScenarioError("Scenario must contain a non-empty steps array")
    if not isinstance(scenario.get("cleanup", True), bool):
        raise ScenarioError("cleanup must be boolean")
    aliases = {"run"}
    for index, step in enumerate(steps, start=1):
        _validate_step(step, f"steps[{index - 1}]")
        alias = step.get("saveAs")
        if alias:
            if not ALIAS.fullmatch(alias):
                raise ScenarioError(f"steps[{index - 1}].saveAs has invalid alias: {alias}")
            if alias in aliases:
                raise ScenarioError(f"Duplicate or reserved saveAs alias: {alias}")
            aliases.add(alias)
    finally_commands = scenario.get("finally", [])
    if not isinstance(finally_commands, list):
        raise ScenarioError("finally must be an array")
    for index, item in enumerate(finally_commands):
        request = item.get("request", item) if isinstance(item, dict) else None
        if not isinstance(request, dict) or not isinstance(request.get("command"), str) or not request["command"]:
            raise ScenarioError(f"finally[{index}] must contain request.command")


def _validate_step(step: Any, location: str) -> None:
    if not isinstance(step, dict):
        raise ScenarioError(f"{location} must be an object")
    request = step.get("request")
    if not isinstance(request, dict) or not isinstance(request.get("command"), str) or not request["command"]:
        raise ScenarioError(f"{location}.request.command is required")
    assertions = step.get("assert", [])
    if not isinstance(assertions, list):
        raise ScenarioError(f"{location}.assert must be an array")
    for index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict) or not isinstance(assertion.get("path", ""), str):
            raise ScenarioError(f"{location}.assert[{index}] must be an object with a string path")
        operator = assertion.get("operator", "eq")
        if operator not in ASSERTION_OPERATORS:
            raise ScenarioError(f"{location}.assert[{index}] has unsupported operator: {operator}")
    retry = step.get("retry", {})
    if not isinstance(retry, dict):
        raise ScenarioError(f"{location}.retry must be an object")
    attempts = retry.get("attempts", 1)
    delay = retry.get("delaySeconds", 1)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ScenarioError(f"{location}.retry.attempts must be an integer >= 1")
    if isinstance(delay, bool) or not isinstance(delay, (int, float)) or delay < 0:
        raise ScenarioError(f"{location}.retry.delaySeconds must be a number >= 0")
    redact = step.get("redactRequest", [])
    if not isinstance(redact, list) or any(not isinstance(path, str) or not path for path in redact):
        raise ScenarioError(f"{location}.redactRequest must be an array of non-empty paths")


def load_scenario(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as source:
        scenario = json.load(source)
    validate_scenario(scenario)
    return scenario


def save_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_scenario_files(path: str | Path) -> list[Path]:
    source = Path(path)
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise ScenarioError(f"Scenario path does not exist: {source}")
    files = sorted(source.rglob("*.scenario.json"))
    if not files:
        raise ScenarioError(f"No *.scenario.json files found in: {source}")
    return files


def run_suite(runner: ScenarioRunner, files: list[Path], fail_fast: bool = False) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    reports = []
    for path in files:
        try:
            definition = load_scenario(path)
            report = runner.run(definition)
        except Exception as exc:
            now = datetime.now(timezone.utc)
            report = {
                "schemaVersion": 1,
                "ok": False,
                "runId": str(uuid.uuid4()),
                "name": path.stem,
                "status": "invalid",
                "startedAt": now.isoformat(),
                "finishedAt": now.isoformat(),
                "durationMs": 0,
                "steps": [],
                "cleanup": [],
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        report["source"] = str(path)
        reports.append(report)
        if fail_fast and not report.get("ok", False):
            break

    finished = datetime.now(timezone.utc)
    failures = sum(not report.get("ok", False) for report in reports)
    return {
        "schemaVersion": 1,
        "ok": failures == 0,
        "status": "passed" if failures == 0 else "failed",
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "durationMs": round((finished - started).total_seconds() * 1000),
        "total": len(reports),
        "passed": len(reports) - failures,
        "failed": failures,
        "scenarios": reports,
    }


def save_junit_report(suite: dict[str, Any], path: str | Path) -> None:
    root = ET.Element("testsuite", {
        "name": "CodexTestBridge",
        "tests": str(suite.get("total", 0)),
        "failures": str(suite.get("failed", 0)),
        "errors": "0",
        "time": f"{suite.get('durationMs', 0) / 1000:.3f}",
    })
    for report in suite.get("scenarios", []):
        case = ET.SubElement(root, "testcase", {
            "classname": "1c.headless",
            "name": str(report.get("name", "unnamed")),
            "time": f"{report.get('durationMs', 0) / 1000:.3f}",
            "file": str(report.get("source", "")),
        })
        if not report.get("ok", False):
            error = report.get("error", {})
            message = str(error.get("message", report.get("status", "failed")))
            failure = ET.SubElement(case, "failure", {"message": message, "type": str(error.get("type", "ScenarioFailure"))})
            failed_steps = [step for step in report.get("steps", []) if step.get("status") == "failed"]
            failure.text = json.dumps(failed_steps or error, ensure_ascii=False, indent=2)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(target, encoding="utf-8", xml_declaration=True)
