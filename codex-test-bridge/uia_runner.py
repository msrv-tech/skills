#!/usr/bin/env python3
"""Small Windows UI Automation fallback for hidden 1C client windows."""

from __future__ import annotations

import ctypes
import fnmatch
import json
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
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
HWND = ctypes.c_void_p
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


class UiaRunnerError(RuntimeError):
    pass


def _automation(desktop_name: str, process_id: int):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.OpenDesktopW.restype = wintypes.HANDLE
    user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
    user32.IsWindowVisible.argtypes = [HWND]
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
    desktop = user32.OpenDesktopW(desktop_name, 0, False, 0x10000000)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    if not user32.SetThreadDesktop(desktop):
        raise ctypes.WinError(ctypes.get_last_error())
    windows: list[tuple[int, int]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)

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


def _click_rectangle(user32, rectangle, relative_x: float = 0.5, relative_y: float = 0.5, fallback_hwnd: int | None = None, double: bool = False) -> int:
    point = wintypes.POINT(int(rectangle.left + (rectangle.right - rectangle.left) * relative_x),
                           int(rectangle.top + (rectangle.bottom - rectangle.top) * relative_y))
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = HWND
    user32.ScreenToClient.argtypes = [HWND, ctypes.POINTER(wintypes.POINT)]
    user32.SendMessageW.argtypes = [HWND, wintypes.UINT, WPARAM, LPARAM]
    target = user32.WindowFromPoint(point)
    if not target:
        if fallback_hwnd is None:
            raise UiaRunnerError("WindowFromPoint did not find a target HWND")
        target = fallback_hwnd
    target = int(target)
    user32.ScreenToClient(target, ctypes.byref(point))
    lparam = (point.y << 16) | (point.x & 0xFFFF)
    user32.GetAncestor.argtypes = [HWND, wintypes.UINT]
    user32.GetAncestor.restype = HWND
    root = int(user32.GetAncestor(target, 2) or target)
    user32.SetForegroundWindow.argtypes = [HWND]
    user32.SetActiveWindow.argtypes = [HWND]
    user32.SetFocus.argtypes = [HWND]
    user32.SetForegroundWindow(root)
    user32.SetActiveWindow(root)
    user32.SetFocus(target)
    user32.SendMessageW(root, 0x0006, 1, 0)
    user32.SendMessageW(target, 0x0021, root, (0x0201 << 16) | 1)
    user32.SendMessageW(target, 0x0020, target, (0x0201 << 16) | 1)
    user32.SendMessageW(target, 0x0200, 0, lparam)
    user32.SendMessageW(target, 0x0201, 0x0001, lparam)
    user32.SendMessageW(target, 0x0202, 0, lparam)
    if double:
        user32.SendMessageW(target, 0x0203, 0x0001, lparam)
        user32.SendMessageW(target, 0x0202, 0, lparam)
    return target


def _real_mouse_click_rectangle(user32, rectangle, relative_x: float = 0.5, relative_y: float = 0.5, clicks: int = 1) -> int:
    x = int(rectangle.left + (rectangle.right - rectangle.left) * relative_x)
    y = int(rectangle.top + (rectangle.bottom - rectangle.top) * relative_y)
    point = wintypes.POINT(x, y)
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = HWND
    target = int(user32.WindowFromPoint(point) or 0)
    if not target:
        raise UiaRunnerError("WindowFromPoint did not find a target HWND")
    width = max(1, int(user32.GetSystemMetrics(0)) - 1)
    height = max(1, int(user32.GetSystemMetrics(1)) - 1)
    absolute_x = int(round(x * 65535 / width))
    absolute_y = int(round(y * 65535 / height))
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    for _ in range(max(1, clicks)):
        events = [
            INPUT(type=0, union=INPUT_UNION(mi=MOUSEINPUT(
                dx=absolute_x, dy=absolute_y, mouseData=0,
                dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                time=0, dwExtraInfo=0,
            ))),
            INPUT(type=0, union=INPUT_UNION(mi=MOUSEINPUT(
                dx=absolute_x, dy=absolute_y, mouseData=0,
                dwFlags=MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE,
                time=0, dwExtraInfo=0,
            ))),
            INPUT(type=0, union=INPUT_UNION(mi=MOUSEINPUT(
                dx=absolute_x, dy=absolute_y, mouseData=0,
                dwFlags=MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE,
                time=0, dwExtraInfo=0,
            ))),
        ]
        array_type = INPUT * len(events)
        sent = user32.SendInput(len(events), array_type(*events), ctypes.sizeof(INPUT))
        if sent != len(events):
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(0.05)
    return target


