from __future__ import annotations

import configparser
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.actions import Actions
from lib.config import ConfigStore, Settings
from lib.game_keys import GAME_KEY_SPECS, duplicate_game_key_groups
from lib.hotkeys import HotkeyManager
from lib import winapi


class _Logger:
    def event(self, *args) -> None:
        pass


class _JitterHotkeys:
    def __init__(self) -> None:
        self.log = _Logger()
        self._should_run_calls = 0

    def should_run(self, _trigger_key, _stop_event) -> bool:
        self._should_run_calls += 1
        return self._should_run_calls <= 6

    def wait_ms_cancel(self, _ms, _trigger_key, _stop_event) -> bool:
        return True


class GameKeyConfigTests(unittest.TestCase):
    def test_old_config_uses_original_output_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(Path(tmp))
            store.ini_path.write_text("[General]\nMinimizeToTray=1\n", encoding="utf-8")

            settings = store.load(Settings())

        actual = {field: getattr(settings, field) for field, _label, _default in GAME_KEY_SPECS}
        expected = {field: default for field, _label, default in GAME_KEY_SPECS}
        self.assertEqual(expected, actual)

    def test_game_keys_round_trip(self) -> None:
        custom = ["q", "w", "e", "r", "t", "y", "u", "i"]
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(Path(tmp))
            settings = Settings()
            for (field, _label, _default), value in zip(GAME_KEY_SPECS, custom):
                setattr(settings, field, value)

            store.save(settings)
            loaded = store.load(Settings())
            parser = configparser.ConfigParser()
            parser.read(store.ini_path, encoding="utf-8")

        self.assertTrue(parser.has_section("GameKeys"))
        self.assertEqual(custom, [getattr(loaded, field) for field, _label, _default in GAME_KEY_SPECS])

    def test_duplicate_outputs_are_detected_case_insensitively(self) -> None:
        values = {field: default for field, _label, default in GAME_KEY_SPECS}
        values["game_key_spam_a"] = "Q"
        values["game_key_jitter_z"] = "q"

        groups = duplicate_game_key_groups(values)

        self.assertEqual([["game_key_spam_a", "game_key_jitter_z"]], groups)


class GameKeyCaptureTests(unittest.TestCase):
    def test_keyboard_only_binding_ignores_mouse_but_accepts_arrow_key(self) -> None:
        manager = HotkeyManager(lambda: True, _Logger())
        manager.set_binding_callback(lambda _name: None, allow_mouse=False)

        manager._on_hook_mouse("left", True)
        self.assertIsNone(manager.poll_binding_key())

        manager._on_hook_key("left", True)
        self.assertEqual("left", manager.poll_binding_key())

    def test_captured_keyboard_names_can_be_sent(self) -> None:
        for key_name in ("a", "1", ";", "left", "f24", "num5", "lshift", "vk_e8"):
            with self.subTest(key_name=key_name):
                self.assertTrue(winapi.can_send_key(key_name))


class GameKeyActionTests(unittest.TestCase):
    def test_jitter_keeps_logical_order_with_configured_outputs(self) -> None:
        settings = Settings(
            game_key_jitter_z="q",
            game_key_jitter_x="w",
            game_key_jitter_c="e",
            game_key_jitter_v="r",
            game_key_jitter_b="t",
        )
        actions = Actions(settings, _JitterHotkeys())
        try:
            with patch("lib.actions.winapi.send_key_tap") as send_key_tap:
                actions.run_jitter("f20", threading.Event())
        finally:
            actions.close()

        self.assertEqual(
            ["q", "w", "e", "r", "t"],
            [call.args[0] for call in send_key_tap.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()
