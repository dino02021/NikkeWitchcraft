from __future__ import annotations

import sys
import ctypes
from ctypes import wintypes
import tkinter as tk
import os
import time
from pathlib import Path
from functools import partial

from lib.config import Settings, ConfigStore, APP_NAME, APP_TITLE
from lib.log import Logger, session_log_path
from lib.hotkeys import HotkeyManager, HotkeyDef
from lib.actions import Actions
from lib.cursor_lock import CursorLockController
from lib.gui.ui import AppUI
from lib.autostart import enable_autostart
from lib import winapi
from PIL import Image, ImageDraw
import pystray
import threading
import queue
import faulthandler


_faulthandler_file = None
_app_state = {
    "hk": None,
    "actions": None,
    "cursor_lock": None,
    "icon": None,
    "log": None,
    "closing": False,
    "shutdown_event": None,
}


def ensure_admin(log: Logger) -> None:
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.IsUserAnAdmin.argtypes = []
    shell32.IsUserAnAdmin.restype = wintypes.BOOL
    shell32.ShellExecuteW.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_int,
    ]
    shell32.ShellExecuteW.restype = wintypes.HINSTANCE
    try:
        is_admin = shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    if not is_admin:
        log.event("SYS", "Admin", "request", "state=0")
        params = " ".join(['"%s"' % arg for arg in sys.argv])
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            exe = exe[:-10] + "pythonw.exe"
        rc = shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        if rc <= 32:
            log.event("SYS", "Admin", "requestFail", f"rc={rc}")
            return
        log.close()
        sys.exit(0)
    else:
        log.event("SYS", "Admin", "ok", "state=1")


def main() -> None:
    base_dir = Path.home() / "Documents" / f"{APP_NAME}Settings"
    store = ConfigStore(base_dir)
    settings = store.load(Settings())
    log = Logger(session_log_path(APP_NAME), enabled=False)
    _app_state["log"] = log
    _set_logging_enabled(log, settings.is_log_enabled)
    log.event("SYS", "App", "sessionStart", f"title={APP_TITLE} pid={os.getpid()} path={log.log_path}")
    _install_exception_logging(log)
    ensure_admin(log)
    _signal_existing_instances(log)
    _terminate_existing_instances(log)
    _sync_autostart_setting(settings, store, log)
    winapi.time_begin_period(1)
    log.event("SYS", "timeBeginPeriod", "init", "ok=1")

    hk = HotkeyManager(
        is_context_enabled=partial(_is_context_enabled, settings),
        logger=log,
        context_info=partial(_context_info, settings),
    )
    _app_state["hk"] = hk
    actions = Actions(settings, hk)
    _app_state["actions"] = actions
    cursor_lock = CursorLockController(settings, log)
    _app_state["cursor_lock"] = cursor_lock
    binding_enabled = not settings.is_hotkeys_paused

    hk.define(HotkeyDef("EscMap", settings.key_esc, settings.is_esc_enabled and binding_enabled,
                        lambda stop: actions.run_single_map(settings.key_esc, "esc", stop)))
    hk.define(HotkeyDef("DSpam", settings.key_spam_d, settings.is_spam_d_enabled and binding_enabled,
                        lambda stop: actions.run_spam(settings.key_spam_d, settings.game_key_spam_d, stop)))
    hk.define(HotkeyDef("SSpam", settings.key_spam_s, settings.is_spam_s_enabled and binding_enabled,
                        lambda stop: actions.run_spam(settings.key_spam_s, settings.game_key_spam_s, stop)))
    hk.define(HotkeyDef("ASpam", settings.key_spam_a, settings.is_spam_a_enabled and binding_enabled,
                        lambda stop: actions.run_spam(settings.key_spam_a, settings.game_key_spam_a, stop)))

    hk.define(HotkeyDef("ClickSeq1", settings.key_click1, settings.is_click1_enabled and binding_enabled,
                        lambda stop: actions.run_click("ClickSeq1", settings.key_click1, settings.click_btn1,
                                                       settings.click1_hold_ms, settings.click1_gap_ms, stop),
                        on_release=lambda: actions.request_release_click_output_for_hotkey("ClickSeq1")))
    hk.define(HotkeyDef("ClickSeq2", settings.key_click2, settings.is_click2_enabled and binding_enabled,
                        lambda stop: actions.run_click("ClickSeq2", settings.key_click2, settings.click_btn2,
                                                       settings.click2_hold_ms, settings.click2_gap_ms, stop),
                        on_release=lambda: actions.request_release_click_output_for_hotkey("ClickSeq2")))
    hk.define(HotkeyDef("ClickSeq3", settings.key_click3, settings.is_click3_enabled and binding_enabled,
                        lambda stop: actions.run_click("ClickSeq3", settings.key_click3, settings.click_btn3,
                                                       settings.click3_hold_ms, settings.click3_gap_ms, stop),
                        on_release=lambda: actions.request_release_click_output_for_hotkey("ClickSeq3")))

    hk.define(HotkeyDef("Jitter", settings.key_jitter, settings.is_jitter_enabled and binding_enabled,
                        lambda stop: actions.run_jitter(settings.key_jitter, stop)))
    for key in ("a", "s", ";", "'"):
        hk.define(HotkeyDef(
            f"RhythmPreset2_{key}",
            key,
            settings.is_rhythm_preset2_enabled,
            lambda stop: None,
            pass_through=True,
            on_event=lambda is_down, trigger=key: actions.handle_rhythm_preset2_key(trigger, is_down),
        ))

    hk.start()

    minimized = "--minimized" in sys.argv
    root, ui = _init_ui(settings, store, hk, actions, log, cursor_lock, minimized=minimized)
    _install_foreground_hook(root, ui, log, hk, settings, cursor_lock)
    _install_shutdown_event(root, log)

    tray = pystray.Icon(
        APP_TITLE,
        _build_tray_icon(),
        APP_TITLE,
        menu=pystray.Menu(
            pystray.MenuItem("開啟面板", lambda: root.after(0, partial(_show_ui, root)), default=True),
            pystray.MenuItem("結束", partial(_quit_app, root)),
        ),
    )
    tray.on_activate = lambda icon, item=None: root.after(0, partial(_show_ui, root))
    _app_state["icon"] = tray

    root.protocol("WM_DELETE_WINDOW", partial(_close_ui, root, settings))
    tray.run_detached()
    root.mainloop()