def _click_element(user32, element, relative_x: float = 0.5, relative_y: float = 0.5) -> int:
    return _click_rectangle(user32, element.CurrentBoundingRectangle, relative_x, relative_y)


def _click_window(user32, hwnd: int, relative_x: float = 0.5, relative_y: float = 0.5) -> int:
    rectangle = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rectangle))
    return _click_rectangle(user32, rectangle, relative_x, relative_y, hwnd)


def _focused_element(uia, root):
    try:
        element = uia.GetFocusedElement()
        if element is not None:
            return element
    except Exception:
        pass
    return root


def _rect_dict(rectangle) -> dict[str, int]:
    return {
        "left": int(rectangle.left), "top": int(rectangle.top),
        "right": int(rectangle.right), "bottom": int(rectangle.bottom),
    }


def _rect_width(rectangle) -> int:
    return max(0, int(rectangle.right - rectangle.left))


def _rect_height(rectangle) -> int:
    return max(0, int(rectangle.bottom - rectangle.top))


def _vertical_overlap(a, b) -> int:
    return max(0, min(int(a.bottom), int(b.bottom)) - max(int(a.top), int(b.top)))


def _safe_element_info(element) -> dict[str, Any]:
    rectangle = element.CurrentBoundingRectangle
    info = {
        "name": element.CurrentName or "",
        "automationId": element.CurrentAutomationId or "",
        "className": element.CurrentClassName or "",
        "controlType": int(element.CurrentControlType),
        "rectangle": _rect_dict(rectangle),
    }
    try:
        info["helpText"] = element.CurrentHelpText or ""
    except Exception:
        info["helpText"] = ""
    return info


def _field_button_candidates(uia, root, focused_element) -> list[Any]:
    focused_rect = focused_element.CurrentBoundingRectangle
    focused_height = _rect_height(focused_rect)
    if focused_height <= 0:
        return []
    right_zone = max(80, focused_height * 4)
    candidates = []
    for element in _elements(uia, root):
        try:
            rectangle = element.CurrentBoundingRectangle
            width = _rect_width(rectangle)
            height = _rect_height(rectangle)
            if width <= 0 or height <= 0:
                continue
            if _vertical_overlap(focused_rect, rectangle) < min(focused_height, height) * 0.45:
                continue
            if int(rectangle.left) < int(focused_rect.right) - right_zone:
                continue
            if int(rectangle.right) > int(focused_rect.right) + 12:
                continue
            if int(rectangle.left) < int(focused_rect.left):
                continue
            name = (element.CurrentName or "").lower()
            automation_id = (element.CurrentAutomationId or "").lower()
            class_name = (element.CurrentClassName or "").lower()
            try:
                help_text = (element.CurrentHelpText or "").lower()
            except Exception:
                help_text = ""
            control_type = int(element.CurrentControlType)
            text = " ".join([name, automation_id, class_name, help_text])
            score = int(rectangle.left)
            if control_type == CONTROL_TYPES["button"]:
                score += 100000
            if any(marker in text for marker in ("выбор", "choose", "choice", "dropdown", "drop", "открыть", "...")):
                score += 50000
            if width <= max(36, focused_height * 2):
                score += 10000
            candidates.append((score, element))
        except Exception:
            continue
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [element for _score, element in candidates[:5]]


def _uia_visible_elements(uia, root, limit: int = 120) -> list[dict[str, Any]]:
    visible = []
    for element in _elements(uia, root):
        try:
            rectangle = element.CurrentBoundingRectangle
            if _rect_width(rectangle) <= 0 or _rect_height(rectangle) <= 0:
                continue
            if not (element.CurrentName or element.CurrentAutomationId):
                continue
            visible.append(_safe_element_info(element))
            if len(visible) >= limit:
                break
        except Exception:
            continue
    return visible


def _table_cell_candidates(uia, root, request: dict[str, Any] | None) -> list[Any]:
    if not request:
        return []
    field_name = str(request.get("fieldName") or "")
    table_name = str(request.get("tableName") or "")
    labels = []
    if field_name:
        labels.append(field_name.lower())
        if table_name and field_name.lower().startswith(table_name.lower()):
            suffix = field_name[len(table_name):]
            if suffix:
                labels.append(suffix.lower())
    labels = [label for label in labels if label]
    if not labels:
        return []
    candidates = []
    for element in _elements(uia, root):
        try:
            if int(element.CurrentControlType) != 50025:
                continue
            name = (element.CurrentName or "").lower()
            if not any(label in name for label in labels):
                continue
            rectangle = element.CurrentBoundingRectangle
            width = _rect_width(rectangle)
            height = _rect_height(rectangle)
            if width <= 0 or height <= 0:
                continue
            score = int(rectangle.top)
            if int(rectangle.top) > 250:
                score += 100000
            if labels[-1] and name.endswith(labels[-1]):
                score += 50000
            score += width
            candidates.append((score, element))
        except Exception:
            continue
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [element for _score, element in candidates[:5]]


