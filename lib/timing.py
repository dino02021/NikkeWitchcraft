from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable
from . import winapi

@dataclass
class WaitProfile:
    long_ms: int = 14
    mid_ms: int = 1
    short_ms: int = 0


def wait_ms_cancel(ms: int, is_cancelled: Callable[[], bool], profile: WaitProfile | None = None) -> bool:
    if profile is None:
        profile = WaitProfile()
    start = _qpc_now_ns()
    target = start + int(ms * 1_000_000)
    while True:
        if is_cancelled():
            return False
        now = _qpc_now_ns()
        if now >= target:
            return True
        remaining_ms = (target - now) / 1_000_000
        if remaining_ms >= 16:
            winapi.msg_wait(profile.long_ms)
        elif remaining_ms >= 2:
            winapi.msg_wait(profile.mid_ms)
        else:
            winapi.msg_wait(profile.short_ms)


def sleep_ms(ms: int) -> None:
    winapi.msg_wait(ms)


def _qpc_now_ns() -> int:
    return time.perf_counter_ns()
