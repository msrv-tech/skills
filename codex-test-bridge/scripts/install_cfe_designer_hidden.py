#!/usr/bin/env python3
"""Install a CFE with batch Designer on an isolated desktop."""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui_worker import UiWorkerError, create_backend, wait_for_process  # noqa: E402


def x11_keysym_name(character: str) -> str:
    if len(character) != 1 or character in "\r\n":
        raise ValueError("Authentication values must contain single-line Unicode text")
    return f"U{ord(character):04X}"


def is_authentication_title(title: str) -> bool:
    normalized = title.casefold()
    if normalized.strip() in {"1с:предприятие", "1c:enterprise"}:
        return True
    return any(marker in normalized for marker in (
        "аутентиф", "доступ к информационной базе", "запуск 1с", "запуск 1c",
        "authentication", "infobase access",
    ))


def is_batch_designer_title(title: str) -> bool:
    normalized = title.casefold()
    return normalized.startswith(("конфигуратор", "designer")) or any(marker in normalized for marker in (
        "загрузка конфигурационной информации", "обновление конфигурации базы данных",
        "реорганизация информации", "loading configuration", "updating database configuration",
    ))


def xvfb_display_candidates(
    socket_directory: Path = Path("/tmp/.X11-unix"), temporary_directory: Path = Path("/tmp"),
) -> list[int]:
    return [
        display for display in range(90, 200)
        if not (socket_directory / f"X{display}").exists()
        and not (temporary_directory / f".X{display}-lock").exists()
    ]


def create_installer_backend() -> tuple[object, int | None]:
    config = {
        "backend": "windowsDesktop" if os.name == "nt" else "xvfb",
        "workingDirectory": str(ROOT),
    }
    run_id = f"CfeInstall-{uuid.uuid4().hex}"
    if os.name == "nt":
        return create_backend(config, run_id), None

    configured_display = os.environ.get("CODEX_XVFB_DISPLAY")
    if configured_display is not None:
        display = int(configured_display)
        config["display"] = display
        return create_backend(config, run_id), display

    last_error: Exception | None = None
    for display in xvfb_display_candidates()[:5]:
        config["display"] = display
        try:
            return create_backend(config, run_id), display
        except UiWorkerError as error:
            last_error = error
    raise RuntimeError("No free Xvfb display could be started") from last_error


