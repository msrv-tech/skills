#!/usr/bin/env python3
"""Compact, stable UI descriptions and failure hints for coding agents."""

from __future__ import annotations

from typing import Any


def _selector(item: dict[str, Any]) -> dict[str, str]:
    if item.get("name"):
        return {"objectName": str(item["name"])}
    if item.get("formName"):
        return {"formName": str(item["formName"])}
    if item.get("title"):
        return {"title": str(item["title"])}
    return {}


def _kind(type_name: str) -> str:
    lowered = type_name.lower()
    for marker, result in (
        ("таблица", "table"), ("поле", "field"), ("кнопка", "button"),
        ("форма", "form"), ("группа", "group"), ("декорация", "decoration"),
    ):
        if marker in lowered:
            return result
    return "element"


def find_ui_trees(value: Any) -> list[list[dict[str, Any]]]:
    trees: list[list[dict[str, Any]]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"actual", "tree", "result"} and isinstance(child, list) and child and all(
                isinstance(item, dict) and "level" in item for item in child
            ):
                trees.append(child)
            else:
                trees.extend(find_ui_trees(child))
    elif isinstance(value, list):
        for child in value:
            trees.extend(find_ui_trees(child))
    return trees


def normalize_ui_tree(tree: list[dict[str, Any]]) -> dict[str, Any]:
    elements = []
    tables = []
    stack: list[dict[str, Any]] = []
    for raw in tree:
        item = {
            "kind": _kind(str(raw.get("type", ""))),
            "name": raw.get("name"),
            "title": raw.get("title"),
            "formName": raw.get("formName"),
            "selector": _selector(raw),
        }
        level = max(1, int(raw.get("level", 1)))
        stack = stack[: level - 1]
        item["path"] = [str(parent.get("name") or parent.get("title") or parent["kind"]) for parent in stack]
        stack.append(item)
        elements.append(item)
        if item["kind"] == "table":
            tables.append({"name": item["name"], "title": item["title"], "selector": item["selector"], "columns": []})
        elif tables and item["kind"] == "field" and len(stack) >= 2 and stack[-2]["kind"] == "table":
            tables[-1]["columns"].append({"name": item["name"], "title": item["title"], "selector": item["selector"]})
    return {
        "schemaVersion": 1,
        "elements": [item for item in elements if item["selector"]],
        "tables": tables,
        "selectorPolicy": ["objectName", "formName", "title"],
    }


def normalize_ui_report(report: dict[str, Any]) -> dict[str, Any]:
    trees = find_ui_trees(report.get("managerResult", report))
    normalized = [normalize_ui_tree(tree) for tree in trees]
    return {
        "ok": report.get("ok", False),
        "runId": report.get("runId"),
        "screens": normalized,
        "artifacts": report.get("artifacts", {}),
    }


def diagnose_ui_failure(report: dict[str, Any]) -> dict[str, Any] | None:
    if report.get("ok"):
        return None
    message = str((report.get("error") or {}).get("message", ""))
    lowered = message.lower()
    if "сетев" in lowered or "network" in lowered or "connection" in lowered:
        category = "test-client-connection"
        next_action = "Check client log and retry the same scenario; this is not a selector failure."
    elif "navigation command was rejected" in lowered:
        category = "navigation-rejected"
        next_action = "Use inspectCommandInterface or a supported direct TestClient command; the target form was never opened."
    elif "ambiguous" in lowered:
        category = "ambiguous-selector"
        next_action = "Use objectName from agentUi instead of title."
    elif "not found" in lowered or "не найден" in lowered:
        category = "selector-not-found"
        next_action = "Run ui-inspect for the same form and choose an objectName selector."
    elif "timed out" in lowered or "timeout" in lowered:
        category = "timeout"
        next_action = "Inspect progress.stepElapsedSeconds and the pre-navigation UI tree."
    else:
        category = "ui-step-failure"
        next_action = "Open diagnostics artifact and inspect the last successful step."
    return {"category": category, "message": message, "nextAction": next_action}
