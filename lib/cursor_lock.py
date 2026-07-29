from __future__ import annotations

from .config import Settings
from .log import Logger
from . import winapi


class CursorLockController:
    def __init__(self, settings: Settings, log: Logger) -> None:
        self._settings = settings
        self._log = log
        self._active_hwnd = 0
        self._owned_rect: winapi.Rect | None = None

    def is_active_window(self, hwnd: int) -> bool:
        return bool(hwnd) and hwnd == self._active_hwnd

    def on_foreground(self, hwnd: int, exe: str, is_primary: bool) -> None:
        target_hwnd = hwnd if exe.lower() == "nikke.exe" and is_primary else 0
        if target_hwnd != self._active_hwnd:
            foreground_rect = winapi.get_client_rect_screen(hwnd) if hwnd and not target_hwnd else None
            self._release_owned("foreground_change", preserve_rect=foreground_rect)
            self._active_hwnd = target_hwnd
        if self._active_hwnd and self._settings.is_cursor_lock:
            self._apply("foreground")

    def on_window_location_changed(self, hwnd: int) -> None:
        if not self.is_active_window(hwnd) or not self._settings.is_cursor_lock:
            return
        self._apply("location")

    def set_enabled(self, enabled: bool) -> None:
        self._settings.is_cursor_lock = enabled
        if enabled and self._active_hwnd:
            self._apply("enabled")
        elif not enabled:
            self._release_owned("disabled")

    def close(self) -> None:
        self._release_owned("shutdown")
        self._active_hwnd = 0

    def _apply(self, reason: str) -> None:
        rect = winapi.get_client_rect_screen(self._active_hwnd)
        if not rect or rect.width <= 0 or rect.height <= 0:
            return
        if rect == self._owned_rect and winapi.get_clip_cursor() == rect:
            return
        if winapi.clip_cursor(rect):
            self._owned_rect = rect
            self._log.event(
                "SYS",
                "CursorLock",
                "apply",
                f"reason={reason} hwnd={self._active_hwnd} rect={rect.left},{rect.top},{rect.right},{rect.bottom}",
            )

    def _release_owned(self, reason: str, preserve_rect: winapi.Rect | None = None) -> None:
        owned_rect = self._owned_rect
        if owned_rect is None:
            return
        current_rect = winapi.get_clip_cursor()
        if current_rect != owned_rect:
            self._owned_rect = None
            self._log.event("SYS", "CursorLock", "releaseSkip", f"reason={reason} owner=changed")
            return
        if preserve_rect == current_rect:
            self._owned_rect = None
            self._log.event("SYS", "CursorLock", "releaseSkip", f"reason={reason} owner=foreground")
            return
        ok = winapi.clip_cursor(None)
        if ok:
            self._owned_rect = None
        self._log.event("SYS", "CursorLock", "release", f"reason={reason} ok={int(ok)}")