def _is_context_enabled(settings: Settings) -> bool:
    return _context_state(settings)["enabled"]


def _context_info(settings: Settings) -> str:
    state = _context_state(settings)
    return (
        f"global={state['global']} fg={state['fg']} "
        f"primary={state['primary']} exe={state['exe']}"
    )


def _context_state(settings: Settings) -> dict[str, int | str | bool]:
    hwnd = winapi.get_foreground_hwnd()
    exe = "-"
    if hwnd:
        path = winapi.get_process_image(hwnd)
        exe = os.path.basename(path).lower() if path else "-"
    fg = 1 if exe == "nikke.exe" else 0
    primary = 1 if (hwnd and winapi.is_window_on_primary_monitor(hwnd)) else 0
    is_global = 1 if settings.is_global_hotkeys else 0
    enabled = bool(is_global or (fg == 1 and primary == 1))
    return {
        "enabled": enabled,
        "global": is_global,
        "fg": fg,
        "primary": primary,
        "exe": exe,
        "hwnd": hwnd,
    }


def _sync_autostart_setting(settings: Settings, store: ConfigStore, log: Logger) -> None:
    if not settings.is_auto_start or settings.is_autostart_task_migrated:
        return
    try:
        enable_autostart()
        settings.is_autostart_task_migrated = True
        store.save(settings)
        log.event("SYS", "AutoStart", "sync", "ok=1")
    except Exception as exc:
        log.event("SYS", "AutoStart", "syncFail", f"err={exc}")


