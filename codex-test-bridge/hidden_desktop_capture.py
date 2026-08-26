#!/usr/bin/env python3
"""Capture the largest visible window of a process on a hidden Windows desktop."""

from __future__ import annotations

import argparse
import ctypes
import struct
from ctypes import wintypes
from pathlib import Path


def capture_window(desktop_name: str, process_id: int, output: str | Path) -> Path:
    if not hasattr(ctypes, "WinDLL"):
        raise RuntimeError("Hidden desktop capture is available only on Windows")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    handle = wintypes.HANDLE
    user32.OpenDesktopW.restype = handle
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowDC.argtypes = [wintypes.HWND]
    user32.GetWindowDC.restype = handle
    user32.PrintWindow.argtypes = [wintypes.HWND, handle, wintypes.UINT]
    gdi32.CreateCompatibleDC.argtypes = [handle]
    gdi32.CreateCompatibleDC.restype = handle
    gdi32.CreateCompatibleBitmap.argtypes = [handle, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = handle
    gdi32.SelectObject.argtypes = [handle, handle]
    gdi32.SelectObject.restype = handle
    gdi32.DeleteObject.argtypes = [handle]
    gdi32.DeleteDC.argtypes = [handle]
    user32.ReleaseDC.argtypes = [wintypes.HWND, handle]
    user32.CloseDesktop.argtypes = [handle]
    gdi32.GetDIBits.argtypes = [handle, handle, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    desktop = user32.OpenDesktopW(desktop_name, 0, False, 0x10000000)
    if not desktop:
        raise ctypes.WinError(ctypes.get_last_error())
    windows: list[tuple[int, int, wintypes.RECT]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd: int, _lparam: int) -> bool:
        pid = wintypes.DWORD()
        rect = wintypes.RECT()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == process_id and user32.IsWindowVisible(hwnd) and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
            windows.append((area, hwnd, rect))
        return True

    try:
        user32.EnumDesktopWindows(desktop, callback_type(collect), 0)
        if not windows:
            raise RuntimeError(f"No visible window found for process {process_id}")
        _area, hwnd, rect = max(windows, key=lambda item: item[0])
        width, height = rect.right - rect.left, rect.bottom - rect.top
        window_dc = user32.GetWindowDC(hwnd)
        memory_dc = gdi32.CreateCompatibleDC(window_dc)
        bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
        previous = gdi32.SelectObject(memory_dc, bitmap)
        try:
            if not user32.PrintWindow(hwnd, memory_dc, 2):
                raise ctypes.WinError(ctypes.get_last_error())

            class BitmapInfo(ctypes.Structure):
                _fields_ = [
                    ("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG),
                    ("planes", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
                    ("size_image", wintypes.DWORD), ("xppm", wintypes.LONG), ("yppm", wintypes.LONG),
                    ("used", wintypes.DWORD), ("important", wintypes.DWORD),
                ]

            image_size = width * height * 4
            info = BitmapInfo(ctypes.sizeof(BitmapInfo), width, -height, 1, 32, 0, image_size, 0, 0, 0, 0)
            pixels = (ctypes.c_ubyte * image_size)()
            if not gdi32.GetDIBits(memory_dc, bitmap, 0, height, pixels, ctypes.byref(info), 0):
                raise ctypes.WinError(ctypes.get_last_error())
            destination = Path(output).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            offset = 54
            with destination.open("wb") as target:
                target.write(struct.pack("<2sIHHI", b"BM", offset + image_size, 0, 0, offset))
                target.write(struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, image_size, 0, 0, 0, 0))
                target.write(bytes(pixels))
            return destination
        finally:
            gdi32.SelectObject(memory_dc, previous)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(hwnd, window_dc)
    finally:
        user32.CloseDesktop(desktop)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--desktop", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(capture_window(args.desktop, args.pid, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
