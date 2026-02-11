# NikkeWitchcraft 規格

> 本文件定義功能與開發規範，所有新增/修改請依此執行。

## 目標與範圍
- 以 Python 重構 Nikke 小工具，功能等效於 AHK 版本。
- Windows 10 / 11 可用。
- 多熱鍵可同時執行，互不排隊、不搶占。
- 以低負擔為目標，計時精度優先。

## 設定與檔案
- 設定資料夾：`%USERPROFILE%\Documents\NikkeWitchcraftSettings`
- 設定檔：`NikkeWitchcraftSettings.ini`
- 日誌：`NikkeWitchcraftDebug.log`

### 設定項目
- 連點延遲
  - Click1_HoldMs, Click1_GapMs
  - Click2_HoldMs, Click2_GapMs
  - Click3_HoldMs, Click3_GapMs
  - KeySpamDelayMs
- 綁定鍵
  - DSpam, SSpam, ASpam
  - ClickSeq1, ClickSeq2, ClickSeq3
  - Panic
- 啟用狀態
  - DSpam, SSpam, ASpam
  - ClickSeq1, ClickSeq2, ClickSeq3
  - Panic
- 連點按鍵方向
  - ClickSeq1_Button, ClickSeq2_Button, ClickSeq3_Button
- 系統選項
  - AutoStart
  - CursorLock
  - GlobalHotkeys

## 功能說明
### D/S/A 連點
- 由綁定鍵觸發 D/S/A 按鍵連點。
- 透過 `KeySpamDelayMs` 控制節奏。

### 連點 1/2/3
- 綁定鍵觸發滑鼠左/右鍵連點。
- 進入循環前若目標滑鼠鍵已按住，先放開並休息一次 gap。
- 進入循環後：hold → gap 交替。

### 逃脫鍵（Panic）
- 立即停止所有連點與熱鍵狀態。

## 前景/全域邏輯
- 僅檢查 `nikke.exe` 是否前景。
- UI 只顯示「遊戲狀態：前景/背景」。
- 非前景時：熱鍵穿透；前景時：阻斷原生輸入。
- 啟用全域熱鍵時：全域阻斷。

## 游標鎖定
- 啟用後，使用 WinAPI `ClipCursor` 將游標限制在遊戲視窗範圍。
- 解鎖時立即恢復。

## UI 規範
- 視窗標題：`NikkeWitchcraft v1.0`。
## 版本
- 版本定義：`APP_VERSION`（`lib/config.py`）。
- 標題來源：`APP_TITLE`（`lib/config.py`）。
- 佈局順序：由上到下、由左到右。
- 區塊順序
  - D/S/A 連點
  - 連點 1/2/3（含左/右切換）
  - 逃脫鍵
  - 延遲設定 + 套用延遲
  - 連點次/秒與超速提示
  - 自動啟動 / 游標鎖定 / 全域熱鍵
  - 狀態列

## 計時與等待
- 以 QPC/perf_counter 為基準。
- 分段等待策略
  - remaining >= 16ms → WaitMsg(14)
  - remaining >= 2ms → WaitMsg(1)
  - else → WaitMsg(0)

## 命名與程式風格
- 檔案一律 UTF-8；中文正常顯示。
- bool 以 `is_` 開頭；對外函式置頂，對內函式 `_` 開頭且置底。
- 對內函式不得巢狀在對外函式內，統一拉到檔案下方維護。
- if 盡量採用反向條件提前跳出，避免多層巢狀縮排。
- 對話框統一使用 `create_dialog(...)`，必須 `grab_set + transient + close_dialog`。

## 測試
- 最少執行 `python -m py_compile` 於修改檔以確認語法正確。

## UI 常數（lib/gui/ui_constants.py）
- 所有 padding / 間距集中在此檔；數值以 DEFAULT_PAD 為基準。
- 分類：FRAME/LIST、按鈕框與 Grid、按鈕間距、訊息區、標籤區。

## 套用原則
- 所有 UI 最外層一定使用 `create_frame` 包裹。
- 只要有 Listbox，外層 frame 就一定要設定 `rowconfigure(0, weight=1)` 讓列表撐滿。
- Listbox 每列文字左側加一個空白字元；若有「需從列表選擇」的情境，雙擊列表等同「套用選擇」。
- 最下方預設一個訊息 Label：預設空字串；錯誤紅色、成功綠色。
- entry 與 entry_label 外層一定使用 `create_entry_frame`。
- 相連的 entry 必須共用同一個 `create_entry_frame`，避免重複 padding。
- btn 外層一定使用 `create_btn_frame`。
- 輸入框/標籤：用 ENTRY_LABEL_PADX / ENTRY_LABEL_PADY、ENTRY_PADX / ENTRY_PADY。
- ComboBox：用 CB_PADX / CB_PADY。
- 列表：用 LIST_PADX / LIST_PADY。
- 訊息 Label：用 MSG_PADX / MSG_PADY。
- 按鈕列：外框用 BTN_FRAME_PAD，Grid 用 BTN_GRID_PADX/BTN_GRID_PADY；多顆按鈕用 BTN_PADX_BETWEEN，最後一顆用 BTN_PADX_LAST。
- UI 的建立必須按照「左到右、上到下」的順序。
- 禁止使用 `columnspan`。
