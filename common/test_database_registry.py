"""Resolve and validate the private 1C test database registry."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping


class RegistryResolutionError(RuntimeError):
    """Raised when the test database registry cannot be resolved or read."""


def _is_blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip()


def _expand_environment_variables(value: str, environ: Mapping[str, str]) -> str:
    """Expand both native Python variables and .NET-style %NAME% variables."""

    expanded = value
    for name, replacement in environ.items():
        expanded = expanded.replace(f"%{name}%", replacement)

    # os.path.expandvars always reads os.environ, so temporarily-independent
    # expansion is implemented explicitly for the supplied environment.
    variable = re.compile(r"\$(\w+|\{[^}]+\})")

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        name = token[1:-1] if token.startswith("{") else token
        return environ.get(name, match.group(0))

    return variable.sub(replace, expanded)


def _full_path(value: str, base_path: Path, environ: Mapping[str, str]) -> Path:
    expanded = _expand_environment_variables(value, environ)
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = base_path / candidate
    return Path(os.path.abspath(candidate))


def _read_json(path: Path, description: str) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryResolutionError(f"Cannot read {description}: {exc}") from exc


def load_registry(path: str | os.PathLike[str], source: str = "registry") -> dict[str, Any]:
    """Read a UTF-8 registry and require a JSON object with a databases array."""

    candidate = Path(path)
    registry = _read_json(candidate, f"test database registry selected by {source}")
    if not isinstance(registry, dict) or not isinstance(registry.get("databases"), list):
        raise RegistryResolutionError(
            f"Test database registry selected by {source} has no databases array."
        )
    return registry


def resolve_registry(
    registry_path: str | os.PathLike[str] | None = None,
    local_config_path: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
    home: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the first configured registry source and validate its contents."""

    env = os.environ if environ is None else environ
    current_path = Path.cwd() if cwd is None else Path(cwd)

    explicit = os.fspath(registry_path) if registry_path is not None else ""
    configured = env.get("CODEX_1C_TEST_DATABASES", "")
    if not _is_blank(explicit):
        source = "-RegistryPath"
        candidate = _full_path(explicit, current_path, env)
    elif not _is_blank(configured):
        source = "CODEX_1C_TEST_DATABASES"
        candidate = _full_path(configured, current_path, env)
    else:
        local_value = os.fspath(local_config_path) if local_config_path is not None else ""
        if _is_blank(local_value):
            codex_home = env.get("CODEX_HOME", "")
            if _is_blank(codex_home):
                home_path = Path.home() if home is None else Path(home)
                codex_root = home_path / ".codex"
            else:
                codex_root = _full_path(codex_home, current_path, env)
            local_path = codex_root / "1c" / "local.json"
        else:
            local_path = _full_path(local_value, current_path, env)

        local_path = Path(os.path.abspath(local_path))
        if not local_path.is_file():
            raise RegistryResolutionError(
                "Test database registry is not configured. Specify -RegistryPath, "
                "CODEX_1C_TEST_DATABASES, or create the local Codex 1C config."
            )
        local_config = _read_json(local_path, "local Codex 1C config")
        test_databases_path = (
            local_config.get("testDatabasesPath") if isinstance(local_config, dict) else None
        )
        if _is_blank(test_databases_path):
            raise RegistryResolutionError("Local Codex 1C config has no testDatabasesPath.")
        source = "local Codex 1C config"
        candidate = _full_path(test_databases_path, local_path.parent, env)

    if not candidate.is_file():
        raise RegistryResolutionError(
            f"Test database registry selected by {source} does not exist."
        )

    load_registry(candidate, source)
    return Path(os.path.abspath(candidate))