def _invoke_table_cell_for_choice(user32, cell) -> list[str]:
    attempts: list[str] = []
    try:
        from comtypes.gen.UIAutomationClient import (
            IUIAutomationInvokePattern,
            IUIAutomationLegacyIAccessiblePattern,
            IUIAutomationScrollItemPattern,
            IUIAutomationSelectionItemPattern,
        )
    except Exception as exc:
        attempts.append(f"importPatterns:{type(exc).__name__}:{exc}")
        return attempts

    pattern_attempts = [
        ("ScrollIntoView", 10017, IUIAutomationScrollItemPattern, "ScrollIntoView"),
        ("Select", 10010, IUIAutomationSelectionItemPattern, "Select"),
        ("Invoke", 10000, IUIAutomationInvokePattern, "Invoke"),
        ("DoDefaultAction", 10018, IUIAutomationLegacyIAccessiblePattern, "DoDefaultAction"),
    ]
    for name, pattern_id, interface, method_name in pattern_attempts:
        try:
            pattern = cell.GetCurrentPattern(pattern_id).QueryInterface(interface)
            getattr(pattern, method_name)()
            attempts.append(name + ":ok")
            time.sleep(0.15)
        except Exception as exc:
            attempts.append(f"{name}:{type(exc).__name__}:{exc}")
    try:
        target = _click_rectangle(user32, cell.CurrentBoundingRectangle, 0.5, 0.5, double=True)
        attempts.append("messageDoubleClick:ok")
        time.sleep(0.2)
    except Exception as exc:
        attempts.append(f"messageDoubleClick:{type(exc).__name__}:{exc}")
    try:
        target = _click_element(user32, cell, 0.94, 0.5)
        _send_key(user32, target, 0x0D)
        time.sleep(0.1)
        target = _click_element(user32, cell, 0.985, 0.5)
        _send_key(user32, target, 0x73)
        attempts.append("messageClickEnterRightF4:ok")
    except Exception as exc:
        attempts.append(f"messageClickEnterRightF4:{type(exc).__name__}:{exc}")
    return attempts


def _click_active_field_button(user32, uia, root, button_kind: str = "choice", fallback_hwnd: int | None = None, request: dict[str, Any] | None = None) -> dict[str, Any]:
    element = _focused_element(uia, root)
    rectangle = element.CurrentBoundingRectangle
    width = _rect_width(rectangle)
    height = _rect_height(rectangle)
    if width <= 0 or height <= 0:
        raise UiaRunnerError("Focused UIA element has an empty bounding rectangle")
    if width >= 1000 and height >= 600:
        cell_candidates = _table_cell_candidates(uia, root, request)
        if cell_candidates:
            cell = cell_candidates[0]
            user32.SendMessageW.argtypes = [HWND, wintypes.UINT, WPARAM, LPARAM]
            user32.GetAncestor.argtypes = [HWND, wintypes.UINT]
            user32.GetAncestor.restype = HWND
            attempts = _invoke_table_cell_for_choice(user32, cell)
            target = fallback_hwnd or 0
            return {
                "buttonKind": button_kind,
                "targetHwnd": int(target),
                "focused": _safe_element_info(element),
                "cell": _safe_element_info(cell),
                "candidateCount": len(cell_candidates),
                "attempts": attempts,
                "request": {
                    "fieldName": (request or {}).get("fieldName", ""),
                    "tableName": (request or {}).get("tableName", ""),
                },
                "method": "tableCellPatterns",
            }
        if fallback_hwnd is None:
            raise UiaRunnerError(
                "Focused UIA element is the desktop/window root, not an active field: "
                + json.dumps(_safe_element_info(element), ensure_ascii=False)
            )
        user32.SetForegroundWindow.argtypes = [HWND]
        user32.SetActiveWindow.argtypes = [HWND]
        user32.SendMessageW.argtypes = [HWND, wintypes.UINT, WPARAM, LPARAM]
        user32.GetAncestor.argtypes = [HWND, wintypes.UINT]
        user32.GetAncestor.restype = HWND
        user32.SetForegroundWindow(fallback_hwnd)
        user32.SetActiveWindow(fallback_hwnd)
        key = 0x73 if button_kind.lower() in {"choice", "open"} else 0x28
        _send_key(user32, fallback_hwnd, key, alt=button_kind.lower() == "dropdown")
        return {
            "buttonKind": button_kind,
            "targetHwnd": int(fallback_hwnd),
            "focused": _safe_element_info(element),
            "request": {
                "fieldName": (request or {}).get("fieldName", ""),
                "tableName": (request or {}).get("tableName", ""),
            },
            "visibleElements": _uia_visible_elements(uia, root),
            "method": "keyboardF4" if key == 0x73 else "keyboardAltDown",
        }
    candidates = _field_button_candidates(uia, root, element)
    if candidates:
        button = candidates[0]
        target = _click_element(user32, button)
        return {
            "buttonKind": button_kind,
            "targetHwnd": int(target),
            "focused": _safe_element_info(element),
            "button": _safe_element_info(button),
            "candidateCount": len(candidates),
            "method": "candidate",
        }
    relative_x = {
        "choice": 0.965,
        "dropdown": 0.925,
        "open": 0.965,
    }.get(button_kind.lower(), 0.965)
    target = _click_rectangle(user32, rectangle, relative_x, 0.5)
    return {
        "buttonKind": button_kind,
        "targetHwnd": int(target),
        "focused": _safe_element_info(element),
        "relativeX": relative_x,
        "method": "relative",
    }


