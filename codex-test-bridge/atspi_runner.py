#!/usr/bin/env python3
"""Linux AT-SPI fallback for semantic 1C UI bridge requests."""

from __future__ import annotations

import os
import re
import ctypes
import ctypes.util
from collections import deque
from typing import Any, Iterable


class AtspiRunnerError(RuntimeError):
    pass


class _XWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("width", ctypes.c_int), ("height", ctypes.c_int),
        ("border_width", ctypes.c_int), ("depth", ctypes.c_int),
        ("visual", ctypes.c_void_p), ("root", ctypes.c_ulong),
        ("window_class", ctypes.c_int), ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong),
        ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
        ("all_event_masks", ctypes.c_long), ("your_event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
        ("screen", ctypes.c_void_p),
    ]


def select_x11_window_candidates(
    owned: list[tuple[int, int, bool]],
    isolated_display: list[tuple[int, int, bool]],
    *,
    allow_isolated_fallback: bool,
) -> list[tuple[int, int, bool]]:
    if owned:
        return owned
    return isolated_display if allow_isolated_fallback else []


def is_worker_owned_xvfb_environment() -> bool:
    if os.environ.get("CODEX_XVFB_ISOLATED") == "1":
        return True
    match = re.fullmatch(r":(\d+)(?:\.\d+)?", os.environ.get("DISPLAY", ""))
    return match is not None and 90 <= int(match.group(1)) <= 199


def _x11_process_windows(x11: Any, display: Any, process_id: int) -> list[tuple[int, int, bool]]:
    root = x11.XDefaultRootWindow(display)
    root_return = ctypes.c_ulong()
    parent_return = ctypes.c_ulong()
    children = ctypes.POINTER(ctypes.c_ulong)()
    count = ctypes.c_uint()
    if not x11.XQueryTree(
        display, root, ctypes.byref(root_return), ctypes.byref(parent_return),
        ctypes.byref(children), ctypes.byref(count),
    ):
        raise AtspiRunnerError("XQueryTree failed")
    pid_atom = x11.XInternAtom(display, b"_NET_WM_PID", 0)
    cardinal_atom = x11.XInternAtom(display, b"CARDINAL", 0)
    owned_pids = process_tree_ids(process_id)
    result: list[tuple[int, int, bool]] = []
    isolated_display_windows: list[tuple[int, int, bool]] = []
    try:
        for index in range(count.value):
            window = int(children[index])
            attributes = _XWindowAttributes()
            visible = bool(x11.XGetWindowAttributes(display, window, ctypes.byref(attributes))) and attributes.map_state == 2
            area = max(0, attributes.width) * max(0, attributes.height)
            if visible and area:
                isolated_display_windows.append((window, area, True))
            actual_type = ctypes.c_ulong()
            actual_format = ctypes.c_int()
            item_count = ctypes.c_ulong()
            bytes_after = ctypes.c_ulong()
            value = ctypes.POINTER(ctypes.c_ubyte)()
            status = x11.XGetWindowProperty(
                display, window, pid_atom, 0, 1, 0, cardinal_atom,
                ctypes.byref(actual_type), ctypes.byref(actual_format),
                ctypes.byref(item_count), ctypes.byref(bytes_after), ctypes.byref(value),
            )
            try:
                if status != 0 or item_count.value < 1 or not value:
                    continue
                owner_pid = int(ctypes.cast(value, ctypes.POINTER(ctypes.c_ulong))[0])
                if owner_pid not in owned_pids:
                    continue
                result.append((window, area, visible))
            finally:
                if value:
                    x11.XFree(value)
    finally:
        if children:
            x11.XFree(children)
    # The Linux 1C launcher can reparent its GUI process after a long-running
    # TestManager session. Then _NET_WM_PID no longer belongs to the original
    # process tree even though the window is still the only application on the
    # worker-owned Xvfb display. Falling back to that isolated display keeps key
    # delivery deterministic without ever targeting the user's real desktop.
    return select_x11_window_candidates(
        result,
        isolated_display_windows,
        allow_isolated_fallback=is_worker_owned_xvfb_environment(),
    )


