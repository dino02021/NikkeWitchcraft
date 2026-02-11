from __future__ import annotations

import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, line: str) -> None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} - {line}\n")

    def event(self, cat: str, ident: str, action: str, detail: str = "") -> None:
        if detail:
            self.write(f"LOG | {cat} | {ident} | {action} | {detail}")
        else:
            self.write(f"LOG | {cat} | {ident} | {action}")
