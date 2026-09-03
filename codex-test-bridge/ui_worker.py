#!/usr/bin/env python3
"""Isolated process worker for native 1C /TestClient and /TestManager UI tests."""

from __future__ import annotations

import ctypes
import argparse
import copy
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
import base64
import urllib.error
import urllib.request
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hidden_desktop_capture import capture_window
from uia_runner import run_uia_bridge_request, run_uia_steps


class UiWorkerError(RuntimeError):
    pass


PLACEHOLDER = re.compile(r"\{([A-Za-z][A-Za-z0-9]*)}")
DEFAULT_SECRET_FLAGS = ["/P", "/N", "/S", "/F", "--password", "--token", "--user", "--server", "--database-path"]
DEFAULT_1C_STARTUP_FLAGS = ["/DisableStartupDialogs", "/DisableStartupMessages", "/DisableSplash"]
NATIVE_UI_ACTIONS: set[str] = {
    "assertConnected", "openNavigationLink", "executeCommand", "nextWindow", "activateWindow",
    "waitForm", "waitFormClosed", "waitElement", "assertElement", "inspectUi", "inspectUI", "inspectTable",
    "inspectCommandInterface", "clickCommandInterface", "activateForm", "activateElement",
    "inputText", "selectReference", "selectFromDropdown", "setCheckbox", "openChoice",
    "selectTableRow", "assertTableRow", "inputTableCell", "click", "assertField",
    "handleDialog", "closeForm",
}
NATIVE_UI_ROOT_FIELDS = {
    "$schema", "name", "navigationLink", "dismissStartupDialogs", "startupDialogAttempts",
    "startupDialogButtons", "startupSettleSeconds", "uiaBeforeSteps", "uiaSteps", "steps",
}
NATIVE_UI_STEP_FIELDS = {
    "action", "name", "command", "link", "uuid", "kind", "metadataName", "form", "saveAs",
    "title", "objectName", "formName", "timeout", "attempts", "strategy", "match", "direction",
    "depth", "value", "expected", "exists", "visible", "enabled", "readOnly", "checked", "strict",
    "finishRow", "onChangeWait", "replace", "waitClosed", "optional", "elementType", "onPrompt",
    "dialogTitle", "promptTimeout", "row", "choiceRow", "element", "field", "button",
    "dialogButton", "table", "choiceTable", "targetForm", "choiceForm",
}
NATIVE_UI_SELECTOR_FIELDS = {"title", "objectName", "formName", "metadataFullName", "saveAs", "timeout", "pollingInterval"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def write_atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def navigation_ref_from_uuid(value: str) -> str:
    """Convert a standard 1C UUID to the byte-group order used by e1cib ref."""
    match = re.fullmatch(
        r"([0-9a-fA-F]{8})-([0-9a-fA-F]{4})-([0-9a-fA-F]{4})-([0-9a-fA-F]{4})-([0-9a-fA-F]{12})",
        value,
    )
    if not match:
        raise UiWorkerError(f"Invalid UUID for navigation link: {value}")
    groups = match.groups()
    return "".join(groups[index] for index in (3, 4, 2, 1, 0)).lower()


def prepare_native_ui_scenario(data: Any) -> dict[str, Any]:
    """Validate a native UI scenario and expand safe navigation-link shorthand."""
    if not isinstance(data, dict):
        raise UiWorkerError("UI scenario must be a JSON object")
    unknown_root = sorted(set(data) - NATIVE_UI_ROOT_FIELDS)
    if unknown_root:
        raise UiWorkerError(f"UI scenario has unknown fields: {', '.join(unknown_root)}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise UiWorkerError("UI scenario steps must be a non-empty array")
    result = copy.deepcopy(data)
    for index, step in enumerate(result["steps"], 1):
        if not isinstance(step, dict):
            raise UiWorkerError(f"UI scenario step {index} must be a JSON object")
        unknown_step = sorted(set(step) - NATIVE_UI_STEP_FIELDS)
        if unknown_step:
            raise UiWorkerError(f"UI scenario step {index} has unknown fields: {', '.join(unknown_step)}")
        action = step.get("action")
        if action not in NATIVE_UI_ACTIONS:
            raise UiWorkerError(f"UI scenario step {index} has unsupported action: {action}")
        if action == "openNavigationLink":
            if not step.get("link") and step.get("uuid"):
                kind = step.get("kind")
                metadata_name = step.get("metadataName")
                kind_names = {"catalog": "Справочник", "document": "Документ"}
                if kind not in kind_names or not isinstance(metadata_name, str) or not metadata_name:
                    raise UiWorkerError(
                        f"UI scenario step {index}: uuid shorthand requires kind=catalog|document and metadataName"
                    )
                ref = navigation_ref_from_uuid(str(step["uuid"]))
                step["link"] = f"e1cib/data/{kind_names[kind]}.{metadata_name}?ref={ref}"
            if not isinstance(step.get("link"), str) or not step["link"]:
                raise UiWorkerError(f"UI scenario step {index}: openNavigationLink requires link or uuid shorthand")
        for selector_name in ("element", "field", "button", "table", "targetForm", "choiceForm"):
            selector = step.get(selector_name)
            if selector is None:
                continue
            if not isinstance(selector, dict):
                raise UiWorkerError(f"UI scenario step {index}: {selector_name} must be a JSON object")
            unknown_selector = sorted(set(selector) - NATIVE_UI_SELECTOR_FIELDS)
            if unknown_selector:
                raise UiWorkerError(
                    f"UI scenario step {index}: {selector_name} has unknown fields: {', '.join(unknown_selector)}"
                )
    return result


def expand(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [expand(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, variables) for key, item in value.items()}
    if not isinstance(value, str):
        return value
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise UiWorkerError(f"Unknown command placeholder: {name}")
        return variables[name]

    return PLACEHOLDER.sub(replace, value)


def load_worker_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as source:
        config = json.load(source)
    validate_worker_config(config)
    return config


def validate_worker_config(config: Any) -> None:
    if not isinstance(config, dict):
        raise UiWorkerError("Worker config must be a JSON object")
    backend = config.get("backend", "auto")
    if backend not in {"auto", "windowsDesktop", "xvfb", "process"}:
        raise UiWorkerError(f"Unsupported UI backend: {backend}")
    transport = config.get("resultTransport", "bridgeJob" if config.get("bridgeBaseUrl") else "file")
    if transport not in {"bridgeJob", "inlineLog", "file"}:
        raise UiWorkerError(f"Unsupported resultTransport: {transport}")
    if transport == "bridgeJob" and not isinstance(config.get("bridgeBaseUrl"), str):
        raise UiWorkerError("bridgeBaseUrl is required for bridgeJob result transport")
    for name in ("clientCommand", "managerCommand"):
        command = config.get(name)
        if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
            raise UiWorkerError(f"{name} must be a non-empty array of strings")
    test_port_value = config.get("testPort", 1538)
    if test_port_value not in (None, "", 0, "0", "auto"):
        if isinstance(test_port_value, bool) or not isinstance(test_port_value, (int, float)) or test_port_value <= 0:
            raise UiWorkerError("testPort must be greater than zero or auto")
    for name, default in (
        ("startupTimeoutSeconds", 60), ("timeoutSeconds", 900),
        ("heartbeatIntervalSeconds", 10), ("progressPollSeconds", 1),
    ):
        value = config.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise UiWorkerError(f"{name} must be greater than zero")
    startup_delay = config.get("startupDelaySeconds", 10)
    if isinstance(startup_delay, bool) or not isinstance(startup_delay, (int, float)) or startup_delay < 0:
        raise UiWorkerError("startupDelaySeconds must be a number >= 0")
    if not isinstance(config.get("probeTestPort", False), bool):
        raise UiWorkerError("probeTestPort must be boolean")
    if not isinstance(config.get("suppressStartupUi", True), bool):
        raise UiWorkerError("suppressStartupUi must be boolean")
    environment = config.get("environment", {})
    if not isinstance(environment, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items()):
        raise UiWorkerError("environment must be an object with string values")
    secret_flags = config.get("secretFlags", [])
    if not isinstance(secret_flags, list) or any(not isinstance(item, str) or not item for item in secret_flags):
        raise UiWorkerError("secretFlags must be an array of non-empty strings")
    environment_placeholders = config.get("environmentPlaceholders", {})
    if not isinstance(environment_placeholders, dict):
        raise UiWorkerError("environmentPlaceholders must be an object")
    for alias, environment_name in environment_placeholders.items():
        if not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", alias):
            raise UiWorkerError(f"Invalid environment placeholder name: {alias}")
        if not isinstance(environment_name, str) or not environment_name:
            raise UiWorkerError(f"Environment variable name is required for placeholder: {alias}")


def redact_command(command: list[str], secret_flags: list[str]) -> list[str]:
    result = list(command)
    normalized = {flag.lower() for flag in [*DEFAULT_SECRET_FLAGS, *secret_flags]}
    for index, argument in enumerate(result):
        lowered = argument.lower()
        if lowered in normalized:
            if index + 1 < len(result):
                result[index + 1] = "***"
            continue
        for flag in normalized:
            if lowered.startswith(flag) and len(argument) > len(flag):
                result[index] = argument[:len(flag)] + "***"
                break
    return result


def suppress_1c_startup_ui(command: list[str]) -> list[str]:
    """Add noninteractive platform startup flags to TestClient/TestManager commands."""
    result = list(command)
    lowered = {argument.lower() for argument in result}
    if "enterprise" not in lowered or not ({"/testclient", "/testmanager"} & lowered):
        return result
    insertion_index = next(
        (index for index, argument in enumerate(result) if argument.lower() in {"/testclient", "/testmanager"}),
        len(result),
    )
    missing = [flag for flag in DEFAULT_1C_STARTUP_FLAGS if flag.lower() not in lowered]
    result[insertion_index:insertion_index] = missing
    return result


class RunningProcess:
    pid: int

    def poll(self) -> int | None:
        raise NotImplementedError

    def terminate(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class SubprocessHandle(RunningProcess):
    def __init__(self, process: subprocess.Popen[bytes]):
        self.process = process
        self.pid = process.pid

    def poll(self) -> int | None:
        return self.process.poll()

    def terminate(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)


class ProcessBackend:
    name = "process"

    def __init__(self, environment: dict[str, str], working_directory: str | None):
        self.environment = environment
        self.working_directory = working_directory

    def start(self, command: list[str]) -> RunningProcess:
        env = os.environ.copy()
        env.update(self.environment)
        process = subprocess.Popen(
            command,
            cwd=self.working_directory or None,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return SubprocessHandle(process)

    def close(self) -> None:
        pass


class WindowsProcessHandle(RunningProcess):
    STILL_ACTIVE = 259

    def __init__(self, kernel32: Any, process_handle: int, thread_handle: int, pid: int):
        self.kernel32 = kernel32
        self.process_handle = process_handle
        self.thread_handle = thread_handle
        self.pid = pid

    def poll(self) -> int | None:
        code = wintypes.DWORD()
        if not self.kernel32.GetExitCodeProcess(self.process_handle, ctypes.byref(code)):
            raise ctypes.WinError()
        return None if code.value == self.STILL_ACTIVE else int(code.value)

    def terminate(self) -> None:
        if self.poll() is None:
            if not self.kernel32.TerminateProcess(self.process_handle, 1):
                raise ctypes.WinError()
            self.kernel32.WaitForSingleObject(self.process_handle, 10_000)

    def close(self) -> None:
        if self.thread_handle:
            self.kernel32.CloseHandle(self.thread_handle)
            self.thread_handle = 0
        if self.process_handle:
            self.kernel32.CloseHandle(self.process_handle)
            self.process_handle = 0


class WindowsHiddenDesktopBackend:
    name = "windowsDesktop"
    GENERIC_ALL = 0x10000000
    CREATE_UNICODE_ENVIRONMENT = 0x00000400

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
            ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
        ]

    def __init__(self, environment: dict[str, str], working_directory: str | None, desktop_name: str):
        if os.name != "nt":
            raise UiWorkerError("windowsDesktop backend is available only on Windows")
        self.environment = environment
        self.working_directory = working_directory
        self.desktop_name = desktop_name
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user32.CreateDesktopW.restype = wintypes.HANDLE
        self.user32.CreateDesktopW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        ]
        self.user32.CloseDesktop.restype = wintypes.BOOL
        self.user32.CloseDesktop.argtypes = [wintypes.HANDLE]
        self.kernel32.CreateProcessW.restype = wintypes.BOOL
        self.kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
            wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
            ctypes.POINTER(self.STARTUPINFO), ctypes.POINTER(self.PROCESS_INFORMATION),
        ]
        self.kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel32.TerminateProcess.restype = wintypes.BOOL
        self.kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.desktop = self.user32.CreateDesktopW(desktop_name, None, None, 0, self.GENERIC_ALL, None)
        if not self.desktop:
            raise ctypes.WinError(ctypes.get_last_error())

    def start(self, command: list[str]) -> RunningProcess:
        startup = self.STARTUPINFO()
        startup.cb = ctypes.sizeof(startup)
        startup.lpDesktop = f"WinSta0\\{self.desktop_name}"
        process_info = self.PROCESS_INFORMATION()
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        environment = os.environ.copy()
        environment.update(self.environment)
        environment_block = "\0".join(f"{key}={value}" for key, value in sorted(environment.items(), key=lambda item: item[0].upper())) + "\0\0"
        environment_buffer = ctypes.create_unicode_buffer(environment_block)
        success = self.kernel32.CreateProcessW(
            None, command_line, None, None, False, self.CREATE_UNICODE_ENVIRONMENT,
            environment_buffer, self.working_directory or None,
            ctypes.byref(startup), ctypes.byref(process_info),
        )
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())
        return WindowsProcessHandle(
            self.kernel32,
            process_info.hProcess,
            process_info.hThread,
            process_info.dwProcessId,
        )

    def close(self) -> None:
        if self.desktop:
            self.user32.CloseDesktop(self.desktop)
            self.desktop = None


class XvfbBackend(ProcessBackend):
    name = "xvfb"

    def __init__(self, environment: dict[str, str], working_directory: str | None, display: int):
        if os.name == "nt":
            raise UiWorkerError("xvfb backend is available only on Unix-like systems")
        env = dict(environment)
        env["DISPLAY"] = f":{display}"
        super().__init__(env, working_directory)
        self.xvfb = subprocess.Popen(
            ["Xvfb", f":{display}", "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        socket_path = Path(f"/tmp/.X11-unix/X{display}")
        deadline = time.monotonic() + 15
        while not socket_path.exists():
            if self.xvfb.poll() is not None:
                raise UiWorkerError("Xvfb exited during startup")
            if time.monotonic() >= deadline:
                self.xvfb.terminate()
                raise UiWorkerError("Xvfb startup timed out")
            time.sleep(0.1)

    def close(self) -> None:
        if self.xvfb.poll() is None:
            self.xvfb.terminate()
            try:
                self.xvfb.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.xvfb.kill()


def wait_for_port(host: str, port: int, timeout: float, process: RunningProcess) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise UiWorkerError(f"Test client exited before opening port {port}, exit code {exit_code}")
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.25)
    raise UiWorkerError(f"Test client did not open {host}:{port} in {timeout:g} seconds")


def choose_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def wait_for_startup(process: RunningProcess, delay: float) -> None:
    deadline = time.monotonic() + delay
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise UiWorkerError(f"Test client exited during startup, exit code {exit_code}")
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))