def send_x11_key(process_id: int, key: str) -> dict[str, Any]:
    x11_path = ctypes.util.find_library("X11")
    xtst_path = ctypes.util.find_library("Xtst")
    if not os.environ.get("DISPLAY") or not x11_path or not xtst_path:
        raise AtspiRunnerError("X11 key injection is unavailable")
    x11 = ctypes.CDLL(x11_path)
    xtst = ctypes.CDLL(xtst_path)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint)]
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XGetWindowProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
    x11.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_XWindowAttributes)]
    x11.XFree.argtypes = [ctypes.c_void_p]
    x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    x11.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_ubyte
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xtst.XTestFakeKeyEvent.restype = ctypes.c_int
    keysyms = {
        "enter": 0xFF0D, "space": 0x20, "right": 0xFF53, "left": 0xFF51,
        "down": 0xFF54, "up": 0xFF52,
        **{f"f{number}": 0xFFBD + number for number in range(1, 13)},
    }
    normalized_key = key.casefold()
    if normalized_key not in keysyms:
        raise AtspiRunnerError(f"Unsupported X11 bridge key: {key}")
    display = x11.XOpenDisplay(None)
    if not display:
        raise AtspiRunnerError("XOpenDisplay failed")
    try:
        windows = _x11_process_windows(x11, display, process_id)
        if not windows:
            raise AtspiRunnerError("X11 window for TestClient process was not found")
        visible = [item for item in windows if item[2]]
        window, area, _ = max(visible or windows, key=lambda item: (item[1], item[0]))
        x11.XRaiseWindow(display, window)
        x11.XSetInputFocus(display, window, 2, 0)
        keycode = int(x11.XKeysymToKeycode(display, keysyms[normalized_key]))
        if not keycode:
            raise AtspiRunnerError(f"X11 keycode was not found for {key}")
        if not xtst.XTestFakeKeyEvent(display, keycode, 1, 0):
            raise AtspiRunnerError("XTest key press failed")
        if not xtst.XTestFakeKeyEvent(display, keycode, 0, 0):
            raise AtspiRunnerError("XTest key release failed")
        x11.XFlush(display)
        return {"method": "x11FocusedKey", "key": normalized_key, "window": hex(window), "area": area}
    finally:
        x11.XCloseDisplay(display)


def normalize_accessible_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    return text.replace("&", "").replace("_", "")


def process_tree_ids(root_pid: int) -> set[int]:
    """Return a best-effort Linux process tree rooted at the launcher PID."""
    result = {int(root_pid)}
    parent_by_pid: dict[int, int] = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            # /proc/<pid>/stat field 2 may contain spaces inside parentheses;
            # split after the final ')' so field 4 is the parent PID.
            with open(f"/proc/{entry.name}/stat", encoding="utf-8") as source:
                stat = source.read()
            tail = stat.rsplit(")", 1)[1].split()
            parent_by_pid[int(entry.name)] = int(tail[1])
        except (OSError, ValueError, IndexError):
            continue
    changed = True
    while changed:
        changed = False
        for pid, parent in parent_by_pid.items():
            if parent in result and pid not in result:
                result.add(pid)
                changed = True
    return result


def _children(accessible: Any) -> Iterable[Any]:
    try:
        count = min(1000, max(0, int(accessible.get_child_count())))
    except Exception:
        return ()
    children = []
    for index in range(count):
        try:
            child = accessible.get_child_at_index(index)
            if child is not None:
                children.append(child)
        except Exception:
            continue
    return children


def _safe_name(accessible: Any) -> str:
    try:
        return str(accessible.get_name() or "")
    except Exception:
        return ""


def _safe_description(accessible: Any) -> str:
    try:
        return str(accessible.get_description() or "")
    except Exception:
        return ""


def _safe_role(accessible: Any) -> str:
    try:
        return str(accessible.get_role_name() or "")
    except Exception:
        return ""


def _safe_attributes(accessible: Any) -> dict[str, str]:
    try:
        attributes = accessible.get_attributes()
        if isinstance(attributes, dict):
            return {str(key): str(value) for key, value in attributes.items()}
    except Exception:
        pass
    return {}


def accessible_info(accessible: Any) -> dict[str, Any]:
    actions = []
    try:
        for index in range(max(0, int(accessible.get_n_actions()))):
            actions.append(str(accessible.get_action_name(index) or ""))
    except Exception:
        pass
    return {
        "name": _safe_name(accessible),
        "description": _safe_description(accessible),
        "role": _safe_role(accessible),
        "actions": actions,
    }


