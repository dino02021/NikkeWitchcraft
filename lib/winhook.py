from __future__ import annotations

import ctypes
from ctypes import wintypes
import threading
import time
from typing import Callable

from . import winapi

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_QUIT = 0x0012
HC_ACTION = 0


ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32
LRESULT = ctypes.c_ssize_t
WPARAM = wintypes.WPARAM
LPARAM = wintypes.LPARAM


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


LowLevelProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, LowLevelProc, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, WPARAM, LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL


class HookState:
    def __init__(self) -> None:
        self.thread: threading.Thread | None = None
        self.tid: int | None = None
        self.h_kb = None
        self.h_ms = None
        self.kb_cb = None
        self.ms_cb = None
        self.hook_error_count = 0
        self.fail_open_enabled = False
        self._stop = threading.Event()


def _vk_to_name(vk: int) -> str | None:
    # Map common VKs to names used in config
    if 0x41 <= vk <= 0x5A:
        return chr(vk + 32)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if vk == 0x1B:
        return "esc"
    if vk == 0x08:
        return "backspace"
    if vk == 0x09:
        return "tab"
    if vk == 0x0D:
        return "enter"
    if vk == 0x20:
        return "space"
    if vk == 0x10:
        return "shift"
    if vk == 0x11:
        return "ctrl"
    if vk == 0x12:
        return "alt"
    if vk == 0x5B:
        return "cmd"
    if 0x70 <= vk <= 0x87:
        return f"f{vk - 0x6F}"
    return None


def _mouse_name(msg: int, mouseData: int) -> str | None:
    if msg in (WM_LBUTTONDOWN, WM_LBUTTONUP):
        return "left"
    if msg in (WM_RBUTTONDOWN, WM_RBUTTONUP):
        return "right"
    if msg in (WM_MBUTTONDOWN, WM_MBUTTONUP):
        return "middle"
    if msg in (WM_XBUTTONDOWN, WM_XBUTTONUP):
        xbtn = (mouseData >> 16) & 0xFFFF
        if xbtn == 1:
            return "x1"
        if xbtn == 2:
            return "x2"
    return None


def start_hooks(
    on_key: Callable[[str, bool], bool],
    on_mouse: Callable[[str, bool], bool],
    on_log: Callable[[str, str, str, str], None] | None = None,
    on_auto_fail_open: Callable[[], None] | None = None,
) -> HookState:
    state = HookState()
    err_lock = threading.Lock()
    last_err_log_ts = 0.0
    err_log_interval_sec = 1.0
    err_threshold = 10

    def _safe_next(nCode, wParam, lParam):
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _log_error(kind: str, exc: Exception):
        nonlocal last_err_log_ts
        state.hook_error_count += 1
        now = time.monotonic()
        with err_lock:
            if on_log and (now - last_err_log_ts >= err_log_interval_sec):
                last_err_log_ts = now
                on_log("SYS", "HookError", kind, f"count={state.hook_error_count} err={exc}")
        if state.hook_error_count >= err_threshold and not state.fail_open_enabled:
            state.fail_open_enabled = True
            if on_auto_fail_open:
                on_auto_fail_open()
            if on_log:
                on_log("SYS", "HookError", "autoFailOpen", f"count={state.hook_error_count}")

    def kb_proc(nCode, wParam, lParam):
        try:
            if state.fail_open_enabled:
                return _safe_next(nCode, wParam, lParam)
            if nCode == HC_ACTION:
                data = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                name = _vk_to_name(data.vkCode)
                if name:
                    is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    if on_key(name, is_down):
                        return 1
        except Exception as exc:
            _log_error("keyboard", exc)
        return _safe_next(nCode, wParam, lParam)

    def ms_proc(nCode, wParam, lParam):
        try:
            if state.fail_open_enabled:
                return _safe_next(nCode, wParam, lParam)
            if nCode == HC_ACTION:
                data = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                name = _mouse_name(wParam, data.mouseData)
                if name:
                    is_down = wParam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN)
                    if on_mouse(name, is_down):
                        return 1
        except Exception as exc:
            _log_error("mouse", exc)
        return _safe_next(nCode, wParam, lParam)

    def run():
        state.tid = kernel32.GetCurrentThreadId()
        state.kb_cb = LowLevelProc(kb_proc)
        state.ms_cb = LowLevelProc(ms_proc)
        state.h_kb = user32.SetWindowsHookExW(WH_KEYBOARD_LL, state.kb_cb, 0, 0)
        state.h_ms = user32.SetWindowsHookExW(WH_MOUSE_LL, state.ms_cb, 0, 0)
        if on_log:
            if not state.h_kb or not state.h_ms:
                err = ctypes.get_last_error()
                on_log("SYS", "Hook", "initFail", f"hkb={int(bool(state.h_kb))} hms={int(bool(state.h_ms))} err={err}")
                state.fail_open_enabled = True
                if on_auto_fail_open:
                    on_auto_fail_open()
            on_log("SYS", "Hook", "init", f"tid={state.tid} hkb={int(bool(state.h_kb))} hms={int(bool(state.h_ms))}")
        msg = wintypes.MSG()
        while not state._stop.is_set() and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if state.h_kb:
            user32.UnhookWindowsHookEx(state.h_kb)
        if state.h_ms:
            user32.UnhookWindowsHookEx(state.h_ms)

    t = threading.Thread(target=run, daemon=True)
    state.thread = t
    t.start()
    return state


def stop_hooks(state: HookState) -> None:
    if not state:
        return
    state._stop.set()
    if state.tid:
        user32.PostThreadMessageW(state.tid, WM_QUIT, 0, 0)
    if state.thread and state.thread.is_alive():
        state.thread.join(timeout=2.0)
