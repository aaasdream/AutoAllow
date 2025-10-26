# AutoAllow - VS Code Chat Auto Allow Tool

🤖 自動監控並點擊 VS Code Chat 中的 Allow 按鈕

## 功能特色

- ✅ 支援多個 VS Code 視窗同時監控
- ✅ 自動尋找並點擊 Allow 按鈕
- ✅ 智能跳過無響應視窗
- ✅ 實時監控狀態顯示
- ✅ 詳細的操作日誌
- ✅ 友好的圖形介面

## 系統需求

- Windows 作業系統
- Python 3.7+
- VS Code

## 安裝依賴

```bash
pip install pywin32 psutil pywinauto
```

## 使用方法

1. 運行主程序：
```bash
python auto_GO_gui.py
```

2. 點擊「開始監控」開始自動監控
3. 或點擊「立即掃描」進行單次掃描

## 檔案說明

- `auto_GO_gui.py` - 主程序（GUI 版本）
- `vscode_scanner_main.py` - UI 元素掃描工具

## 工作原理

程序會：
1. 掃描所有開啟的 VS Code 視窗
2. 使用 UI Automation 搜尋 Allow 按鈕
3. 自動點擊找到的按鈕
4. 智能處理連接失敗的情況

## 注意事項

- 程序不會自動開啟新視窗，只監控現有的 VS Code
- 如果視窗無響應，會暫時跳過並稍後重試
- 建議保持程序在背景運行

## 更新日誌

### v2.0 (2025-10-26)
- 🔧 新增智能跳過機制，避免卡在無響應視窗
- 🔧 優化視窗管理，自動清理已關閉視窗
- 🔧 改進日誌輸出，降低錯誤訊息頻率
- 🔧 增強按鈕搜尋深度（30 層）
- 🔧 新增多種點擊方法，提高成功率

## 授權

MIT License

## 作者

aaasdream