def wait_for_process(process: RunningProcess, timeout: float) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            return exit_code
        time.sleep(0.25)
    raise UiWorkerError(f"Test manager timed out after {timeout:g} seconds")


def emit_progress(events: list[dict[str, Any]], artifact_file: Path, stage: str, message: str, **fields: Any) -> None:
    event = {
        "stage": stage,
        "message": message,
        "at": utc_now().isoformat(),
        **fields,
    }
    events.append(event)
    print(f"[ui:{stage}] {message}", flush=True)
    snapshot_status = stage if stage in {"passed", "failed"} else "running"
    snapshot = {"status": snapshot_status, "lastHeartbeatAt": event["at"], "current": event, "events": events}
    write_atomic_json(artifact_file, snapshot)


def bridge_command(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    url = str(config["bridgeBaseUrl"]).rstrip("/") + "/command"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    headers.update(config.get("bridgeHeaders", {}))
    username = config.get("bridgeUsername")
    password = config.get("bridgePassword", "")
    if username:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=float(config.get("bridgeTimeoutSeconds", 30))) as response:
            result = json.loads(response.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8-sig", errors="replace")
        raise UiWorkerError(f"Bridge command failed with HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise UiWorkerError(f"Bridge command failed: {exc}") from exc
    if not isinstance(result, dict):
        raise UiWorkerError("Bridge command returned a non-object JSON response")
    return result


def is_scenario_result(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    status = value.get("status")
    if status in {"running", "uia-request", "uia-response"}:
        return False
    return "ok" in value or isinstance(value.get("steps"), list)


def create_backend(config: dict[str, Any], run_id: str) -> ProcessBackend | WindowsHiddenDesktopBackend | XvfbBackend:
    backend = config.get("backend", "auto")
    if backend == "auto":
        backend = "windowsDesktop" if os.name == "nt" else "xvfb"
    environment = config.get("environment", {})
    working_directory = config.get("workingDirectory")
    if backend == "windowsDesktop":
        return WindowsHiddenDesktopBackend(environment, working_directory, f"Codex1C-{run_id}")
    if backend == "xvfb":
        return XvfbBackend(environment, working_directory, int(config.get("display", 99)))
    return ProcessBackend(environment, working_directory)


def run_ui_worker(config: dict[str, Any], scenario_path: str | Path, artifact_dir: str | Path) -> dict[str, Any]:
    validate_worker_config(config)
    started = utc_now()
    run_id = uuid.uuid4().hex
    artifacts = Path(artifact_dir).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    progress_file = artifacts / "progress.json"
    summary_file = artifacts / "summary.json"
    for stale_name in ("progress.json", "summary.json", "ui-diagnostics.json", "screenshot.bmp"):
        stale_file = artifacts / stale_name
        if stale_file.is_file():
            stale_file.unlink()
    write_atomic_json(summary_file, {
        "runId": run_id, "status": "starting", "startedAt": started.isoformat(), "lastHeartbeatAt": started.isoformat(),
    })
    progress_events: list[dict[str, Any]] = []

    def progress(stage: str, message: str, **fields: Any) -> None:
        emit_progress(progress_events, progress_file, stage, message, runId=run_id, **fields)

    progress("starting", "UI worker started")
    source_scenario = Path(scenario_path).resolve()
    if not source_scenario.is_file():
        raise UiWorkerError(f"UI scenario file does not exist: {source_scenario}")
    transport = config.get("resultTransport", "bridgeJob" if config.get("bridgeBaseUrl") else "file")
    scenario_data = None
    scenario_text = ""
    scenario = source_scenario
    if source_scenario.suffix.lower() == ".json":
        scenario_data = prepare_native_ui_scenario(json.loads(source_scenario.read_text(encoding="utf-8-sig")))
        scenario_data.pop("$schema", None)
        scenario = artifacts / f"scenario-{run_id}.ui.json"
        scenario.write_text(json.dumps(scenario_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if transport in {"bridgeJob", "inlineLog"}:
        if scenario_data is None:
            scenario_data = json.loads(source_scenario.read_text(encoding="utf-8-sig"))
        scenario_text = json.dumps(scenario_data, ensure_ascii=True, separators=(",", ":"))
    client_log = artifacts / f"client-{run_id}.log"
    manager_log = artifacts / f"manager-{run_id}.log"
    configured_test_port = config.get("testPort")
    if configured_test_port in (None, "", 0, "0", "auto"):
        test_port = choose_free_port(str(config.get("testHost", "127.0.0.1")))
    else:
        test_port = int(configured_test_port)
    variables = {
        "runId": run_id,
        "jobId": run_id,
        "scenario": str(source_scenario),
        "artifactDir": str(artifacts),
        "testPort": str(test_port),
        "scenarioBase64": base64.b64encode(scenario_text.encode("ascii")).decode("ascii") if scenario_text else "",
        "clientLog": str(client_log),
        "managerLog": str(manager_log),
    }
    for alias, environment_name in config.get("environmentPlaceholders", {}).items():
        if environment_name not in os.environ:
            raise UiWorkerError(f"Required environment variable is not set: {environment_name}")
        variables[alias] = os.environ[environment_name]
    client_command = expand(config["clientCommand"], variables)
    manager_command = expand(config["managerCommand"], variables)
    if config.get("suppressStartupUi", True):
        client_command = suppress_1c_startup_ui(client_command)
        manager_command = suppress_1c_startup_ui(manager_command)
    result_file = None
    if transport == "file":
        result_file_value = expand(config.get("resultFile", "{artifactDir}/manager-result-{runId}.json"), variables)
        result_file = Path(result_file_value)
        if result_file.exists():
            raise UiWorkerError(f"Result file already exists; use a unique path with {{runId}}: {result_file}")
        result_file.parent.mkdir(parents=True, exist_ok=True)
    secret_flags = config.get("secretFlags", [])
    client: RunningProcess | None = None
    manager: RunningProcess | None = None
    backend = None
    status = "failed"
    error = None
    manager_result = None
    manager_exit_code = None
    screenshot_file = None
    screenshot_error = None
    uia_before_results = None
    uia_results = None
    uia_bridge_results: list[dict[str, Any]] = []
    runtime_config = copy.deepcopy(config)

    try:
        runtime_config = expand(runtime_config, variables)
        if transport == "bridgeJob":
            progress("startup", "Creating bridge job")
            bridge_command(runtime_config, {
                "command": "uiJobCreate", "jobId": run_id, "scenario": scenario_text,
            })
        backend = create_backend(runtime_config, run_id)
        progress("startup", f"Starting TestClient on isolated {backend.name} backend")
        client = backend.start(client_command)
        if config.get("probeTestPort", False):
            wait_for_port(
                str(config.get("testHost", "127.0.0.1")),
                test_port,
                float(config.get("startupTimeoutSeconds", 60)),
                client,
            )
        else:
            wait_for_startup(client, float(config.get("startupDelaySeconds", 10)))
        progress("connect", "TestClient startup completed", clientPid=client.pid)
        if (
            isinstance(scenario_data, dict)
            and scenario_data.get("uiaBeforeSteps")
            and isinstance(backend, WindowsHiddenDesktopBackend)
            and client is not None
        ):
            progress("uia", "Running pre-native UI Automation steps")
            uia_before_results = run_uia_steps(backend.desktop_name, client.pid, scenario_data["uiaBeforeSteps"])
            if any(step.get("status") != "passed" for step in uia_before_results):
                raise UiWorkerError("A pre-native UI Automation step failed")
        progress("startup", "Starting TestManager")
        manager = backend.start(manager_command)
        progress("running", "TestManager started", managerPid=manager.pid)
        manager_deadline = time.monotonic() + float(config.get("timeoutSeconds", 900))
        heartbeat_interval = float(config.get("heartbeatIntervalSeconds", 10))
        next_heartbeat = time.monotonic() + heartbeat_interval
        next_job_poll = 0.0
        last_progress_signature: tuple[Any, ...] | None = None
        last_partial_result: dict[str, Any] | None = None
        handled_uia_requests: set[str] = set()
        current_step_started = time.monotonic()
        while time.monotonic() < manager_deadline:
            exit_code = manager.poll()
            if exit_code is not None:
                manager_exit_code = exit_code
                break
            now = time.monotonic()
            if transport == "bridgeJob" and now >= next_job_poll:
                next_job_poll = now + float(config.get("progressPollSeconds", 1))
                try:
                    progress_job = bridge_command(runtime_config, {"command": "uiJobGet", "jobId": run_id})
                    progress_text = progress_job.get("result", "")
                    if progress_text:
                        partial = json.loads(progress_text)
                        if isinstance(partial, dict) and partial.get("status") == "uia-request":
                            request_id = str(partial.get("requestId", ""))
                            if request_id and request_id not in handled_uia_requests:
                                handled_uia_requests.add(request_id)
                                progress("uia", f"Running UIA bridge request: {partial.get('action')}", requestId=request_id)
                                if isinstance(backend, WindowsHiddenDesktopBackend) and client is not None:
                                    response = run_uia_bridge_request(backend.desktop_name, client.pid, partial)
                                else:
                                    response = {
                                        "ok": False,
                                        "requestId": request_id,
                                        "status": "uia-response",
                                        "error": "UIA bridge requests require windowsDesktop backend",
                                    }
                                uia_bridge_results.append(response)
                                bridge_command(runtime_config, {
                                    "command": "uiJobSet",
                                    "jobId": run_id,
                                    "status": "uia-response",
                                    "result": json.dumps(response, ensure_ascii=True, separators=(",", ":")),
                                })
                            continue
                        if isinstance(partial, dict) and partial.get("status") == "running":
                            last_partial_result = partial
                            current = partial.get("step") or {}
                            signature = (
                                partial.get("stage"), partial.get("currentStep"),
                                current.get("status"), current.get("action"), current.get("name"),
                            )
                            if signature != last_progress_signature:
                                last_progress_signature = signature
                                current_step_started = now
                                progress(
                                    "running",
                                    f"Step {partial.get('currentStep', 0)}/{partial.get('totalSteps', 0)}: "
                                    f"{current.get('name') or current.get('action') or partial.get('stage')}",
                                    currentStep=partial.get("currentStep"),
                                    totalSteps=partial.get("totalSteps"),
                                    step=current,
                                )
                except Exception:
                    pass
            if now >= next_heartbeat:
                elapsed = round((utc_now() - started).total_seconds())
                if last_partial_result:
                    step_elapsed = round(now - current_step_started)
                    message = (
                        f"Waiting for step {last_partial_result.get('currentStep', 0)}/"
                        f"{last_partial_result.get('totalSteps', 0)}, step elapsed {step_elapsed}s, total {elapsed}s"
                    )
                else:
                    step_elapsed = None
                    message = f"Waiting for TestManager, elapsed {elapsed}s"
                progress("waiting", message, elapsedSeconds=elapsed, stepElapsedSeconds=step_elapsed)
                next_heartbeat = now + heartbeat_interval
            time.sleep(0.25)
        else:
            raise UiWorkerError(f"Test manager timed out after {float(config.get('timeoutSeconds', 900)):g} seconds")
        progress("running", f"TestManager finished with exit code {manager_exit_code}")
        if transport == "bridgeJob":
            result_deadline = time.monotonic() + float(config.get("resultWaitAfterExitSeconds", 30))
            while time.monotonic() < result_deadline:
                job = bridge_command(runtime_config, {"command": "uiJobGet", "jobId": run_id})
                result_text = job.get("result", "")
                if result_text:
                    candidate_result = json.loads(result_text)
                    if is_scenario_result(candidate_result):
                        manager_result = candidate_result
                        break
                time.sleep(float(config.get("progressPollSeconds", 1)))
        elif transport == "inlineLog" and manager_log.exists():
            raw_log = manager_log.read_bytes()
            log_text = ""
            for encoding in ("utf-8-sig", "utf-16", "cp1251"):
                try:
                    log_text = raw_log.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            marker = "CODEX_UI_RESULT:"
            marker_position = log_text.rfind(marker)
            if marker_position >= 0:
                result_text = log_text[marker_position + len(marker):].lstrip()
                manager_result, _ = json.JSONDecoder().raw_decode(result_text)
        elif result_file is not None and result_file.exists():
            with result_file.open("r", encoding="utf-8-sig") as source:
                manager_result = json.load(source)
        manager_ok = manager_exit_code == 0 and isinstance(manager_result, dict)
        if isinstance(manager_result, dict):
            manager_ok = manager_ok and manager_result.get("ok", True)
        status = "passed" if manager_ok else "failed"
        if not manager_ok:
            if manager_result is None:
                if transport == "bridgeJob":
                    target = f"bridge job {run_id}"
                elif transport == "inlineLog":
                    target = f"manager log: {manager_log}"
                else:
                    target = f"result file: {result_file}"
                error = {"type": "MissingResult", "message": f"Test manager did not create a result in {target}"}
            else:
                failed_steps = [step for step in manager_result.get("steps", []) if step.get("status") == "failed"]
                if failed_steps:
                    error = {"type": "ScenarioFailure", "message": str(failed_steps[-1].get("error", "UI step failed"))}
                else:
                    error = {"type": "ManagerFailure", "message": f"Test manager exit code: {manager_exit_code}"}

        post_manager_delay = float(config.get("postManagerDelaySeconds", 0))
        if post_manager_delay > 0 and client is not None:
            wait_for_startup(client, post_manager_delay)

        if isinstance(scenario_data, dict) and scenario_data.get("uiaSteps") and isinstance(backend, WindowsHiddenDesktopBackend) and client is not None:
            uia_results = run_uia_steps(backend.desktop_name, client.pid, scenario_data["uiaSteps"])
            if any(step.get("status") != "passed" for step in uia_results):
                status = "failed"
                error = {"type": "UiaFailure", "message": "A UI Automation fallback step failed"}

        if config.get("captureOnFinish", False) and isinstance(backend, WindowsHiddenDesktopBackend) and client is not None:
            try:
                screenshot_file = str(capture_window(backend.desktop_name, client.pid, artifacts / "screenshot.bmp"))
            except Exception as exc:
                screenshot_error = {"type": type(exc).__name__, "message": str(exc)}
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        progress("failed", str(exc))
    finally:
        progress("cleanup", "Stopping worker-owned TestManager and TestClient processes")
        for process in (manager, client):
            if process is not None:
                try:
                    process.terminate()
                finally:
                    process.close()
        if backend is not None:
            backend.close()
        if transport == "bridgeJob" and not config.get("keepJob", False):
            try:
                bridge_command(runtime_config, {"command": "uiJobDelete", "jobId": run_id})
            except Exception:
                pass

    finished = utc_now()
    diagnostics_file = None
    diagnostics: list[dict[str, Any]] = []
    if isinstance(manager_result, dict):
        for step in manager_result.get("steps", []):
            if isinstance(step, dict) and "diagnostics" in step:
                diagnostics.append({"step": step.get("index"), "action": step.get("action"), "data": step.pop("diagnostics")})
        if diagnostics:
            diagnostics_file = artifacts / "ui-diagnostics.json"
            diagnostics_file.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            for item in diagnostics:
                for step in manager_result.get("steps", []):
                    if step.get("index") == item["step"]:
                        step["diagnosticsArtifact"] = str(diagnostics_file)
    report = {
        "schemaVersion": 1,
        "ok": status == "passed",
        "runId": run_id,
        "status": status,
        "backend": backend.name if backend is not None else config.get("backend", "auto"),
        "scenario": str(scenario),
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "durationMs": round((finished - started).total_seconds() * 1000),
        "client": {"pid": client.pid if client else None, "command": redact_command(client_command, secret_flags)},
        "manager": {"pid": manager.pid if manager else None, "command": redact_command(manager_command, secret_flags), "exitCode": manager_exit_code},
        "resultTransport": transport,
        "jobId": run_id if transport == "bridgeJob" else None,
        "clientLog": str(client_log) if client_log.exists() else None,
        "managerLog": str(manager_log) if transport == "inlineLog" else None,
        "resultFile": str(result_file) if result_file is not None else None,
        "managerResult": manager_result,
        "uiaBeforeResult": uia_before_results,
        "uiaBridgeResult": uia_bridge_results or None,
        "uiaResult": uia_results,
        "progress": progress_events,
        "artifacts": {"screenshot": screenshot_file, "progress": str(progress_file), "diagnostics": str(diagnostics_file) if diagnostics_file else None},
    }
    if error:
        report["error"] = error
    if screenshot_error:
        report["screenshotError"] = screenshot_error
    summary = {
        "runId": run_id,
        "status": status,
        "durationMs": report["durationMs"],
        "lastSuccessfulStep": next((step for step in reversed((manager_result or {}).get("steps", [])) if step.get("status") == "passed"), None),
        "error": error,
        "artifacts": report["artifacts"],
    }
    write_atomic_json(summary_file, summary)
    report["artifacts"]["summary"] = str(summary_file)
    final_stage = "passed" if status == "passed" else "failed"
    progress(final_stage, f"UI worker {final_stage} in {report['durationMs']}ms")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a native headless 1C UI scenario")
    parser.add_argument("--config", required=True, help="Worker JSON configuration")
    parser.add_argument("--scenario", required=True, help="UI scenario JSON")
    parser.add_argument("--artifact-dir", required=True, help="Artifact output directory")
    parser.add_argument("--report", help="Optional JSON report path")
    args = parser.parse_args(argv)
    try:
        with Path(args.config).open("r", encoding="utf-8-sig") as source:
            config = json.load(source)
        report = run_ui_worker(config, args.scenario, args.artifact_dir)
    except Exception as exc:
        report = {
            "schemaVersion": 1,
            "ok": False,
            "status": "failed",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