def _send_key(user32, target: int, virtual_key: int, *, control: bool = False, shift: bool = False, alt: bool = False) -> None:
    root = user32.GetAncestor(target, 2) if hasattr(user32, "GetAncestor") else target
    destinations = [target] if not root or root == target else [target, root]
    for destination in destinations:
        if control:
            user32.SendMessageW(destination, 0x0100, 0x11, 0)
        if shift:
            user32.SendMessageW(destination, 0x0100, 0x10, 0)
        if alt:
            user32.SendMessageW(destination, 0x0100, 0x12, 0)
        user32.SendMessageW(destination, 0x0100, virtual_key, 0)
        user32.SendMessageW(destination, 0x0101, virtual_key, 0)
        if alt:
            user32.SendMessageW(destination, 0x0101, 0x12, 0)
        if shift:
            user32.SendMessageW(destination, 0x0101, 0x10, 0)
        if control:
            user32.SendMessageW(destination, 0x0101, 0x11, 0)


def _send_input_key(user32, virtual_key: int, *, control: bool = False, shift: bool = False, alt: bool = False) -> None:
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    keys: list[int] = []
    if control:
        keys.append(0x11)
    if shift:
        keys.append(0x10)
    if alt:
        keys.append(0x12)
    keys.append(virtual_key)
    events: list[INPUT] = []
    for key in keys:
        events.append(INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(key, 0, 0, 0, 0))))
    for key in reversed(keys):
        events.append(INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(key, 0, KEYEVENTF_KEYUP, 0, 0))))
    array_type = INPUT * len(events)
    sent = user32.SendInput(len(events), array_type(*events), ctypes.sizeof(INPUT))
    if sent != len(events):
        raise ctypes.WinError(ctypes.get_last_error())


def _send_input_text(user32, value: str, *, enter: bool = False) -> None:
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    events: list[INPUT] = []
    for character in value:
        code = ord(character)
        events.append(INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0))))
        events.append(INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))))
    if events:
        array_type = INPUT * len(events)
        sent = user32.SendInput(len(events), array_type(*events), ctypes.sizeof(INPUT))
        if sent != len(events):
            raise ctypes.WinError(ctypes.get_last_error())
    if enter:
        _send_input_key(user32, 0x0D)


