from __future__ import annotations

from collections.abc import Mapping


GAME_KEY_SPECS = (
    ("game_key_spam_a", "A連點", "a"),
    ("game_key_spam_s", "S連點", "s"),
    ("game_key_spam_d", "D連點", "d"),
    ("game_key_jitter_z", "抖槍術 Z", "z"),
    ("game_key_jitter_x", "抖槍術 X", "x"),
    ("game_key_jitter_c", "抖槍術 C", "c"),
    ("game_key_jitter_v", "抖槍術 V", "v"),
    ("game_key_jitter_b", "抖槍術 B", "b"),
)
GAME_KEY_LABELS = {field: label for field, label, _default in GAME_KEY_SPECS}


def normalize_game_key(key_name: str) -> str:
    return key_name.strip().lower()


def duplicate_game_key_groups(values: Mapping[str, str]) -> list[list[str]]:
    value_to_fields: dict[str, list[str]] = {}
    for field, value in values.items():
        value_to_fields.setdefault(normalize_game_key(value), []).append(field)
    return [fields for fields in value_to_fields.values() if len(fields) > 1]
