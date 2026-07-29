from __future__ import annotations

import unittest
from unittest.mock import patch

from lib.config import Settings
from lib.cursor_lock import CursorLockController
from lib.winapi import Rect


class _Logger:
    def event(self, *args) -> None:
        pass


class CursorLockControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(is_cursor_lock=True)
        self.controller = CursorLockController(self.settings, _Logger())
        self.nikke_rect = Rect(10, 20, 810, 620)
        self.window_rects = {
            100: self.nikke_rect,
            200: Rect(100, 100, 900, 700),
            300: Rect(200, 200, 1000, 800),
        }
        self.current_clip = None
        self.clip_calls = []

        def clip_cursor(rect):
            self.clip_calls.append(rect)
            self.current_clip = rect
            return True

        self.patches = [
            patch(
                "lib.cursor_lock.winapi.get_client_rect_screen",
                side_effect=lambda hwnd: self.window_rects.get(hwnd),
            ),
            patch("lib.cursor_lock.winapi.get_clip_cursor", side_effect=lambda: self.current_clip),
            patch("lib.cursor_lock.winapi.clip_cursor", side_effect=clip_cursor),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self) -> None:
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def test_other_game_never_changes_cursor_without_owned_lock(self) -> None:
        self.controller.on_foreground(200, "other.exe", True)

        self.assertEqual([], self.clip_calls)

    def test_leaving_nikke_releases_unchanged_owned_lock_once(self) -> None:
        self.controller.on_foreground(100, "nikke.exe", True)
        self.controller.on_foreground(200, "other.exe", True)
        self.controller.on_foreground(300, "another.exe", True)

        self.assertEqual([self.nikke_rect, None], self.clip_calls)

    def test_leaving_nikke_does_not_clear_another_program_lock(self) -> None:
        self.controller.on_foreground(100, "nikke.exe", True)
        other_rect = Rect(0, 0, 1920, 1080)
        self.current_clip = other_rect

        self.controller.on_foreground(200, "other.exe", True)

        self.assertEqual([self.nikke_rect], self.clip_calls)
        self.assertEqual(other_rect, self.current_clip)

    def test_same_size_foreground_window_is_not_unlocked(self) -> None:
        self.controller.on_foreground(100, "nikke.exe", True)
        self.window_rects[200] = self.nikke_rect

        self.controller.on_foreground(200, "other.exe", True)

        self.assertEqual([self.nikke_rect], self.clip_calls)
        self.assertEqual(self.nikke_rect, self.current_clip)

    def test_disabling_releases_owned_lock(self) -> None:
        self.controller.on_foreground(100, "nikke.exe", True)

        self.controller.set_enabled(False)

        self.assertEqual([self.nikke_rect, None], self.clip_calls)

    def test_nikke_location_event_updates_owned_rect(self) -> None:
        self.controller.on_foreground(100, "nikke.exe", True)
        moved_rect = Rect(50, 60, 850, 660)
        self.window_rects[100] = moved_rect
        self.controller.on_window_location_changed(100)

        self.assertEqual([self.nikke_rect, moved_rect], self.clip_calls)


if __name__ == "__main__":
    unittest.main()
