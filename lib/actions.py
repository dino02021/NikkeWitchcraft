from __future__ import annotations

import threading

from .config import Settings
from .hotkeys import HotkeyManager
from . import winapi


class Actions:
    def __init__(self, settings: Settings, hotkeys: HotkeyManager):
        self.s = settings
        self.hk = hotkeys

    def is_context_enabled(self) -> bool:
        return self.s.is_global_hotkeys or winapi.is_foreground_exe("nikke.exe")

    def panic(self) -> None:
        for key in ["DSpam", "SSpam", "ASpam", "ClickSeq1", "ClickSeq2", "ClickSeq3"]:
            self.hk.stop_hotkey(key)

    def run_spam(self, trigger_key: str, output_key: str, stop_ev: threading.Event) -> None:
        while self.hk.should_run(trigger_key, stop_ev):
            self._press_key(output_key)
            if not self.hk.wait_ms_cancel(self.s.key_spam_delay_ms, trigger_key, stop_ev):
                break

    def run_click(self, key_name: str, btn_name: str, hold_ms: int, gap_ms: int, stop_ev: threading.Event) -> None:
        btn_pressed_name = "left" if btn_name.lower() == "lbutton" else "right"
        trigger_norm = key_name.strip().lower()
        self.hk.log.event(
            "ACT",
            "Click",
            "pre",
            f"btn_pressed_name={btn_pressed_name} btn_name={btn_name} trigger={trigger_norm}",
        )
        released_any = False
        if self.hk.is_pressed("left") and trigger_norm != "left":
            self._release_click("LButton")
            released_any = True
        if self.hk.is_pressed("right") and trigger_norm != "right":
            self._release_click("RButton")
            released_any = True
        if released_any:
            if not self.hk.wait_ms_cancel(gap_ms, key_name, stop_ev):
                return
        try:
            while self.hk.should_run(key_name, stop_ev):
                self._hold_click(btn_name)
                if not self.hk.wait_ms_cancel(hold_ms, key_name, stop_ev):
                    break
                self._release_click(btn_name)
                if not self.hk.wait_ms_cancel(gap_ms, key_name, stop_ev):
                    break
        finally:
            self._release_click(btn_name)

    def _key_from_name(self, name: str):
        n = name.strip().lower()
        if len(n) == 1:
            return n
        return n

    def _press_key(self, name: str) -> None:
        key = self._key_from_name(name)
        if not key:
            return
        winapi.send_key_tap(key)

    def _click(self, btn_name: str) -> None:
        winapi.send_mouse_click(btn_name)

    def _hold_click(self, btn_name: str) -> None:
        winapi.send_mouse_down(btn_name)

    def _release_click(self, btn_name: str) -> None:
        winapi.send_mouse_up(btn_name)
