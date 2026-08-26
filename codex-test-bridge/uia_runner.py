#!/usr/bin/env python3
"""Small Windows UI Automation fallback for hidden 1C client windows."""

from __future__ import annotations

import ctypes
import fnmatch
import time
from ctypes import wintypes
from typing import Any


CONTROL_TYPES = {
    "button": 50000,
    "edit": 50004,
    "checkbox": 50002,
    "text": 50020,
    "tabitem": 50019,
    "pane": 50033,
    "table": 50036,
}


class UiaRunnerError(RuntimeError):
    pass


def _automation(desktop_name: str, process_id: int):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.OpenDesktopW.restype = wintypes.HANDLE
    user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    desktop = user32.OpenDesktopW(desktop_name, 0, False, 0x10000000)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    if not user32.SetThreadDesktop(desktop):
        raise ctypes.WinError(ctypes.get_last_error())
    windows: list[tuple[int, int]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd: int, _lparam: int) -> bool:
        pid = wintypes.DWORD()
        rect = wintypes.RECT()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if pid.value == process_id and user32.IsWindowVisible(hwnd):
            windows.append((max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top), hwnd))
        return True

    user32.EnumDesktopWindows(desktop, callback_type(collect), 0)
    if not windows:
        raise UiaRunnerError(f"Visible 1C window was not found for process {process_id}")
    import comtypes.client

    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import IUIAutomation

    uia = comtypes.client.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}", interface=IUIAutomation)
    hwnd = max(windows)[1]
    return user32, desktop, hwnd, uia, uia.ElementFromHandle(hwnd)


def _click_element(user32, element, relative_x: float = 0.5, relative_y: float = 0.5) -> int:
    rectangle = element.CurrentBoundingRectangle
    point = wintypes.POINT(int(rectangle.left + (rectangle.right - rectangle.left) * relative_x),
                           int(rectangle.top + (rectangle.bottom - rectangle.top) * relative_y))
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    target = user32.WindowFromPoint(point)
    if not target:
        raise UiaRunnerError("WindowFromPoint did not find a target HWND")
    user32.ScreenToClient(target, ctypes.byref(point))
    lparam = (point.y << 16) | (point.x & 0xFFFF)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    root = user32.GetAncestor(target, 2) or target
    user32.SetForegroundWindow(root)
    user32.SetActiveWindow(root)
    user32.SetFocus(target)
    user32.SendMessageW(root, 0x0006, 1, 0)
    user32.SendMessageW(target, 0x0021, root, (0x0201 << 16) | 1)
    user32.SendMessageW(target, 0x0020, target, (0x0201 << 16) | 1)
    user32.SendMessageW(target, 0x0200, 0, lparam)
    user32.SendMessageW(target, 0x0201, 0x0001, lparam)
    user32.SendMessageW(target, 0x0202, 0, lparam)
    return target


def _send_key(user32, target: int, virtual_key: int, *, control: bool = False) -> None:
    root = user32.GetAncestor(target, 2) if hasattr(user32, "GetAncestor") else target
    destinations = [target] if not root or root == target else [target, root]
    for destination in destinations:
        if control:
            user32.SendMessageW(destination, 0x0100, 0x11, 0)
        user32.SendMessageW(destination, 0x0100, virtual_key, 0)
        user32.SendMessageW(destination, 0x0101, virtual_key, 0)
        if control:
            user32.SendMessageW(destination, 0x0101, 0x11, 0)


def _type_text(user32, element, value: str, *, clear: bool = True, enter: bool = False) -> None:
    try:
        element.SetFocus()
    except Exception:
        pass
    target = _click_element(user32, element)
    if clear:
        _send_key(user32, target, ord("A"), control=True)
        _send_key(user32, target, 0x08)
    for character in value:
        user32.SendMessageW(target, 0x0102, ord(character), 0)
    if enter:
        _send_key(user32, target, 0x0D)


def _elements(uia, root):
    collection = root.FindAll(4, uia.CreateTrueCondition())
    return [collection.GetElement(index) for index in range(collection.Length)]


def _matches(element, selector: dict[str, Any]) -> bool:
    name = selector.get("name", "*")
    if not fnmatch.fnmatchcase(element.CurrentName or "", name):
        return False
    control_type = selector.get("controlType")
    if isinstance(control_type, str):
        control_type = CONTROL_TYPES.get(control_type.lower())
    return control_type is None or element.CurrentControlType == control_type


