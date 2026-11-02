"""Small Win32 helpers via ctypes (no hard pywin32 dependency)."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"

if IS_WIN:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WDA_EXCLUDEFROMCAPTURE = 0x11


def foreground_window() -> tuple[int, int, str, str]:
    """(hwnd, pid, title, exe_name) of the active window."""
    if not IS_WIN:
        return 0, 0, "", ""
    try:
        hwnd = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        return hwnd, pid.value, buf.value, process_exe(pid.value)
    except Exception:
        return 0, 0, "", ""


def process_exe(pid: int) -> str:
    if not IS_WIN or not pid:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(h)


def exclude_from_capture(hwnd: int) -> bool:
    """Hide a window from screen capture so the overlay is never OCR'd (Win10 2004+)."""
    if not IS_WIN:
        return False
    try:
        return bool(user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


def monitor_rects() -> dict[str, tuple[int, int, int, int]]:
    """Physical-pixel rectangle of each monitor, keyed by device name (\\\\.\\DISPLAY1)."""
    out: dict[str, tuple[int, int, int, int]] = {}
    if not IS_WIN:
        return out

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                                         ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, _hdc, _rect, _data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            out[info.szDevice] = (r.left, r.top, r.right, r.bottom)
        return 1

    try:
        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(cb), 0)
    except Exception:
        pass
    return out