def selector_score(accessible: Any, values: list[str]) -> int:
    wanted = [normalize_accessible_text(value) for value in values if normalize_accessible_text(value)]
    if not wanted:
        return -1
    attributes = _safe_attributes(accessible)
    candidates = [
        normalize_accessible_text(_safe_name(accessible)),
        normalize_accessible_text(_safe_description(accessible)),
        *[normalize_accessible_text(value) for value in attributes.values()],
    ]
    score = -1
    for expected in wanted:
        for candidate in candidates:
            if not candidate:
                continue
            if candidate == expected:
                score = max(score, 100)
            elif expected in candidate or candidate in expected:
                score = max(score, 50)
    return score


def find_accessible_element(roots: list[Any], values: list[str], *, limit: int = 10000) -> Any:
    queue = deque((root, 0) for root in roots)
    best: tuple[int, int, Any] | None = None
    visited = 0
    while queue and visited < limit:
        accessible, depth = queue.popleft()
        visited += 1
        score = selector_score(accessible, values)
        if score >= 0:
            candidate = (score, -depth, accessible)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
                if score == 100 and depth > 0:
                    # Keep traversing this branch only far enough to prefer a
                    # more specific child with the same exact accessible name.
                    pass
        for child in _children(accessible):
            queue.append((child, depth + 1))
    if best is None:
        raise AtspiRunnerError("AT-SPI element was not found by title or object name")
    return best[2]


def invoke_accessible_element(accessible: Any, atspi: Any) -> dict[str, Any]:
    preferred = ("click", "press", "activate", "jump", "open")
    actions: list[tuple[int, str]] = []
    try:
        actions = [
            (index, str(accessible.get_action_name(index) or ""))
            for index in range(max(0, int(accessible.get_n_actions())))
        ]
    except Exception:
        actions = []
    ordered = sorted(
        actions,
        key=lambda item: next(
            (position for position, word in enumerate(preferred) if word in item[1].casefold()),
            len(preferred),
        ),
    )
    errors = []
    for index, name in ordered:
        try:
            if accessible.do_action(index):
                return {"method": "atspiAction", "action": name, **accessible_info(accessible)}
            errors.append(f"{name or index}: returned false")
        except Exception as exc:
            errors.append(f"{name or index}: {type(exc).__name__}")
    try:
        component = accessible.get_component_iface()
        if component is None or not component.grab_focus():
            raise AtspiRunnerError("element did not accept accessibility focus")
        if not atspi.generate_keyboard_event(0xFF0D, None, atspi.KeySynthType.PRESSRELEASE):
            raise AtspiRunnerError("AT-SPI Enter synthesis returned false")
        return {"method": "atspiFocusEnter", **accessible_info(accessible)}
    except Exception as exc:
        detail = "; ".join(errors) if errors else "no default actions"
        raise AtspiRunnerError(f"AT-SPI element cannot be invoked ({detail}; {exc})") from exc


def expand_accessible_element(accessible: Any, atspi: Any) -> dict[str, Any]:
    preferred = ("expand", "toggle")
    actions: list[tuple[int, str]] = []
    try:
        actions = [
            (index, str(accessible.get_action_name(index) or ""))
            for index in range(max(0, int(accessible.get_n_actions())))
        ]
    except Exception:
        actions = []
    ordered = sorted(
        actions,
        key=lambda item: next(
            (position for position, word in enumerate(preferred) if word in item[1].casefold()),
            len(preferred),
        ),
    )
    errors = []
    for index, name in ordered:
        if not any(word in name.casefold() for word in preferred):
            continue
        try:
            if accessible.do_action(index):
                return {"method": "atspiExpandAction", "action": name, **accessible_info(accessible)}
            errors.append(f"{name or index}: returned false")
        except Exception as exc:
            errors.append(f"{name or index}: {type(exc).__name__}")
    try:
        component = accessible.get_component_iface()
        if component is None or not component.grab_focus():
            raise AtspiRunnerError("tree row did not accept accessibility focus")
        if not atspi.generate_keyboard_event(0xFF53, None, atspi.KeySynthType.PRESSRELEASE):
            raise AtspiRunnerError("AT-SPI Right synthesis returned false")
        return {"method": "atspiFocusRight", **accessible_info(accessible)}
    except Exception as exc:
        detail = "; ".join(errors) if errors else "no expand action"
        raise AtspiRunnerError(f"AT-SPI tree row cannot be expanded ({detail}; {exc})") from exc


