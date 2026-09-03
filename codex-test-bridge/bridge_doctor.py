#!/usr/bin/env python3
"""Read-only environment checks for the HTTP bridge and native UI worker."""

from __future__ import annotations

import csv
import io
import os
import shutil
import socket
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from ui_worker import WindowsHiddenDesktopBackend, expand, load_worker_config


def _check(name: str, ok: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, **details}


def _environment_values(config: dict[str, Any]) -> dict[str, str]:
    values = {}
    for alias, variable in config.get("environmentPlaceholders", {}).items():
        if variable in os.environ:
            values[alias] = os.environ[variable]
    return values


def run_doctor(
    request_health: Callable[[], dict[str, Any]], request_capabilities: Callable[[], dict[str, Any]],
    worker_config_path: str = "",
) -> dict[str, Any]:
    checks = []
    try:
        health = request_health()
        checks.append(_check("http-health", bool(health.get("ok")), metadataName=health.get("metadataName")))
    except Exception as exc:
        checks.append(_check("http-health", False, error=f"{type(exc).__name__}: {exc}"))
    try:
        capabilities = request_capabilities()
        checks.append(_check(
            "capabilities-v2", bool(capabilities.get("ok")) and capabilities.get("contractVersion", 0) >= 2,
            variant=capabilities.get("variant"), bridgeVersion=capabilities.get("bridgeVersion"),
            uiWorker=(capabilities.get("ui") or {}).get("worker"),
        ))
    except Exception as exc:
        checks.append(_check("capabilities-v2", False, error=f"{type(exc).__name__}: {exc}"))

    warnings = []
    if worker_config_path:
        try:
            config = load_worker_config(worker_config_path)
            checks.append(_check("worker-config", True, backend=config.get("backend", "auto")))
            values = _environment_values(config)
            values.update({
                "runId": "doctor", "jobId": "doctor", "scenario": "doctor.ui.json",
                "artifactDir": "artifacts", "testPort": str(config.get("testPort", 1538) or 1538),
                "scenarioBase64": "", "clientLog": "client.log", "managerLog": "manager.log",
            })
            missing = sorted(set(config.get("environmentPlaceholders", {}).values()) - set(os.environ))
            checks.append(_check("worker-environment", not missing, missing=missing))
            if not missing:
                for command_name in ("clientCommand", "managerCommand"):
                    executable = Path(expand(config[command_name], values)[0])
                    checks.append(_check(f"{command_name}-executable", executable.is_file(), executable=executable.name))
            port = config.get("testPort", "auto")
            if port in (None, "", 0, "0", "auto"):
                checks.append(_check("test-port", True, mode="auto"))
            else:
                try:
                    with socket.socket() as probe:
                        probe.bind((str(config.get("testHost", "127.0.0.1")), int(port)))
                    checks.append(_check("test-port", True, port=int(port)))
                except OSError as exc:
                    checks.append(_check("test-port", False, port=int(port), error=str(exc)))
            backend = config.get("backend", "auto")
            if os.name == "nt" and backend in {"auto", "windowsDesktop"}:
                desktop = WindowsHiddenDesktopBackend({}, None, "CodexDoctor-" + uuid.uuid4().hex)
                desktop.close()
                checks.append(_check("hidden-desktop", True, backend="windowsDesktop"))
            elif backend == "xvfb" or (backend == "auto" and os.name != "nt"):
                checks.append(_check("hidden-desktop", shutil.which("Xvfb") is not None, backend="xvfb"))
        except Exception as exc:
            checks.append(_check("worker-config", False, error=f"{type(exc).__name__}: {exc}"))

    if os.name == "nt":
        try:
            output = subprocess.check_output(["tasklist", "/fo", "csv", "/nh"], text=True, encoding="utf-8", errors="replace")
            count = sum(1 for row in csv.reader(io.StringIO(output)) if row and row[0].casefold() in {"1cv8.exe", "1cv8c.exe"})
            if count:
                warnings.append({"name": "running-1c-processes", "count": count, "message": "May include legitimate user sessions; doctor does not stop them."})
        except Exception:
            pass
    return {"ok": all(item["ok"] for item in checks), "checks": checks, "warnings": warnings}
