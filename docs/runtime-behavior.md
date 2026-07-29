# 執行行為細節

> 本文件是 `spec.md` 的補充文件，只描述目前版本的執行細節。
>
> 長期原則與規格入口以 `spec.md` 為準。

## 有效情境

熱鍵只在以下任一條件成立時生效：

- `General.GlobalHotkeys` 已啟用。
- `nikke.exe` 是目前前景程式，且遊戲視窗位於主螢幕。

同一套情境判斷會用在熱鍵觸發、按鍵阻斷、PRESET 2、worker 停止條件與 context 診斷 log。切換全域熱鍵時，阻斷狀態必須立即更新。

前景狀態由 Windows `EVENT_SYSTEM_FOREGROUND` 主動通知，不使用固定間隔輪詢。WinEvent hook 在獨立訊息執行緒接收事件，只能寫入 queue 並透過 `root.after(0, ...)` 排入建立 Tk interpreter 的 main thread；UI、熱鍵情境與游標狀態只能在 main thread 更新。Hook 必須在 Tk mainloop 開始後建立，shutdown 開始後不得再排入 Tk。

## 滑鼠鎖定

`General.CursorLock` 啟用時，只在 `nikke.exe` 位於前景且在主螢幕時，將游標限制在遊戲 client rect。前景切換以及妮姬視窗移動或縮放皆由 Windows event 通知，不使用固定間隔輪詢。

程式只追蹤自己成功設定的限制範圍。離開妮姬、取消設定或結束程式時，只有在 Windows 目前的限制範圍仍等於程式最後設定的範圍，且不等於新前景視窗範圍時才解除一次；若其他程式已設定不同範圍，或新前景可能使用相同範圍，必須保留且不再操作。其他遊戲維持前景期間不得呼叫 `ClipCursor`。

## 按鍵阻斷

hook 只允許阻斷「目前啟用、已綁定、且不是 pass-through」的按鍵。停用、暫停或未綁定的按鍵必須正常穿透。

PRESET 2 的觸發鍵固定為 pass-through，因此 `a`、`s`、`;`、`'` 的原始輸入會保留，程式只監聽它們的按住與放開狀態。

## 滑鼠 Hook

mouse hook 只在需要時安裝：

- 至少有一個已啟用熱鍵綁定到 `left`、`right`、`middle`、`x1`、`x2`。
- UI 正在綁定模式中，需要捕捉下一個滑鼠按鍵。

沒有滑鼠綁定且不在綁定模式時，程式不安裝 mouse hook，也不處理滑鼠事件。若只綁定 `x2`，未綁定的 `left` / `right` 不會進入 HotkeyManager 判斷。

連點啟動前會即時查詢 Windows 目前的 left/right 實體按住狀態；若已按住，會先送出對應 mouse up，再開始連點循環。這個檢查不依賴 mouse hook，因此不需要長期監控未綁定的 left/right。

## 綁定模式

hook callback 不直接操作 Tk 元件。進入綁定模式後，hook thread 只把按鍵名稱放進 queue；Tk main thread 透過 `root.after()` 輪詢 queue，再完成 `_finish_bind()`。

關閉綁定視窗時，必須清掉待綁定目標、關閉 binding capture，並清空已排隊的綁定事件，避免後續按鍵被誤綁。

## 音遊模式 PRESET 2

`General.RhythmPreset2` 預設關閉。

啟用且情境有效時：

- `a` + `s` 同時按住會鎖住 `lshift`。
- `;` + `'` 同時按住會鎖住 `rshift`。
- `a` + `s` + `;` + `'` 四鍵同時按住會鎖住 `space`。

每個輸出鍵只在「當次觸發它的原始觸發鍵集合」全部放開後才釋放。後續補按的新鍵不會延長既有 latch。失去有效情境、關閉 PRESET 2 或程式結束時，必須釋放 `lshift`、`rshift`、`space`。

## 其他設定

`General.MinimizeToTray` 預設啟用。啟用時右上角關閉按鈕會隱藏 UI 到工具列；停用時右上角關閉按鈕會直接結束程式。

`General.HotkeysPaused` 預設關閉。啟用時，按鍵綁定區的熱鍵會停用並從阻斷集合移除，因此原始按鍵會正常穿透。PRESET 2 不受此設定影響，仍由 `General.RhythmPreset2` 獨立控制。

## 啟動參數

程式支援以下命令列參數：

- `--minimized`：使用此參數啟動時，主視窗會直接隱藏（縮小至系統托盤），不顯示主界面。用戶可點擊系統托盤圖示或右鍵選單中的「開啟面板」來還原並顯示主視窗。

## 自動啟動

「開機自啟」設定啟用時，程式會透過 Windows 工作排程器（Task Scheduler）註冊一個名為 `NikkeWitchcraftAutostart` 的任務：
- **觸發程序**：於設定自啟動的當前使用者登入時（AtLogOn -User）啟動，不會影響其他登入這台電腦的使用者。
- **權限層級**：以最高權限（Highest Privilege）執行。這樣可確保程式在開機時直接以系統管理員權限運行，避免 Windows UAC 提權彈窗。
- **啟動參數**：會自動帶上 `--minimized` 參數，以便程式在開機登入後靜默啟動於系統托盤。
- **相容性與清理**：開啟或關閉自啟設定時，會自動檢查並清理舊版本可能殘留在使用者啟動資料夾（`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`）的 `NikkeWitchcraftStarter.lnk` 捷徑檔案。

## 單一實例

新實例啟動時，會先透過每位使用者獨立的 named shutdown event 通知舊實例正常關閉。新版本實例會在 Tk main thread 輪詢此 event，收到後走正常 shutdown 流程。

若舊版本不支援 shutdown event，或逾時仍未結束，才 fallback 強制終止符合條件的舊程序。

## Session Log

每次啟動會在 `%LOCALAPPDATA%\NikkeWitchcraft\Logs` 建立一個 session log。

UI 的「開啟Log資料夾」按鈕會開啟目前 session log 所在資料夾。

hook callback 不同步寫入磁碟。runtime event 會先排入背景 writer queue，於 shutdown 或 fatal exit 時 flush/close。高頻診斷必須 rate-limit；連點與連發類動作只記錄 start/stop summary，不記錄每一次輸出。