def _init_ui(
    settings: Settings,
    store: ConfigStore,
    hk: HotkeyManager,
    actions: Actions,
    log: Logger,
    cursor_lock: CursorLockController,
    minimized: bool = False,
) -> tuple[tk.Tk, AppUI]:
    try:
        # Enable High DPI awareness to prevent window and text blurriness under Windows display scaling
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        root = tk.Tk()
        root.withdraw()
        root.report_callback_exception = lambda exc, val, tb: log.event("SYS", "UI", "exception", f"err={val}")
        ui = AppUI(
            root,
            settings,
            store,
            hk,
            actions,
            log,
            on_logging_changed=partial(_set_logging_enabled, log),
            on_cursor_lock_changed=cursor_lock.set_enabled,
        )
        log.event("SYS", "UI", "init", f"ok=1 minimized={int(minimized)}")
        root.update_idletasks()
        if not minimized:
            _show_ui(root)
        return root, ui
    except Exception as exc:
        log.event("SYS", "UI", "initFail", f"err={exc}")
        raise


def _install_foreground_hook(
    root: tk.Tk,
    ui: AppUI,
    log: Logger,
    hk: HotkeyManager,
    settings: Settings,
    cursor_lock: CursorLockController,
) -> None:
    state = {"last": None}
    event_queue: queue.SimpleQueue[tuple[str, int, str, int, int]] = queue.SimpleQueue()
    dispatch_state = {"scheduled": False}
    dispatch_lock = threading.Lock()

    def drain_events() -> None:
        with dispatch_lock:
            dispatch_state["scheduled"] = False
        latest_location = 0
        while True:
            try:
                kind, fg, exe, hwnd, is_primary = event_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "foreground":
                _handle_foreground_update(
                    ui,
                    log,
                    hk,
                    settings,
                    cursor_lock,
                    fg,
                    exe,
                    hwnd,
                    is_primary,
                )
            elif kind == "location":
                latest_location = hwnd
        if latest_location:
            cursor_lock.on_window_location_changed(latest_location)

    def enqueue_event(kind: str, fg: int, exe: str, hwnd: int, is_primary: int) -> None:
        if _app_state.get("closing"):
            return
        event_queue.put((kind, fg, exe, hwnd, is_primary))
        with dispatch_lock:
            if dispatch_state["scheduled"]:
                return
            dispatch_state["scheduled"] = True
        try:
            root.after(0, drain_events)
        except Exception as exc:
            with dispatch_lock:
                dispatch_state["scheduled"] = False
            log.event("SYS", "EventDispatcher", "scheduleFail", f"kind={kind} err={exc}")

    def on_foreground(hook, event, hwnd, obj_id, child_id, thread_id, time_ms):
        try:
            path = winapi.get_process_image(hwnd) if hwnd else None
            exe = os.path.basename(path).lower() if path else "-"
            fg = 1 if exe == "nikke.exe" else 0
            is_primary = 1 if hwnd and winapi.is_window_on_primary_monitor(hwnd) else 0
            current = (fg, exe, hwnd, is_primary)
            if state["last"] != current:
                state["last"] = current
                enqueue_event("foreground", fg, exe, hwnd, is_primary)
        except Exception as exc:
            log.event("SYS", "ForegroundHook", "error", f"err={exc}")

    def on_location(hook, event, hwnd, obj_id, child_id, thread_id, time_ms):
        try:
            if obj_id != winapi.OBJID_WINDOW or child_id != winapi.CHILDID_SELF:
                return
            if not cursor_lock.is_active_window(hwnd):
                return
            enqueue_event("location", 0, "-", hwnd, 0)
        except Exception as exc:
            log.event("SYS", "LocationHook", "error", f"err={exc}")

    def start_hooks() -> None:
        if _app_state.get("closing"):
            return
        hook_state = winapi.start_window_event_hooks(on_foreground, on_location)
        setattr(root, "_window_event_hooks", hook_state)
        if not hook_state.foreground_hook:
            log.event("SYS", "ForegroundHook", "initFail", f"err={hook_state.foreground_error}")
        else:
            log.event("SYS", "ForegroundHook", "init", "ok=1")
        if not hook_state.location_hook:
            log.event("SYS", "LocationHook", "initFail", f"err={hook_state.location_error}")
        else:
            log.event("SYS", "LocationHook", "init", "ok=1")
        hwnd = winapi.get_foreground_hwnd()
        on_foreground(0, 0, hwnd, 0, 0, 0, 0)

    root.after(0, start_hooks)