def _atspi_module():
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        return Atspi
    except Exception as exc:
        raise AtspiRunnerError(f"Python GI AT-SPI 2.0 is unavailable: {exc}") from exc


def application_roots(atspi: Any, process_id: int) -> list[Any]:
    desktop = atspi.get_desktop(0)
    applications = list(_children(desktop))
    owned_pids = process_tree_ids(process_id)
    owned = []
    for application in applications:
        try:
            if int(application.get_process_id()) in owned_pids:
                owned.append(application)
        except Exception:
            continue
    # Every Xvfb backend owns a private D-Bus accessibility session. If the
    # 1C launcher has reparented its GUI process, the session itself remains a
    # safe boundary and is more reliable than accepting a global desktop app.
    return owned or applications


def focus_application_window(roots: list[Any]) -> dict[str, Any]:
    queue = deque((root, 0) for root in roots)
    candidates: list[tuple[int, int, Any]] = []
    visited = 0
    preferred_roles = {"frame", "window", "dialog"}
    while queue and visited < 10000:
        accessible, depth = queue.popleft()
        visited += 1
        role = _safe_role(accessible).casefold()
        priority = 0 if role in preferred_roles else 1
        candidates.append((priority, depth, accessible))
        for child in _children(accessible):
            queue.append((child, depth + 1))
    for _, _, accessible in sorted(candidates, key=lambda item: (item[0], item[1])):
        try:
            component = accessible.get_component_iface()
            if component is not None and component.grab_focus():
                return accessible_info(accessible)
        except Exception:
            continue
    raise AtspiRunnerError("AT-SPI could not focus the tested application window")


def run_atspi_bridge_request(process_id: int, request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("requestId")
    try:
        action = str(request.get("action", "")).casefold()
        if action == "presskey":
            key = str(request.get("key", "")).casefold()
            keysyms = {
                "enter": 0xFF0D, "space": 0x20, "right": 0xFF53, "left": 0xFF51,
                "down": 0xFF54, "up": 0xFF52,
                **{f"f{number}": 0xFFBD + number for number in range(1, 13)},
            }
            if key not in keysyms:
                raise AtspiRunnerError(f"Unsupported AT-SPI bridge key: {key}")
            try:
                actual = send_x11_key(process_id, key)
                return {"ok": True, "requestId": request_id, "status": "uia-response", "actual": actual}
            except Exception as x11_error:
                # Only initialize AT-SPI after the independent X11 path failed.
                # Some minimal Linux workers have no accessibility bus, while
                # XTest remains fully functional on the private Xvfb display.
                atspi = _atspi_module()
                roots = application_roots(atspi, process_id)
                if not roots:
                    raise AtspiRunnerError("AT-SPI desktop contains no applications")
                focused = focus_application_window(roots)
                if not atspi.generate_keyboard_event(keysyms[key], None, atspi.KeySynthType.PRESSRELEASE):
                    raise AtspiRunnerError("AT-SPI key synthesis returned false")
                actual = {"method": "atspiFocusedKey", "key": key, "focused": focused, "x11Error": str(x11_error)}
                return {"ok": True, "requestId": request_id, "status": "uia-response", "actual": actual}

        atspi = _atspi_module()
        roots = application_roots(atspi, process_id)
        if not roots:
            raise AtspiRunnerError("AT-SPI desktop contains no applications")
        if action == "invokeelement":
            title = str(request.get("title") or "")
            element_name = str(request.get("elementName") or "")
            if not title and not element_name:
                raise AtspiRunnerError("invokeElement requires element title or name")
            element = find_accessible_element(roots, [title, element_name])
            actual = invoke_accessible_element(element, atspi)
            return {"ok": True, "requestId": request_id, "status": "uia-response", "actual": actual}
        if action == "expandelement":
            title = str(request.get("title") or "")
            element_name = str(request.get("elementName") or "")
            if not title and not element_name:
                raise AtspiRunnerError("expandElement requires element title or name")
            element = find_accessible_element(roots, [title, element_name])
            actual = expand_accessible_element(element, atspi)
            return {"ok": True, "requestId": request_id, "status": "uia-response", "actual": actual}
        raise AtspiRunnerError(f"Unsupported AT-SPI bridge action: {request.get('action')}")
    except Exception as exc:
        return {
            "ok": False,
            "requestId": request_id,
            "status": "uia-response",
            "error": f"{type(exc).__name__}: {exc}",
        }