def submit_linux_authentication(display_number: int, username: str, password: str, process: object) -> bool:
    """Fill the 8.5 Linux authentication window that ignores /N and /P."""
    if os.name == "nt" or not username:
        return False
    x11 = ctypes.CDLL("libX11.so.6")
    xtst = ctypes.CDLL("libXtst.so.6")
    display_pointer = ctypes.c_void_p
    window_type = ctypes.c_ulong
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = display_pointer
    x11.XCloseDisplay.argtypes = [display_pointer]
    x11.XDefaultRootWindow.argtypes = [display_pointer]
    x11.XDefaultRootWindow.restype = window_type
    x11.XQueryTree.argtypes = [
        display_pointer, window_type, ctypes.POINTER(window_type), ctypes.POINTER(window_type),
        ctypes.POINTER(ctypes.POINTER(window_type)), ctypes.POINTER(ctypes.c_uint),
    ]
    x11.XQueryTree.restype = ctypes.c_int
    x11.XGetGeometry.argtypes = [
        display_pointer, window_type, ctypes.POINTER(window_type),
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
    ]
    x11.XGetGeometry.restype = ctypes.c_int
    x11.XTranslateCoordinates.argtypes = [
        display_pointer, window_type, window_type, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(window_type),
    ]
    x11.XTranslateCoordinates.restype = ctypes.c_int
    x11.XFetchName.argtypes = [display_pointer, window_type, ctypes.POINTER(ctypes.c_char_p)]
    x11.XFetchName.restype = ctypes.c_int
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XKeysymToKeycode.argtypes = [display_pointer, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_uint
    x11.XDisplayKeycodes.argtypes = [display_pointer, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    x11.XGetKeyboardMapping.argtypes = [display_pointer, ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    x11.XGetKeyboardMapping.restype = ctypes.POINTER(ctypes.c_ulong)
    x11.XChangeKeyboardMapping.argtypes = [display_pointer, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_ulong), ctypes.c_int]
    x11.XFree.argtypes = [ctypes.c_void_p]
    x11.XFlush.argtypes = [display_pointer]
    x11.XSync.argtypes = [display_pointer, ctypes.c_int]
    xtst.XTestFakeMotionEvent.argtypes = [display_pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    xtst.XTestFakeButtonEvent.argtypes = [display_pointer, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    xtst.XTestFakeKeyEvent.argtypes = [display_pointer, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

    display = x11.XOpenDisplay(f":{display_number}".encode("ascii"))
    if not display:
        return False
    original_mapping = None
    original_keysyms_per_keycode = ctypes.c_int()
    injection_keycode = 0
    try:
        root = x11.XDefaultRootWindow(display)

        def click(window: int, relative_x: int, relative_y: int) -> None:
            root_x = ctypes.c_int(); root_y = ctypes.c_int(); child = window_type()
            x11.XTranslateCoordinates(display, window, root, 0, 0,
                                      ctypes.byref(root_x), ctypes.byref(root_y), ctypes.byref(child))
            xtst.XTestFakeMotionEvent(display, 0, root_x.value + relative_x, root_y.value + relative_y, 0)
            xtst.XTestFakeButtonEvent(display, 1, 1, 0)
            xtst.XTestFakeButtonEvent(display, 1, 0, 0)
            x11.XFlush(display)
            time.sleep(0.1)

        def window_title(window: int) -> str:
            title_pointer = ctypes.c_char_p()
            if not x11.XFetchName(display, window, ctypes.byref(title_pointer)) or not title_pointer.value:
                return ""
            try:
                raw_title = title_pointer.value
                for encoding in ("utf-8", "cp1251"):
                    try:
                        return raw_title.decode(encoding)
                    except UnicodeDecodeError:
                        pass
                return raw_title.decode("utf-8", errors="replace")
            finally:
                x11.XFree(ctypes.cast(title_pointer, ctypes.c_void_p))

        def find_onec_dialog() -> tuple[int, int, int, str] | None:
            returned_root = window_type()
            returned_parent = window_type()
            children = ctypes.POINTER(window_type)()
            count = ctypes.c_uint()
            if x11.XQueryTree(display, root, ctypes.byref(returned_root), ctypes.byref(returned_parent), ctypes.byref(children), ctypes.byref(count)):
                try:
                    for index in range(count.value):
                        window = children[index]
                        geometry_root = window_type()
                        x = ctypes.c_int(); y = ctypes.c_int()
                        width = ctypes.c_uint(); height = ctypes.c_uint()
                        border = ctypes.c_uint(); depth = ctypes.c_uint()
                        if x11.XGetGeometry(display, window, ctypes.byref(geometry_root), ctypes.byref(x), ctypes.byref(y),
                                           ctypes.byref(width), ctypes.byref(height), ctypes.byref(border), ctypes.byref(depth)):
                            title = window_title(int(window))
                            if (is_batch_designer_title(title)
                                    or 250 <= width.value <= 700 and 150 <= height.value <= 500):
                                return int(window), int(width.value), int(height.value), title
                finally:
                    if children:
                        x11.XFree(children)
            return None

        deadline = time.monotonic() + 30
        authentication = None
        while time.monotonic() < deadline and process.poll() is None:
            dialog = find_onec_dialog()
            if dialog is None:
                time.sleep(0.2)
                continue
            dialog_window, dialog_width, dialog_height, dialog_title = dialog
            if is_batch_designer_title(dialog_title):
                return False
            if dialog_height < 250:
                # Batch Designer may show a client/server version warning even
                # with /DisableStartupDialogs. Its only safe action is OK.
                click(dialog_window, max(20, dialog_width - 55), max(20, dialog_height - 45))
                time.sleep(0.5)
                continue
            if not is_authentication_title(dialog_title):
                time.sleep(0.2)
                continue
            authentication = dialog
            if authentication is not None:
                break
        if authentication is None:
            return False

        minimum_keycode = ctypes.c_int()
        maximum_keycode = ctypes.c_int()
        x11.XDisplayKeycodes(display, ctypes.byref(minimum_keycode), ctypes.byref(maximum_keycode))
        injection_keycode = maximum_keycode.value
        original_mapping = x11.XGetKeyboardMapping(
            display, injection_keycode, 1, ctypes.byref(original_keysyms_per_keycode),
        )
        if not original_mapping or original_keysyms_per_keycode.value < 1:
            raise RuntimeError("Cannot reserve an X11 keycode for Unicode authentication input")

        def key(name: str, pressed: bool) -> None:
            symbol = x11.XStringToKeysym(name.encode("ascii"))
            code = x11.XKeysymToKeycode(display, symbol)
            xtst.XTestFakeKeyEvent(display, code, int(pressed), 0)

        def type_unicode(value: str) -> None:
            for character in value:
                symbol = x11.XStringToKeysym(x11_keysym_name(character).encode("ascii"))
                if not symbol:
                    raise RuntimeError("X11 cannot represent a character from the registered credentials")
                mapping = (ctypes.c_ulong * 1)(symbol)
                x11.XChangeKeyboardMapping(display, injection_keycode, 1, mapping, 1)
                x11.XSync(display, 0)
                xtst.XTestFakeKeyEvent(display, injection_keycode, 1, 0)
                xtst.XTestFakeKeyEvent(display, injection_keycode, 0, 0)
            x11.XSync(display, 0)

        for attempt in range(3):
            # The top-level window is mapped before its custom controls consume
            # XTest events. Re-resolve and retry it instead of requiring a human.
            time.sleep(2 + attempt)
            if process.poll() is not None:
                return True
            authentication = find_onec_dialog()
            if authentication is None:
                return True
            authentication_window, window_width, window_height, window_title_value = authentication
            if is_batch_designer_title(window_title_value):
                return True
            if window_height < 250:
                click(authentication_window, max(20, window_width - 55), max(20, window_height - 45))
                continue
            field_x = max(80, window_width // 2)
            # /N already selects the registry user in the 8.5 account combo.
            # Re-typing it would edit search text rather than select an account.
            click(authentication_window, field_x, 220)
            key("Control_L", True); key("a", True); key("a", False); key("Control_L", False)
            type_unicode(password)
            key("Return", True); key("Return", False)
            x11.XSync(display, 0)
            outcome_deadline = time.monotonic() + 10
            while time.monotonic() < outcome_deadline and process.poll() is None:
                dialog = find_onec_dialog()
                if dialog is None:
                    time.sleep(0.2)
                    continue
                dialog_window, dialog_width, dialog_height, dialog_title = dialog
                if is_batch_designer_title(dialog_title):
                    return True
                if dialog_height < 250:
                    click(dialog_window, max(20, dialog_width - 55), max(20, dialog_height - 45))
                    break
                time.sleep(0.2)
        raise RuntimeError("1C authentication window did not accept the registered credentials")
    finally:
        if original_mapping:
            x11.XChangeKeyboardMapping(
                display, injection_keycode, original_keysyms_per_keycode.value, original_mapping, 1,
            )
            x11.XSync(display, 0)
            x11.XFree(original_mapping)
        x11.XCloseDisplay(display)


def read_log(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, help="Path to 1cv8.exe or its bin directory")
    connection = parser.add_mutually_exclusive_group(required=True)
    connection.add_argument("--server")
    connection.add_argument("--database-path")
    parser.add_argument("--database", help="Server infobase name; required with --server")
    parser.add_argument("--user", default="", help="Infobase user; omit for anonymous infobases")
    parser.add_argument("--password-env", default="CODEX_1C_PASSWORD")
    parser.add_argument("--empty-password", action="store_true", help="Use an explicitly empty infobase password")
    parser.add_argument("--extension", default="CodexTestBridge")
    parser.add_argument("--cfe", default=str(ROOT / "codex-test-bridge.cfe"))
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()

    if args.server and not args.database:
        parser.error("--database is required with --server")

    password = os.environ.get(args.password_env)
    if args.empty_password:
        password = ""
    if args.user and password is None:
        raise RuntimeError(f"Environment variable is not set: {args.password_env}")

    platform = Path(args.platform).resolve()
    executable_name = "1cv8.exe" if os.name == "nt" else "1cv8"
    executable = platform / executable_name if platform.is_dir() else platform
    cfe = Path(args.cfe).resolve()
    log = Path(args.log).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"{executable_name} not found: {executable}")
    if not cfe.is_file():
        raise FileNotFoundError(f"CFE not found: {cfe}")
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists():
        log.unlink()

    # The Linux launcher can ignore values passed as the next argv item and
    # open an interactive authentication form. The compact 1C syntax works on
    # both platforms and keeps batch Designer genuinely non-interactive.
    target = [f"/S{args.server}\\{args.database}"] if args.server else [f"/F{Path(args.database_path).resolve()}"]
    password_argument = '/P""' if os.name != "nt" and password == "" else f"/P{password}"
    authentication = [f"/N{args.user}", password_argument] if args.user else []
    command = [
        str(executable), "DESIGNER", *target, *authentication,
        "/DisableStartupDialogs", "/DisableStartupMessages",
        "/LoadCfg", str(cfe), "-Extension", args.extension,
        "/UpdateDBCfg", "/Out", str(log),
    ]

    backend, display_number = create_installer_backend()
    process = None
    try:
        process = backend.start(command)
        if os.name != "nt":
            submit_linux_authentication(int(display_number), args.user, password or "", process)
        exit_code = wait_for_process(process, args.timeout)
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            process.close()
        backend.close()

    details = read_log(log)
    if exit_code != 0:
        raise RuntimeError(f"Designer exited with code {exit_code}: {details or 'no log output'}")
    print(details or "CFE installation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