def _handle_foreground_update(
    ui: AppUI,
    log: Logger,
    hk: HotkeyManager,
    settings: Settings,
    cursor_lock: CursorLockController,
    fg: int,
    exe: str,
    hwnd: int,
    is_primary: int,
) -> None:
    if _app_state.get("closing"):
        return
    cursor_lock.on_foreground(hwnd, exe, bool(is_primary))
    is_global = 1 if settings.is_global_hotkeys else 0
    suppress = 1 if (is_global or (fg == 1 and is_primary == 1)) else 0
    log.event(
        "SYS",
        "Context",
        "foreground",
        f"fg={fg} exe={exe} primary={is_primary} global={is_global} suppress={suppress}",
    )
    hk.set_key_blocking(bool(suppress))
    if not suppress:
        ui.actions.release_rhythm_preset2()
    ui.set_game_state(fg, exe)


def _show_ui(root: tk.Tk) -> None:
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))


def _close_ui(root: tk.Tk, settings: Settings) -> None:
    log: Logger | None = _app_state.get("log")
    if not settings.is_minimize_to_tray:
        _shutdown_app(root, "close")
        return
    if log:
        log.event("SYS", "App", "close", "start")
    root.withdraw()
    if log:
        log.event("SYS", "App", "close", "done")


def _quit_app(root: tk.Tk, icon, item=None) -> None:
    _shutdown_app(root, "quit", icon)


def _build_tray_icon() -> Image.Image:
    try:
        icon_path = Path(__file__).resolve().parent / "assets" / "app.png"
        return Image.open(icon_path).convert("RGBA")
    except Exception:
        img = Image.new("RGB", (64, 64), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle((8, 8, 56, 56), outline=(255, 255, 255), width=3)
        draw.text((18, 18), "NW", fill=(255, 255, 255))
        return img


def _shutdown_app(root: tk.Tk, reason: str, icon=None) -> None:
    if _app_state.get("closing"):
        return
    _app_state["closing"] = True
    log: Logger | None = _app_state.get("log")
    try:
        if log:
            log.event("SYS", "App", "shutdown", f"reason={reason} step=start")
        cursor_lock: CursorLockController | None = _app_state.get("cursor_lock")
        if cursor_lock:
            cursor_lock.close()
        hk: HotkeyManager | None = _app_state.get("hk")
        if hk:
            if log:
                log.event("SYS", "App", "shutdown", "step=hotkeys_stop")
            hk.stop()
        actions: Actions | None = _app_state.get("actions")
        if actions:
            actions.release_click_outputs()
            actions.release_rhythm_preset2()
            actions.close()
        window_event_hooks: winapi.WinEventHookState | None = getattr(root, "_window_event_hooks", None)
        if window_event_hooks:
            if log:
                log.event("SYS", "App", "shutdown", "step=window_events_stop")
            winapi.stop_window_event_hooks(window_event_hooks)
        if log:
            log.event("SYS", "App", "shutdown", "step=destroy")
        root.after(0, root.destroy)
        icon = icon or _app_state.get("icon")
        if icon:
            if log:
                log.event("SYS", "App", "shutdown", "step=tray_stop")
            icon.stop()
        winapi.time_end_period(1)
        if log:
            log.event("SYS", "timeEndPeriod", "shutdown", "ok=1")
        if log:
            log.event("SYS", "App", "shutdown", "step=done")
    except Exception as exc:
        if log:
            log.event("SYS", "App", "shutdownFail", f"err={exc}")
    finally:
        _close_shutdown_event()
        _disable_faulthandler()
        if log:
            log.close()


def _install_exception_logging(log: Logger) -> None:
    def _hook(exc_type, exc, tb):
        log.event("SYS", "App", "crash", f"err={exc}")
    sys.excepthook = _hook
    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            log.event("SYS", "Thread", "crash", f"err={args.exc_value}")
        threading.excepthook = _thread_hook


def _set_logging_enabled(log: Logger, enabled: bool) -> None:
    if enabled == log.is_enabled():
        return
    if enabled:
        log.set_enabled(True)
        _enable_faulthandler(log.log_path)
        log.event("SYS", "Log", "enabled", f"path={log.log_path}")
    else:
        _disable_faulthandler()
        log.set_enabled(False)


def _enable_faulthandler(log_path: Path) -> None:
    global _faulthandler_file
    _disable_faulthandler()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _faulthandler_file = open(log_path, "a", encoding="utf-8")
    faulthandler.enable(_faulthandler_file)


def _disable_faulthandler() -> None:
    global _faulthandler_file
    try:
        faulthandler.disable()
    except Exception:
        pass
    if _faulthandler_file:
        try:
            _faulthandler_file.close()
        except Exception:
            pass
        _faulthandler_file = None


def _shutdown_event_name() -> str:
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "default"
    safe = "".join(ch if ch.isalnum() else "_" for ch in user)
    return f"Local\\{APP_NAME}_Shutdown_{safe}"


def _signal_existing_instances(log: Logger) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    EVENT_MODIFY_STATE = 0x0002
    handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, _shutdown_event_name())
    if not handle:
        log.event("SYS", "SingleInstance", "signalSkip", "reason=no_shutdown_event")
        return
    try:
        ok = kernel32.SetEvent(handle)
        log.event("SYS", "SingleInstance", "signal", f"ok={int(bool(ok))}")
    finally:
        kernel32.CloseHandle(handle)
    time.sleep(1.5)


