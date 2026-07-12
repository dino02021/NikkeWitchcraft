from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

TASK_NAME = "NikkeWitchcraftAutostart"


def enable_autostart(target_path: Path | None = None) -> None:
    resolved_target, args, work_dir = _resolve_launch_target(target_path)

    # 自動啟動時，加上 --minimized 參數使其開機直接縮小至系統托盤
    if args:
        task_args = f"{args} --minimized"
    else:
        task_args = "--minimized"

    # 註冊工作排程器任務
    try:
        _create_task_powershell(TASK_NAME, resolved_target, task_args)
    except Exception as e:
        # 如果 PowerShell 失敗，fallback 使用 Windows 內建的 schtasks
        try:
            _create_task_schtasks(TASK_NAME, resolved_target, task_args)
        except Exception as exc:
            raise RuntimeError(f"無法建立工作排程器任務：{exc}") from exc

    # 建立新 task 成功後再清理舊版 Startup 捷徑，避免 task 建立失敗時自啟被移除。
    try:
        old_link = _startup_link_path()
        if old_link.exists():
            old_link.unlink()
    except Exception:
        pass


def disable_autostart() -> None:
    # 嘗試清理舊版本的啟動資料夾捷徑
    try:
        old_link = _startup_link_path()
        if old_link.exists():
            old_link.unlink()
    except Exception:
        pass

    # 刪除工作排程器任務
    cmd = [
        "schtasks",
        "/delete",
        "/tn", TASK_NAME,
        "/f"
    ]
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except Exception:
        pass


def _startup_link_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "NikkeWitchcraftStarter.lnk"
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


def _resolve_launch_target(target_path: Path | None) -> tuple[Path, str, Path]:
    if target_path is not None:
        tp = Path(target_path).resolve()
        return tp, "", tp.parent

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return exe, "", exe.parent

    script = Path(__file__).resolve().parents[1] / "main.py"
    exe = Path(sys.executable).resolve()
    if exe.name.lower() == "python.exe":
        pyw = exe.with_name("pythonw.exe")
        if pyw.exists():
            exe = pyw
    args = f'"{script}"'
    return exe, args, script.parent


def _create_task_powershell(task_name: str, target_path: Path, arguments: str) -> None:
    def esc(text: str) -> str:
        return text.replace("'", "''")

    username = os.environ.get("USERNAME", "")
    userdomain = os.environ.get("USERDOMAIN", "")
    if username and userdomain:
        user_id = f"{esc(userdomain)}\\{esc(username)}"
        user_trigger = f"-User '{user_id}'"
        user_principal = f"-UserId '{user_id}' -LogonType Interactive"
    else:
        user_trigger = ""
        user_principal = ""

    # 建立登入時自動啟動、最高權限且取消筆電電池限制的排程任務
    ps_script = (
        f"$action = New-ScheduledTaskAction -Execute '{esc(str(target_path))}' -Argument '{esc(arguments)}'; "
        f"$trigger = New-ScheduledTaskTrigger -AtLogOn {user_trigger}; "
        f"$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
        f"$principal = New-ScheduledTaskPrincipal -RunLevel Highest {user_principal}; "
        f"Register-ScheduledTask -TaskName '{esc(task_name)}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force"
    )

    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=True,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _create_task_schtasks(task_name: str, target_path: Path, arguments: str) -> None:
    exe_str = str(target_path)
    task_run_cmd = f'"{exe_str}" {arguments}'
    cmd = [
        "schtasks",
        "/create",
        "/tn", task_name,
        "/tr", task_run_cmd,
        "/sc", "onlogon",
        "/rl", "highest",
        "/f"
    ]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