def _find(uia, root, selector: dict[str, Any], timeout: float):
    deadline = time.monotonic() + timeout
    occurrence = int(selector.get("occurrence", 1))
    while True:
        matches = [element for element in _elements(uia, root) if _matches(element, selector)]
        if len(matches) >= occurrence:
            return matches[occurrence - 1]
        if time.monotonic() >= deadline:
            raise UiaRunnerError(f"UIA element was not found: {selector}")
        time.sleep(0.25)


def run_uia_steps(desktop_name: str, process_id: int, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user32, desktop, _hwnd, uia, root = _automation(desktop_name, process_id)
    results: list[dict[str, Any]] = []
    try:
        for index, step in enumerate(steps, 1):
            action = str(step.get("action", "")).lower()
            result: dict[str, Any] = {"index": index, "action": step.get("action"), "name": step.get("stepName", f"uia-{index}")}
            try:
                if action == "inspect":
                    result["actual"] = [
                        {"name": element.CurrentName, "controlType": element.CurrentControlType,
                         "automationId": element.CurrentAutomationId, "className": element.CurrentClassName}
                        for element in _elements(uia, root) if element.CurrentName or element.CurrentAutomationId
                    ]
                elif action == "wait":
                    _find(uia, root, step, float(step.get("timeout", 60)))
                elif action == "invoke":
                    from comtypes.gen.UIAutomationClient import IUIAutomationInvokePattern, IUIAutomationLegacyIAccessiblePattern
                    element = _find(uia, root, step, float(step.get("timeout", 60)))
                    try:
                        element.GetCurrentPattern(10000).QueryInterface(IUIAutomationInvokePattern).Invoke()
                    except Exception:
                        try:
                            element.GetCurrentPattern(10018).QueryInterface(IUIAutomationLegacyIAccessiblePattern).DoDefaultAction()
                        except Exception:
                            _click_element(user32, element)
                elif action == "click":
                    element = _find(uia, root, step, float(step.get("timeout", 60)))
                    _click_element(user32, element, float(step.get("relativeX", 0.5)), float(step.get("relativeY", 0.5)))
                elif action == "legacyinvoke":
                    from comtypes.gen.UIAutomationClient import IUIAutomationLegacyIAccessiblePattern
                    element = _find(uia, root, step, float(step.get("timeout", 60)))
                    element.GetCurrentPattern(10018).QueryInterface(IUIAutomationLegacyIAccessiblePattern).DoDefaultAction()
                elif action == "setvalue":
                    from comtypes.gen.UIAutomationClient import IUIAutomationValuePattern
                    element = _find(uia, root, step, float(step.get("timeout", 60)))
                    element.SetFocus()
                    value = str(step.get("value", ""))
                    try:
                        element.GetCurrentPattern(10002).QueryInterface(IUIAutomationValuePattern).SetValue(value)
                        if step.get("enter", False):
                            target = _click_element(user32, element)
                            _send_key(user32, target, 0x0D)
                    except Exception:
                        _type_text(user32, element, value, enter=bool(step.get("enter", False)))
                elif action == "typetext":
                    element = _find(uia, root, step, float(step.get("timeout", 60)))
                    _type_text(user32, element, str(step.get("value", "")),
                               clear=bool(step.get("clear", True)), enter=bool(step.get("enter", False)))
                elif action == "presskey":
                    element = _find(uia, root, step, float(step.get("timeout", 60)))
                    try:
                        element.SetFocus()
                    except Exception:
                        pass
                    target = _click_element(user32, element)
                    key = str(step.get("key", "enter")).lower()
                    virtual_keys = {"enter": 0x0D, "tab": 0x09, "escape": 0x1B, "space": 0x20,
                                    "down": 0x28, "up": 0x26, "delete": 0x2E, "backspace": 0x08,
                                    **{f"f{number}": 0x6F + number for number in range(1, 13)}}
                    if key not in virtual_keys:
                        raise UiaRunnerError(f"Unsupported key: {key}")
                    _send_key(user32, target, virtual_keys[key], control=bool(step.get("control", False)))
                elif action == "toggle":
                    from comtypes.gen.UIAutomationClient import IUIAutomationTogglePattern
                    element = _find(uia, root, step, float(step.get("timeout", 60)))
                    element.GetCurrentPattern(10015).QueryInterface(IUIAutomationTogglePattern).Toggle()
                elif action == "sleep":
                    time.sleep(float(step.get("seconds", 1)))
                else:
                    raise UiaRunnerError(f"Unsupported UIA action: {action}")
                result["status"] = "passed"
            except Exception as exc:
                result["status"] = "failed"
                result["error"] = f"{type(exc).__name__}: {exc}"
                results.append(result)
                break
            results.append(result)
        return results
    finally:
        user32.CloseDesktop(desktop)