def _install_shutdown_event(root: tk.Tk, log: Logger) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
    kernel32.ResetEvent.restype = wintypes.BOOL

    handle = kernel32.CreateEventW(None, True, False, _shutdown_event_name())
    if not handle:
        log.event("SYS", "SingleInstance", "eventInitFail", f"err={ctypes.get_last_error()}")
        return
    kernel32.ResetEvent(handle)
    _app_state["shutdown_event"] = handle
    log.event("SYS", "SingleInstance", "eventInit", "ok=1")

    def _poll_shutdown_event() -> None:
        if _app_state.get("closing"):
            return
        if kernel32.WaitForSingleObject(handle, 0) == 0:
            kernel32.ResetEvent(handle)
            log.event("SYS", "SingleInstance", "shutdownSignal", "received=1")
            _shutdown_app(root, "single_instance")
            return
        root.after(250, _poll_shutdown_event)

    root.after(250, _poll_shutdown_event)


def _close_shutdown_event() -> None:
    handle = _app_state.get("shutdown_event")
    if not handle:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(handle)
    _app_state["shutdown_event"] = None


def _terminate_existing_instances(log: Logger) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    current_pid = os.getpid()
    current_exe = os.path.normcase(os.path.abspath(sys.executable))

    def _get_process_image(pid: int) -> str | None:
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            buf_len = wintypes.DWORD(4096)
            buf = ctypes.create_unicode_buffer(buf_len.value)
            ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(buf_len))
            if not ok:
                return None
            return buf.value
        finally:
            kernel32.CloseHandle(handle)

    def enum_proc(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return 1
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if not buf.value.startswith(APP_NAME):
            return 1
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and pid.value != current_pid:
            img = _get_process_image(pid.value)
            if not img:
                return 1
            if os.path.normcase(os.path.abspath(img)) != current_exe:
                return 1
            handle = kernel32.OpenProcess(0x0001, False, pid.value)
            if handle:
                log.event("SYS", "SingleInstance", "terminateFallback", f"pid={pid.value}")
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
        return 1

    cb = EnumWindowsProc(enum_proc)
    user32.EnumWindows(cb, 0)






if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log = _app_state.get("log") or Logger(session_log_path(APP_NAME), enabled=False)
        log.event("SYS", "App", "fatal", f"err={exc}")
        log.close()
        raise