def _clipboard_text(user32) -> str:
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    if not user32.OpenClipboard(0):
        return ""
    try:
        handle = user32.GetClipboardData(13)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _set_clipboard_text(user32, value: str) -> None:
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    data = (value + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(0x0002, len(data))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        raise ctypes.WinError(ctypes.get_last_error())
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(0):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(13, handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        user32.CloseClipboard()


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
    user32, desktop, hwnd, uia, root = _automation(desktop_name, process_id)
    results: list[dict[str, Any]] = []
    last_target = hwnd
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
                    if "name" in step or "controlType" in step:
                        element = _find(uia, root, step, float(step.get("timeout", 60)))
                        last_target = _click_element(user32, element, float(step.get("relativeX", 0.5)), float(step.get("relativeY", 0.5)))
                    else:
                        last_target = _click_window(user32, hwnd, float(step.get("relativeX", 0.5)), float(step.get("relativeY", 0.5)))
                elif action == "clickwindow":
                    last_target = _click_window(user32, hwnd, float(step.get("relativeX", 0.5)), float(step.get("relativeY", 0.5)))
                elif action == "clickactivefieldbutton":
                    actual = _click_active_field_button(user32, uia, root, str(step.get("buttonKind", "choice")))
                    last_target = int(actual["targetHwnd"])
                    result["actual"] = actual
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
                    if "name" in step or "controlType" in step:
                        element = _find(uia, root, step, float(step.get("timeout", 60)))
                        _type_text(user32, element, str(step.get("value", "")),
                                   clear=bool(step.get("clear", True)), enter=bool(step.get("enter", False)))
                    else:
                        _send_input_text(user32, str(step.get("value", "")), enter=bool(step.get("enter", False)))
                elif action == "typetextwindow":
                    value = str(step.get("value", ""))
                    if step.get("useClipboard", True):
                        previous_clipboard = _clipboard_text(user32)
                        try:
                            _set_clipboard_text(user32, value)
                            _send_key(user32, last_target, ord("V"), control=True)
                            if step.get("enter", False):
                                _send_key(user32, last_target, 0x0D)
                        finally:
                            _set_clipboard_text(user32, previous_clipboard)
                    else:
                        _send_input_text(user32, value, enter=bool(step.get("enter", False)))
                elif action == "pastetextwindow":
                    previous_clipboard = _clipboard_text(user32)
                    try:
                        _set_clipboard_text(user32, str(step.get("value", "")))
                        _send_key(user32, last_target, ord("V"), control=True)
                        if step.get("enter", False):
                            _send_key(user32, last_target, 0x0D)
                    finally:
                        _set_clipboard_text(user32, previous_clipboard)
                elif action == "presskey":
                    if "name" in step or "controlType" in step:
                        element = _find(uia, root, step, float(step.get("timeout", 60)))
                        try:
                            element.SetFocus()
                        except Exception:
                            pass
                        target = _click_element(user32, element)
                    else:
                        target = last_target
                    key = str(step.get("key", "enter")).lower()
                    virtual_keys = {"enter": 0x0D, "tab": 0x09, "escape": 0x1B, "space": 0x20,
                                    "down": 0x28, "up": 0x26, "delete": 0x2E, "backspace": 0x08,
                                    **{f"f{number}": 0x6F + number for number in range(1, 13)}}
                    if key not in virtual_keys:
                        raise UiaRunnerError(f"Unsupported key: {key}")
                    if "name" in step or "controlType" in step:
                        _send_key(user32, target, virtual_keys[key], control=bool(step.get("control", False)), shift=bool(step.get("shift", False)), alt=bool(step.get("alt", False)))
                    else:
                        _send_input_key(user32, virtual_keys[key], control=bool(step.get("control", False)), shift=bool(step.get("shift", False)), alt=bool(step.get("alt", False)))
                elif action == "presskeywindow":
                    key = str(step.get("key", "enter")).lower()
                    virtual_keys = {"enter": 0x0D, "tab": 0x09, "escape": 0x1B, "space": 0x20,
                                    "down": 0x28, "up": 0x26, "delete": 0x2E, "backspace": 0x08,
                                    **{f"f{number}": 0x6F + number for number in range(1, 13)}}
                    if key not in virtual_keys:
                        raise UiaRunnerError(f"Unsupported key: {key}")
                    _send_input_key(user32, virtual_keys[key], control=bool(step.get("control", False)), shift=bool(step.get("shift", False)), alt=bool(step.get("alt", False)))
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


def run_uia_bridge_request(desktop_name: str, process_id: int, request: dict[str, Any]) -> dict[str, Any]:
    user32, desktop, hwnd, uia, root = _automation(desktop_name, process_id)
    try:
        action = str(request.get("action", "")).lower()
        if action == "clickactivefieldbutton":
            actual = _click_active_field_button(user32, uia, root, str(request.get("buttonKind", "choice")), hwnd, request)
            tentative = actual.get("method") in {"tableCellPatterns"}
            return {
                "ok": not tentative,
                "requestId": request.get("requestId"),
                "status": "uia-response",
                "actual": actual,
                **({"error": "UIA table cell fallback was tentative; native bridge should continue fallback chain"} if tentative else {}),
            }
        raise UiaRunnerError(f"Unsupported UIA bridge action: {request.get('action')}")
    except Exception as exc:
        return {
            "ok": False,
            "requestId": request.get("requestId"),
            "status": "uia-response",
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        user32.CloseDesktop(desktop)
