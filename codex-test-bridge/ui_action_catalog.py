"""Machine-readable contract for native CodexTestBridge UI actions."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).with_name("ui-actions.matrix.json")


class UiActionCatalogError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_ui_action_catalog(path: str | Path = CATALOG_PATH) -> dict[str, Any]:
    source = Path(path)
    try:
        catalog = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UiActionCatalogError(f"UI action catalog cannot be read: {source}") from exc
    actions = catalog.get("actions") if isinstance(catalog, dict) else None
    if not isinstance(actions, list) or not actions:
        raise UiActionCatalogError("UI action catalog must contain a non-empty actions array")
    element_types = catalog.get("elementTypes")
    if not isinstance(element_types, list) or not element_types or not all(
        isinstance(element_type, str) and element_type for element_type in element_types
    ):
        raise UiActionCatalogError("UI action catalog has no elementTypes")
    known_element_types = set(element_types)
    names: set[str] = set()
    case_ids: set[str] = set()
    variant_ids: set[str] = set()
    for index, action in enumerate(actions, 1):
        if not isinstance(action, dict):
            raise UiActionCatalogError(f"UI action catalog row {index} must be an object")
        name = action.get("name")
        if not isinstance(name, str) or not name:
            raise UiActionCatalogError(f"UI action catalog row {index} has no name")
        if name in names:
            raise UiActionCatalogError(f"Duplicate UI action: {name}")
        names.add(name)
        visibility = action.get("visibility")
        if visibility not in {"public", "internal", "alias"}:
            raise UiActionCatalogError(f"UI action {name} has invalid visibility")
        coverage = action.get("coverage")
        if coverage not in {"fixture", "integration", "platform", "internal", "alias"}:
            raise UiActionCatalogError(f"UI action {name} has invalid coverage")
        if visibility == "public" and coverage != "fixture":
            raise UiActionCatalogError(
                f"Public UI action {name} must have executable fixture coverage"
            )
        if visibility == "internal" and coverage != "internal":
            raise UiActionCatalogError(f"Internal UI action {name} must use internal coverage")
        if visibility == "alias" and coverage != "alias":
            raise UiActionCatalogError(f"UI action alias {name} must use alias coverage")
        if not isinstance(action.get("scope"), str) or not action["scope"]:
            raise UiActionCatalogError(f"UI action {name} has no scope")
        action_element_types = action.get("elementTypes")
        if not isinstance(action_element_types, list) or not set(action_element_types) <= known_element_types:
            raise UiActionCatalogError(f"UI action {name} has invalid elementTypes")
        backend_element_types = action.get("backendElementTypes", {})
        if not isinstance(backend_element_types, dict):
            raise UiActionCatalogError(f"UI action {name} has invalid backendElementTypes")
        for backend, supported_types in backend_element_types.items():
            if backend not in {"xvfb", "windowsDesktop"} or not isinstance(supported_types, list):
                raise UiActionCatalogError(f"UI action {name} has invalid backendElementTypes")
            if not set(supported_types) <= set(action_element_types):
                raise UiActionCatalogError(f"UI action {name} backendElementTypes exceed elementTypes")
        backends = action.get("backends")
        if not isinstance(backends, list) or not backends or not set(backends) <= {"xvfb", "windowsDesktop"}:
            raise UiActionCatalogError(f"UI action {name} has invalid backends")
        cases = action.get("cases")
        if not isinstance(cases, list) or not cases or not all(isinstance(case, str) and case for case in cases):
            raise UiActionCatalogError(f"UI action {name} has no conformance cases")
        case_ids.update(cases)
        variants = action.get("variants", [])
        if not isinstance(variants, list):
            raise UiActionCatalogError(f"UI action {name} has invalid variants")
        local_variant_ids: set[str] = set()
        for variant in variants:
            if not isinstance(variant, dict):
                raise UiActionCatalogError(f"UI action {name} has an invalid variant")
            variant_id = variant.get("id")
            match = variant.get("match")
            if not isinstance(variant_id, str) or not variant_id:
                raise UiActionCatalogError(f"UI action {name} has a variant without id")
            if variant_id in local_variant_ids:
                raise UiActionCatalogError(f"UI action {name} has duplicate variant {variant_id}")
            if not isinstance(match, dict) or not match:
                raise UiActionCatalogError(f"UI action {name} variant {variant_id} has no match")
            if not all(isinstance(key, str) and key for key in match):
                raise UiActionCatalogError(f"UI action {name} variant {variant_id} has invalid match keys")
            local_variant_ids.add(variant_id)
            variant_ids.add(f"{name}.{variant_id}")
    for action in actions:
        alias_of = action.get("aliasOf")
        if action["visibility"] == "alias" and alias_of not in names:
            raise UiActionCatalogError(f"UI action alias {action['name']} refers to an unknown action")
    catalog["caseIds"] = sorted(case_ids)
    catalog["variantIds"] = sorted(variant_ids)
    return catalog


def action_names(*, include_internal: bool = True, include_aliases: bool = True) -> set[str]:
    result = set()
    for action in load_ui_action_catalog()["actions"]:
        if action["visibility"] == "internal" and not include_internal:
            continue
        if action["visibility"] == "alias" and not include_aliases:
            continue
        result.add(action["name"])
    return result


def public_action_names(*, include_aliases: bool = False) -> set[str]:
    return action_names(include_internal=False, include_aliases=include_aliases)


def action_rows() -> dict[str, dict[str, Any]]:
    return {action["name"]: action for action in load_ui_action_catalog()["actions"]}
