"""Strict cross-platform discovery of 1C:Enterprise runtime components."""

from __future__ import annotations

import glob
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class RuntimeResolutionError(RuntimeError):
    """Raised when a requested 1C runtime component cannot be resolved."""


def mask_sensitive_arguments(arguments: Sequence[str]) -> list[str]:
    """Return command arguments with 1C password values masked."""
    masked: list[str] = []
    hide_next = False
    for argument in arguments:
        if hide_next:
            masked.append("***")
            hide_next = False
        elif argument in ("/P", "--password"):
            masked.append(argument)
            hide_next = True
        elif argument.startswith("/P") and len(argument) > 2:
            masked.append("/P***")
        elif argument.startswith("--password="):
            masked.append("--password=***")
        else:
            masked.append(argument)
    return masked


@dataclass(frozen=True)
class RuntimeComponent:
    path: str
    bin_dir: str
    version: str | None


_ENV_NAMES = {
    "1cv8": ("ONEC_1CV8_PATH", "CODEX_1C_EXECUTABLE"),
    "ibcmd": ("ONEC_IBCMD_PATH", "CODEX_IBCMD"),
    "webinst": ("ONEC_WEBINST_PATH",),
    "wsap": ("ONEC_WSAP_MODULE_PATH",),
}

_WINDOWS_NAMES = {
    "1cv8": "1cv8.exe",
    "ibcmd": "ibcmd.exe",
    "webinst": "webinst.exe",
    "wsap": "wsap24.dll",
}

_LINUX_NAMES = {
    "1cv8": "1cv8",
    "ibcmd": "ibcmd",
    "webinst": "webinst",
    "wsap": "wsap24.so",
}


def _platform_name() -> str:
    return "windows" if os.name == "nt" else "linux"


def _component_name(kind: str, platform_name: str) -> str:
    names = _WINDOWS_NAMES if platform_name == "windows" else _LINUX_NAMES
    return names[kind]


def _standard_patterns(kind: str, platform_name: str) -> Sequence[str]:
    name = _component_name(kind, platform_name)
    if platform_name == "windows":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        return (os.path.join(program_files, "1cv8", "*", "bin", name),)
    return (
        os.path.join("/opt/1cv8/x86_64", "*", name),
        os.path.join("/opt/1cv8/x86_64", "*", "bin", name),
    )


def _version_key(path: str) -> tuple[int, ...]:
    version = detect_version(path)
    if version is None:
        return ()
    return tuple(int(part) for part in version.split("."))


def detect_version(path: str | os.PathLike[str]) -> str | None:
    """Extract a dotted platform version from a component path."""
    for part in reversed(Path(path).parts):
        if re.fullmatch(r"\d+(?:\.\d+){2,3}", part):
            return part
    return None


def onec_process_env(
    overrides: Mapping[str, str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an isolated environment suitable for starting 1C processes."""
    result = dict(os.environ if environ is None else environ)
    if overrides:
        result.update(overrides)

    if sys.platform.startswith("linux"):
        configured = result.get("GDK_BACKEND", "")
        backends = {item.strip().casefold() for item in configured.split(",") if item.strip()}
        if "x11" not in backends:
            result["GDK_BACKEND"] = "x11"
    return result


def _validate_candidate(kind: str, value: str, source: str, platform_name: str) -> str:
    candidate = os.path.abspath(os.path.expanduser(os.path.expandvars(value)))
    if os.path.isdir(candidate):
        candidate = os.path.join(candidate, _component_name(kind, platform_name))

    if not os.path.isfile(candidate):
        raise RuntimeResolutionError(
            f"{_component_name(kind, platform_name)} not found at {candidate} ({source})"
        )
    if kind != "wsap" and platform_name != "windows" and not os.access(candidate, os.X_OK):
        raise RuntimeResolutionError(f"{candidate} is not executable ({source})")
    return os.path.normpath(candidate)


def resolve_component(
    kind: str,
    explicit: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> RuntimeComponent:
    """Resolve a component strictly from an argument, environment, or standard paths."""
    if kind not in _ENV_NAMES:
        raise ValueError(f"Unknown 1C runtime component: {kind}")

    platform_name = _platform_name()
    if explicit:
        path = _validate_candidate(kind, os.fspath(explicit), "explicit argument", platform_name)
        return RuntimeComponent(path, os.path.dirname(path), detect_version(path))

    env = os.environ if environ is None else environ
    for env_name in _ENV_NAMES[kind]:
        value = env.get(env_name)
        if value:
            path = _validate_candidate(kind, value, env_name, platform_name)
            return RuntimeComponent(path, os.path.dirname(path), detect_version(path))

    found = {
        os.path.normpath(candidate)
        for pattern in _standard_patterns(kind, platform_name)
        for candidate in glob.glob(pattern)
        if os.path.isfile(candidate)
    }
    if kind != "wsap" and platform_name != "windows":
        found = {candidate for candidate in found if os.access(candidate, os.X_OK)}
    if found:
        path = max(found, key=lambda item: (_version_key(item), item))
        return RuntimeComponent(path, os.path.dirname(path), detect_version(path))

    env_hint = " or ".join(_ENV_NAMES[kind])
    raise RuntimeResolutionError(
        f"{_component_name(kind, platform_name)} not found; "
        f"specify an explicit path or set {env_hint}"
    )


def resolve_1cv8(explicit: str | os.PathLike[str] | None = None) -> str:
    return resolve_component("1cv8", explicit).path


def resolve_ibcmd(explicit: str | os.PathLike[str] | None = None) -> str:
    return resolve_component("ibcmd", explicit).path


def resolve_webinst(explicit: str | os.PathLike[str] | None = None) -> str:
    return resolve_component("webinst", explicit).path


def resolve_wsap_module(explicit: str | os.PathLike[str] | None = None) -> str:
    return resolve_component("wsap", explicit).path


def resolve_1cv8_cli(explicit: str | os.PathLike[str] | None = None) -> str:
    """CLI-compatible resolver that reports a concise error and exits."""
    try:
        return resolve_1cv8(explicit)
    except RuntimeResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
