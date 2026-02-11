from __future__ import annotations

import subprocess
from pathlib import Path


def enable_autostart(target_path: Path) -> None:
    link = _startup_link_path()
    link.parent.mkdir(parents=True, exist_ok=True)
    cmd = (
        "$s=(New-Object -COM WScript.Shell).CreateShortcut('{link}');"
        "$s.TargetPath='{target}';"
        "$s.WorkingDirectory='{workdir}';"
        "$s.Save()"
    ).format(link=str(link), target=str(target_path), workdir=str(target_path.parent))
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False)


def disable_autostart() -> None:
    link = _startup_link_path()
    if not link.exists():
        return
    link.unlink()


def _startup_link_path() -> Path:
    return (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "NikkeWitchcraftStarter.lnk"
    )
