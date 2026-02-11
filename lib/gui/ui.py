from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from ..config import Settings, ConfigStore, APP_TITLE
from ..log import Logger
from ..hotkeys import HotkeyManager
from ..actions import Actions
from ..autostart import enable_autostart, disable_autostart
from .layout import (
    create_frame,
    create_entry_frame,
    create_btn_frame,
    create_btn_between,
    create_btn_last,
    create_entry_label,
    create_entry,
    create_msg_label,
    create_checkbutton,
    create_dialog,
    close_dialog,
)
from . import ui_constants as ui


class AppUI:
    def __init__(self, root: tk.Tk, settings: Settings, store: ConfigStore, hk: HotkeyManager, actions: Actions, logger: Logger):
        self.root = root
        self.s = settings
        self.store = store
        self.hk = hk
        self.actions = actions
        self.log = logger

        self.root.title(APP_TITLE)
        self.root.resizable(False, False)

        self._binding_target: str | None = None
        self._bind_tip: tk.Toplevel | None = None
        self._status_var = tk.StringVar()
        self._status_label: ttk.Label | None = None
        self._apply_msg_var = tk.StringVar()
        self._hotkey_vars: dict[str, tk.StringVar] = {}
        self._delay_vars: dict[str, tk.StringVar] = {}
        self._panic_var = tk.StringVar()
        self._click_info_vars = {
            "ClickSeq1": tk.StringVar(),
            "ClickSeq2": tk.StringVar(),
            "ClickSeq3": tk.StringVar(),
        }
        self._click_warn_vars = {
            "ClickSeq1": tk.StringVar(),
            "ClickSeq2": tk.StringVar(),
            "ClickSeq3": tk.StringVar(),
        }

        self._build()
        self._refresh()

    def _build(self) -> None:
        container = create_frame(self.root)
        try:
            icon_path = Path(__file__).resolve().parents[2] / "assets" / "app.png"
            if icon_path.exists():
                self.root.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
        except Exception:
            pass
        row = 0

        bind_frame = create_entry_frame(container, row=row, column=0)
        bind_frame.columnconfigure(1, weight=1, uniform="hotkey")
        bind_frame.columnconfigure(2, weight=0)
        bind_frame.columnconfigure(3, weight=0)
        bind_frame.columnconfigure(4, weight=0)

        create_entry_label(bind_frame, "按鍵綁定：", row=0, column=0)
        hotkey_frame = create_entry_frame(bind_frame, row=1, column=0)
        self._row_hotkey(hotkey_frame, 1, "D連點：", "DSpam")
        self._row_hotkey(hotkey_frame, 2, "S連點：", "SSpam")
        self._row_hotkey(hotkey_frame, 3, "A連點：", "ASpam")
        self._row_click(hotkey_frame, 4, "連點1：", "ClickSeq1")
        self._row_click(hotkey_frame, 5, "連點2：", "ClickSeq2")
        self._row_click(hotkey_frame, 6, "連點3：", "ClickSeq3")
        self._row_panic(hotkey_frame, 7, "逃脫鍵：")
        row += 1

        self._add_separator(container, row)
        row += 1

        delay_frame = create_entry_frame(container, row=row, column=0)
        
        create_entry_label(delay_frame, "延遲設定：", row=0, column=0)
        self._row_delay(delay_frame, 1, "連點1", "ClickSeq1")
        self._row_delay(delay_frame, 2, "連點2", "ClickSeq2")
        self._row_delay(delay_frame, 3, "連點3", "ClickSeq3")

        btn_frame = create_btn_frame(delay_frame, row=4, column=0)
        create_btn_last(btn_frame, "套用延遲", self._apply_delays, row=0, column=0, sticky="w")
        msg_label = create_msg_label(btn_frame, self._apply_msg_var, row=0, column=1, sticky="w")
        msg_label.configure(foreground="green")

        info_frame = create_entry_frame(delay_frame, row=5, column=0)
        self._add_click_info(info_frame, 0, "ClickSeq1")
        self._add_click_info(info_frame, 1, "ClickSeq2")
        self._add_click_info(info_frame, 2, "ClickSeq3")
        row += 1

        self._add_separator(container, row)
        row += 1

        opt_frame = create_entry_frame(container, row=row, column=0)
        
        create_entry_label(opt_frame, "其他設定：", row=0, column=0)
        other_frame = create_entry_frame(opt_frame, row=1, column=0)
        self.chk_autostart = tk.IntVar()
        create_checkbutton(other_frame, "開機時自動啟動", self.chk_autostart, self._toggle_autostart, row=0, column=0)
        self.chk_cursor_lock = tk.IntVar()
        create_checkbutton(other_frame, "鎖定滑鼠於遊戲視窗內", self.chk_cursor_lock, self._toggle_cursor_lock, row=1, column=0)
        self.chk_global_hotkeys = tk.IntVar()
        create_checkbutton(other_frame, "全域啟用熱鍵", self.chk_global_hotkeys, self._toggle_global_hotkeys, row=2, column=0)

        btn_row = create_btn_frame(opt_frame, row=3, column=0)
        create_btn_between(btn_row, "開啟設定資料夾", self._open_settings, row=0, column=0, sticky="w", pady=ui.LABEL_PADY)
        create_btn_between(btn_row, "匯出設定", self._export_settings, row=0, column=1, sticky="w")
        create_btn_last(btn_row, "匯入設定", self._import_settings, row=0, column=2, sticky="w")
        row += 1

        self._add_separator(container, row)
        row += 1
        
        status_frame = create_entry_frame(container, row=row, column=0)
        self._status_label = create_msg_label(status_frame, self._status_var, row=0, column=0, padx=0)

    def _row_hotkey(self, parent, row: int, label: str, hid: str) -> None:
        create_entry_label(parent, label, row=row, column=0)
        var = tk.StringVar()
        ent = create_entry(parent, var, row=row, column=1)
        ent.configure(state="readonly")
        self._hotkey_vars[hid] = var
        setattr(self, f"edit_{hid}", ent)
        btn_frame = create_btn_frame(parent, row=row, column=2, padding=(0, 0, 0, 0), pady=ui.ENTRY_PADY)
        create_btn_between(btn_frame, "變更", lambda: self._start_bind(hid), row=0, column=0, sticky="w")
        var_chk = tk.IntVar()
        chk = ttk.Checkbutton(parent, text="啟用", variable=var_chk, command=lambda: self._toggle_enabled(hid, var_chk))
        chk.grid(row=row, column=3, sticky="w", padx=ui.LABEL_PADX)
        setattr(self, f"chk_{hid}", var_chk)

    def _row_click(self, parent, row: int, label: str, hid: str) -> None:
        self._row_hotkey(parent, row, label, hid)
        btn_frame = create_btn_frame(parent, row=row, column=4, padding=(0, 0, 0, 0), pady=ui.ENTRY_PADY)
        btn = create_btn_last(btn_frame, "左鍵", lambda: self._toggle_click_button(hid), row=0, column=0, sticky="w")
        setattr(self, f"btn_{hid}", btn)

    def _row_delay(self, parent, row: int, title: str, hid: str) -> None:
        row_frame = create_entry_frame(parent, row=row, column=0)
        hold_var = tk.StringVar()
        gap_var = tk.StringVar()
        create_entry_label(row_frame, f"{title}：按住 (ms)", row=0, column=0)
        ent_hold = create_entry(row_frame, hold_var, row=0, column=1)
        ent_hold.configure(width=12)
        create_entry_label(row_frame, f"{title}：休息 (ms)", row=1, column=0)
        ent_gap = create_entry(row_frame, gap_var, row=1, column=1)
        ent_gap.configure(width=12)
        self._delay_vars[f"{hid}_hold"] = hold_var
        self._delay_vars[f"{hid}_gap"] = gap_var
        setattr(self, f"edit_{hid}_hold", ent_hold)
        setattr(self, f"edit_{hid}_gap", ent_gap)

    def _row_panic(self, parent, row: int, label: str) -> None:
        create_entry_label(parent, label, row=row, column=0, pady=ui.ENTRY_LABEL_PADY)
        ent = create_entry(parent, self._panic_var, row=row, column=1, pady=ui.ENTRY_PADY)
        ent.configure(state="readonly", width=12)
        self.edit_panic = ent
        btn_frame = create_btn_frame(parent, row=row, column=2, padding=(0, 0, 0, 0), pady=ui.ENTRY_PADY)
        create_btn_between(btn_frame, "變更", lambda: self._start_bind("Panic"), row=0, column=0, sticky="w")
        self.chk_panic = tk.IntVar()
        chk = ttk.Checkbutton(parent, text="啟用", variable=self.chk_panic, command=self._toggle_panic)
        chk.grid(row=row, column=3, sticky="w", padx=ui.LABEL_PADX, pady=ui.ENTRY_LABEL_PADY)

    def _add_click_info(self, parent, row: int, hid: str) -> None:
        lbl = ttk.Label(parent, textvariable=self._click_info_vars[hid])
        lbl.grid(row=row, column=0, sticky="w")
        warn = ttk.Label(parent, textvariable=self._click_warn_vars[hid], foreground="red")
        warn.grid(row=row, column=1, sticky="w", padx=ui.LABEL_PADX, pady=ui.LABEL_PADY)

    def _add_separator(self, parent, row: int) -> None:
        sep_frame = ttk.Frame(parent)
        sep_frame.grid(row=row, column=0, sticky="ew", padx=ui.FRAME_GRID_PADX, pady=ui.FRAME_GRID_PADY)
        sep_frame.columnconfigure(0, weight=1)
        ttk.Separator(sep_frame, orient="horizontal").grid(row=0, column=0, sticky="ew")

    def _start_bind(self, hid: str) -> None:
        self._binding_target = hid
        if self._bind_tip:
            close_dialog(self._bind_tip)
        self._bind_tip = create_dialog(self.root, "綁定", 220, 90)
        dlg_frame = create_frame(self._bind_tip)
        create_entry_label(dlg_frame, "請按下要綁定的按鍵", row=0, column=0, sticky="w")
        self.hk.set_binding_callback(self._finish_bind)

    def _finish_bind(self, key_name: str) -> None:
        hid = self._binding_target
        self._binding_target = None
        self.hk.set_binding_callback(None)
        if self._bind_tip:
            close_dialog(self._bind_tip)
            self._bind_tip = None
        if not hid:
            return
        if hid == "DSpam":
            self.s.key_spam_d = key_name
        elif hid == "SSpam":
            self.s.key_spam_s = key_name
        elif hid == "ASpam":
            self.s.key_spam_a = key_name
        elif hid == "ClickSeq1":
            self.s.key_click1 = key_name
        elif hid == "ClickSeq2":
            self.s.key_click2 = key_name
        elif hid == "ClickSeq3":
            self.s.key_click3 = key_name
        elif hid == "Panic":
            self.s.key_panic = key_name
        self._apply_hotkey_defs()
        self.store.save(self.s)
        self._refresh()

    def _toggle_enabled(self, hid: str, var: tk.IntVar) -> None:
        val = var.get() != 0
        if hid == "DSpam":
            self.s.is_spam_d_enabled = val
        elif hid == "SSpam":
            self.s.is_spam_s_enabled = val
        elif hid == "ASpam":
            self.s.is_spam_a_enabled = val
        elif hid == "ClickSeq1":
            self.s.is_click1_enabled = val
        elif hid == "ClickSeq2":
            self.s.is_click2_enabled = val
        elif hid == "ClickSeq3":
            self.s.is_click3_enabled = val
        self._apply_hotkey_defs()
        self.store.save(self.s)

    def _toggle_panic(self) -> None:
        self.s.is_panic_enabled = self.chk_panic.get() != 0
        self._apply_hotkey_defs()
        self.store.save(self.s)

    def _toggle_click_button(self, hid: str) -> None:
        if hid == "ClickSeq1":
            self.s.click_btn1 = "RButton" if self.s.click_btn1 == "LButton" else "LButton"
        elif hid == "ClickSeq2":
            self.s.click_btn2 = "RButton" if self.s.click_btn2 == "LButton" else "LButton"
        elif hid == "ClickSeq3":
            self.s.click_btn3 = "RButton" if self.s.click_btn3 == "LButton" else "LButton"
        self.store.save(self.s)
        self._refresh()

    def _toggle_autostart(self) -> None:
        self.s.is_auto_start = self.chk_autostart.get() != 0
        if self.s.is_auto_start:
            enable_autostart(Path(__file__).resolve().parents[1] / "main.py")
        else:
            disable_autostart()
        self.store.save(self.s)

    def _toggle_cursor_lock(self) -> None:
        self.s.is_cursor_lock = self.chk_cursor_lock.get() != 0
        self.store.save(self.s)

    def _toggle_global_hotkeys(self) -> None:
        self.s.is_global_hotkeys = self.chk_global_hotkeys.get() != 0
        self.store.save(self.s)

    def _apply_delays(self) -> None:
        try:
            self.s.click1_hold_ms = max(1, int(self.edit_ClickSeq1_hold.get()))
            self.s.click1_gap_ms = max(1, int(self.edit_ClickSeq1_gap.get()))
            self.s.click2_hold_ms = max(1, int(self.edit_ClickSeq2_hold.get()))
            self.s.click2_gap_ms = max(1, int(self.edit_ClickSeq2_gap.get()))
            self.s.click3_hold_ms = max(1, int(self.edit_ClickSeq3_hold.get()))
            self.s.click3_gap_ms = max(1, int(self.edit_ClickSeq3_gap.get()))
        except ValueError:
            messagebox.showerror("延遲設定", "請輸入有效的數字")
            return
        self.store.save(self.s)
        self._apply_msg_var.set("已套用延遲")
        self._update_click_info()
        self.root.after(5000, lambda: self._apply_msg_var.set(""))

    def _open_settings(self) -> None:
        self.store.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(self.store.base_dir))
        except Exception:
            pass

    def _export_settings(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".ini", filetypes=[("INI", "*.ini")])
        if not path:
            return
        self.store.save(self.s)
        Path(path).write_bytes(self.store.ini_path.read_bytes())

    def _import_settings(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("INI", "*.ini")])
        if not path:
            return
        Path(self.store.ini_path).write_bytes(Path(path).read_bytes())
        self.store.load(self.s)
        self._apply_hotkey_defs()
        self._refresh()

    def _apply_hotkey_defs(self) -> None:
        self.hk.update_key("DSpam", self.s.key_spam_d)
        self.hk.update_key("SSpam", self.s.key_spam_s)
        self.hk.update_key("ASpam", self.s.key_spam_a)
        self.hk.update_key("ClickSeq1", self.s.key_click1)
        self.hk.update_key("ClickSeq2", self.s.key_click2)
        self.hk.update_key("ClickSeq3", self.s.key_click3)
        self.hk.update_key("Panic", self.s.key_panic)

        self.hk.update_enabled("DSpam", self.s.is_spam_d_enabled)
        self.hk.update_enabled("SSpam", self.s.is_spam_s_enabled)
        self.hk.update_enabled("ASpam", self.s.is_spam_a_enabled)
        self.hk.update_enabled("ClickSeq1", self.s.is_click1_enabled)
        self.hk.update_enabled("ClickSeq2", self.s.is_click2_enabled)
        self.hk.update_enabled("ClickSeq3", self.s.is_click3_enabled)
        self.hk.update_enabled("Panic", self.s.is_panic_enabled)

    def _refresh(self) -> None:
        self._hotkey_vars["DSpam"].set(self.s.key_spam_d)
        self._hotkey_vars["SSpam"].set(self.s.key_spam_s)
        self._hotkey_vars["ASpam"].set(self.s.key_spam_a)
        self._hotkey_vars["ClickSeq1"].set(self.s.key_click1)
        self._hotkey_vars["ClickSeq2"].set(self.s.key_click2)
        self._hotkey_vars["ClickSeq3"].set(self.s.key_click3)
        self._panic_var.set(self.s.key_panic)

        self.chk_DSpam.set(1 if self.s.is_spam_d_enabled else 0)
        self.chk_SSpam.set(1 if self.s.is_spam_s_enabled else 0)
        self.chk_ASpam.set(1 if self.s.is_spam_a_enabled else 0)
        self.chk_ClickSeq1.set(1 if self.s.is_click1_enabled else 0)
        self.chk_ClickSeq2.set(1 if self.s.is_click2_enabled else 0)
        self.chk_ClickSeq3.set(1 if self.s.is_click3_enabled else 0)
        self.chk_panic.set(1 if self.s.is_panic_enabled else 0)

        self.btn_ClickSeq1.config(text="✓左鍵" if self.s.click_btn1 == "LButton" else "✓右鍵")
        self.btn_ClickSeq2.config(text="✓左鍵" if self.s.click_btn2 == "LButton" else "✓右鍵")
        self.btn_ClickSeq3.config(text="✓左鍵" if self.s.click_btn3 == "LButton" else "✓右鍵")

        self._delay_vars["ClickSeq1_hold"].set(str(self.s.click1_hold_ms))
        self._delay_vars["ClickSeq1_gap"].set(str(self.s.click1_gap_ms))
        self._delay_vars["ClickSeq2_hold"].set(str(self.s.click2_hold_ms))
        self._delay_vars["ClickSeq2_gap"].set(str(self.s.click2_gap_ms))
        self._delay_vars["ClickSeq3_hold"].set(str(self.s.click3_hold_ms))
        self._delay_vars["ClickSeq3_gap"].set(str(self.s.click3_gap_ms))

        self.chk_autostart.set(1 if self.s.is_auto_start else 0)
        self.chk_cursor_lock.set(1 if self.s.is_cursor_lock else 0)
        self.chk_global_hotkeys.set(1 if self.s.is_global_hotkeys else 0)

        self._apply_hotkey_defs()
        self._update_click_info()
        self._update_status()

    def _update_click_info(self) -> None:
        mapping = {
            "ClickSeq1": ("連點1", self.s.click1_hold_ms, self.s.click1_gap_ms),
            "ClickSeq2": ("連點2", self.s.click2_hold_ms, self.s.click2_gap_ms),
            "ClickSeq3": ("連點3", self.s.click3_hold_ms, self.s.click3_gap_ms),
        }
        for hid in ["ClickSeq1", "ClickSeq2", "ClickSeq3"]:
            label, hold, gap = mapping[hid]
            total = hold + gap
            cps = 1000.0 / total if total > 0 else 0.0
            self._click_info_vars[hid].set(f"{label}：{hold} + {gap} = {total} ms (約 {cps:.2f} 次/秒)")
            if cps > 4.1:
                self._click_warn_vars[hid].set("#超速警告")
            else:
                self._click_warn_vars[hid].set("")

    def _update_status(self) -> None:
        from .. import winapi
        exe = winapi.get_foreground_exe_name() or "-"
        fg = 1 if winapi.is_foreground_exe("nikke.exe") else 0
        self.set_game_state(fg, exe)

    def set_game_state(self, fg: int, exe: str | None) -> None:
        exe_name = exe or "-"
        self._status_var.set(f"遊戲狀態：{'前景' if fg else '背景'}")
        if self._status_label:
            self._status_label.configure(foreground="green" if fg else "red")
        last = getattr(self, "_last_game_state", None)
        current = (fg, exe_name)
        if last != current:
            self._last_game_state = current
            if exe_name.lower() == "nikke.exe":
                self.log.event("UI", "GameState", "event", f"fg={fg} exe={exe_name}")
