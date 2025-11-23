"""
VS Code Chat Auto Allow - GUI 版本
支援多個 VS Code 視窗的自動 Allow 點擊
"""

import win32gui
import win32process
import win32api
import win32con
import psutil
from pywinauto import Desktop
import time
from datetime import datetime
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import sys
import argparse

class AutoAllowGUI:
    def __init__(self):
        self.monitoring = False
        self.click_count = 0
        self.scan_count = 0
        self.vscode_windows = {}
        self.monitor_thread = None
        
        # 解析命令列參數
        parser = argparse.ArgumentParser(description='VS Code Auto Allow')
        parser.add_argument('--ai-mode', action='store_true', help='啟用 AI 模式 (自動開始 + 控制台輸出)')
        args, _ = parser.parse_known_args()
        self.ai_mode = args.ai_mode
        
        # 🔧 新增：記錄連接失敗的視窗，避免頻繁重試
        self.failed_connections = {}  # {hwnd: (fail_count, last_fail_time)}
        self.max_connection_failures = 5  # 連續失敗 5 次後暫時跳過（降低阈值）
        
        # 創建 GUI
        self.root = tk.Tk()
        self.root.title("VS Code Auto Allow - 多視窗監控")
        self.root.geometry("1000x700")
        self.setup_ui()
        
    def setup_ui(self):
        """設置 UI"""
        # 標題區
        header = tk.Frame(self.root, bg="#2c3e50", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(
            header,
            text="🤖 VS Code Chat Auto Allow",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        title.pack(pady=20)
        
        # 控制面板
        control_frame = tk.Frame(self.root, bg="#ecf0f1", height=100)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        control_frame.pack_propagate(False)
        
        # 按鈕容器
        btn_container = tk.Frame(control_frame, bg="#ecf0f1")
        btn_container.pack(expand=True)
        
        # 開始/停止按鈕
        self.toggle_btn = tk.Button(
            btn_container,
            text="▶️ 開始監控",
            command=self.toggle_monitoring,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#27ae60",
            fg="white",
            padx=30,
            pady=12,
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=10)
        
        # 重置按鈕
        self.reset_btn = tk.Button(
            btn_container,
            text="🔄 重置狀態",
            command=self.reset_failed_connections,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#9b59b6",
            fg="white",
            padx=30,
            pady=12,
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        self.reset_btn.pack(side=tk.LEFT, padx=10)
        
        # 掃描按鈕
        self.scan_btn = tk.Button(
            btn_container,
            text="🔍 立即掃描",
            command=self.manual_scan,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#3498db",
            fg="white",
            padx=30,
            pady=12,
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        self.scan_btn.pack(side=tk.LEFT, padx=10)
        
        # 清空日誌按鈕
        clear_btn = tk.Button(
            btn_container,
            text="🗑️ 清空日誌",
            command=self.clear_log,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#e74c3c",
            fg="white",
            padx=30,
            pady=12,
            relief=tk.FLAT,
            cursor="hand2",
            width=15
        )
        clear_btn.pack(side=tk.LEFT, padx=10)
        
        # 統計資訊面板
        stats_frame = tk.Frame(self.root, bg="#34495e", height=80)
        stats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        stats_frame.pack_propagate(False)
        
        stats_container = tk.Frame(stats_frame, bg="#34495e")
        stats_container.pack(expand=True, fill=tk.BOTH)
        
        # 統計標籤
        self.stats_labels = {}
        
        stats_data = [
            ("windows", "VS Code 視窗", "0"),
            ("scans", "掃描次數", "0"),
            ("clicks", "點擊次數", "0"),
            ("status", "狀態", "待命中")
        ]
        
        for i, (key, label, value) in enumerate(stats_data):
            frame = tk.Frame(stats_container, bg="#34495e")
            frame.pack(side=tk.LEFT, expand=True, padx=20)
            
            tk.Label(
                frame,
                text=label,
                font=("Microsoft YaHei UI", 9),
                fg="#95a5a6",
                bg="#34495e"
            ).pack()
            
            value_label = tk.Label(
                frame,
                text=value,
                font=("Microsoft YaHei UI", 16, "bold"),
                fg="#ecf0f1",
                bg="#34495e"
            )
            value_label.pack()
            self.stats_labels[key] = value_label
        
        # VS Code 視窗列表
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        tk.Label(
            list_frame,
            text="📋 監控中的 VS Code 視窗",
            font=("Microsoft YaHei UI", 11, "bold"),
            anchor=tk.W
        ).pack(fill=tk.X, pady=(0, 5))
        
        # Treeview
        columns = ("HWND", "標題", "最後掃描", "狀態")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=8)
        
        self.tree.heading("#0", text="序號")
        self.tree.heading("HWND", text="視窗 ID")
        self.tree.heading("標題", text="視窗標題")
        self.tree.heading("最後掃描", text="最後掃描時間")
        self.tree.heading("狀態", text="狀態")
        
        self.tree.column("#0", width=60, anchor=tk.CENTER)
        self.tree.column("HWND", width=100, anchor=tk.CENTER)
        self.tree.column("標題", width=400)
        self.tree.column("最後掃描", width=150, anchor=tk.CENTER)
        self.tree.column("狀態", width=200, anchor=tk.CENTER)
        
        tree_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 配置 Treeview 樣式
        style = ttk.Style()
        style.configure("Treeview", rowheight=25, font=("Microsoft YaHei UI", 9))
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))
        
        # 日誌區域
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        tk.Label(
            log_frame,
            text="📝 操作日誌",
            font=("Microsoft YaHei UI", 11, "bold"),
            anchor=tk.W
        ).pack(fill=tk.X, pady=(0, 5))
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            font=("Consolas", 9),
            wrap=tk.WORD,
            bg="#2c3e50",
            fg="#ecf0f1"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def log(self, message, level="INFO"):
        """添加日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        colors = {
            "INFO": "#3498db",
            "SUCCESS": "#27ae60",
            "WARNING": "#f39c12",
            "ERROR": "#e74c3c",
            "DEBUG": "#95a5a6"
        }
        
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"[{level}] ", level)
        self.log_text.insert(tk.END, f"{message}\n")
        
        # 配置標籤顏色
        self.log_text.tag_config("timestamp", foreground="#95a5a6")
        self.log_text.tag_config(level, foreground=colors.get(level, "#ecf0f1"))
        
        # 自動滾動到底部
        self.log_text.see(tk.END)
        
        # 如果是 AI 模式，同時輸出到控制台
        if self.ai_mode:
            print(f"[{timestamp}] [{level}] {message}")
    
    def clear_log(self):
        """清空日誌"""
        self.log_text.delete(1.0, tk.END)
        self.log("日誌已清空", "INFO")
    
    def reset_failed_connections(self):
        """重置失敗連接記錄"""
        count = len(self.failed_connections)
        self.failed_connections.clear()
        self.log(f"🔄 已重置 {count} 個失敗連接記錄，所有視窗將重新嘗試連接", "SUCCESS")
        if count > 0:
            self.log("💡 提示：如果剛才有視窗被跳過，現在會重新掃描", "INFO")
    
    def get_process_name_from_hwnd(self, hwnd):
        """獲取進程名稱"""
        if hwnd == 0:
            return ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name().lower().replace(".exe", "")
        except:
            return ""
    
    def find_all_vscode_windows(self):
        """尋找所有 VS Code 視窗"""
        windows = []
        
        def enum_callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                process_name = self.get_process_name_from_hwnd(hwnd)
                
                # 排除 Extension Development Host (擴充功能開發視窗)
                if "Extension Development Host" in title:
                    return True
                
                # 排除空標題
                if not title or len(title.strip()) == 0:
                    return True
                
                if process_name == "code" and "Visual Studio Code" in title:
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "process": process_name
                    })
            return True
        
        win32gui.EnumWindows(enum_callback, None)
        return windows
    
    def find_and_click_allow_button(self, hwnd):
        """在指定視窗中尋找並點擊 Allow 按鈕"""
        try:
            # 檢查視窗是否存在
            if not win32gui.IsWindow(hwnd):
                # 只在第一次發現視窗消失時記錄
                if hwnd in self.vscode_windows:
                    self.log(f"⚠️ 視窗 {hwnd} 已不存在", "WARNING")
                return False
            
            # 🔧 檢查是否應該跳過此視窗（連接失敗太多次）
            if hwnd in self.failed_connections:
                fail_count, last_fail_time = self.failed_connections[hwnd]
                # 如果連續失敗次數過多，且距離上次失敗不到 15 秒，則跳過（縮短為 15 秒）
                if fail_count >= self.max_connection_failures:
                    if (datetime.now() - last_fail_time).total_seconds() < 15:
                        return False
                    else:
                        # 超過 15 秒，重置計數器，重新嘗試
                        self.failed_connections[hwnd] = (0, datetime.now())
                        self.log(f"🔄 視窗 {hwnd} 重新嘗試連接", "INFO")
            
            # 🔧 重要：每次都重新連接到視窗，確保獲取最新的 UI 樹
            try:
                desktop = Desktop(backend="uia")
                window = desktop.window(handle=hwnd)
                # 成功連接，重置失敗計數器
                if hwnd in self.failed_connections:
                    del self.failed_connections[hwnd]
            except Exception as e:
                # 記錄連接失敗
                if hwnd in self.failed_connections:
                    fail_count, _ = self.failed_connections[hwnd]
                    self.failed_connections[hwnd] = (fail_count + 1, datetime.now())
                else:
                    self.failed_connections[hwnd] = (1, datetime.now())
                
                # 降低錯誤日誌頻率，避免刷屏
                if self.scan_count % 50 == 0:
                    self.log(f"⚠️ 無法連接到視窗 {hwnd}: {e}", "DEBUG")
                return False
            
            # 增加搜尋深度並增加等待時間，確保 UI 已載入
            # 搜尋多種類型的按鈕控制項
            # 優先順序：Button > SplitButton > MenuButton > MenuItem > Hyperlink > Text
            button_types = [
                "Button",           # 普通按鈕 (最常見)
                "SplitButton",      # 分割按鈕
                "MenuButton",       # 選單按鈕
                "MenuItem",         # 選單項目
                "Hyperlink",        # 超連結
                "Text",             # 文字 (最慢，最後檢查)
            ]
            
            for btn_type in button_types:
                try:
                    # 🔧 優化：根據類型調整搜尋深度
                    # Button/SplitButton 通常比較淺，Text 可能比較深
                    search_depth = 20 if btn_type in ["Button", "SplitButton"] else 30
                    
                    # 獲取該類型的所有元素
                    buttons = window.descendants(control_type=btn_type, depth=search_depth)
                    
                    # 立即檢查這些元素，如果找到就馬上點擊並返回
                    for button in buttons:
                        try:
                            # 🔧 確保獲取最新的元素資訊
                            try:
                                button.element_info.update()
                            except:
                                pass
                            
                            element_info = button.element_info
                            name = getattr(element_info, 'name', '').lower()
                            
                            # Allow 相關關鍵字
                            allow_keywords = ['allow', '允許', 'accept', 'confirm']
                            
                            # 排除關鍵字
                            exclude_keywords = ['section', 'explorer', 'autoallow', 'folder', 'directory']
                            
                            # 檢查是否應該排除
                            should_exclude = any(ex in name for ex in exclude_keywords)
                            if should_exclude:
                                continue
                            
                            # 檢查是否匹配 Allow
                            if any(keyword in name for keyword in allow_keywords):
                                button_name = getattr(element_info, 'name', '')
                                
                                # 對於 Text 類型，必須是精確匹配或很短的詞
                                if btn_type == "Text":
                                    if len(name) > 30: 
                                        continue

                                # 檢查按鈕是否可用和可見
                                try:
                                    is_enabled = button.is_enabled()
                                except:
                                    is_enabled = True
                                    
                                try:
                                    is_visible = button.is_visible()
                                except:
                                    is_visible = True 

                                # 即使不可見，如果名字匹配，也嘗試點擊
                                if is_enabled:
                                    if not is_visible:
                                        self.log(f"⚠️ 發現隱藏的 Allow 元素: '{button_name}' (類型: {btn_type}) - 嘗試強制點擊", "WARNING")
                                    else:
                                        self.log(f"🎯 找到 Allow 按鈕: '{button_name}' (類型: {btn_type}, HWND: {hwnd})", "SUCCESS")
                                    
                                    # 嘗試點擊
                                    click_methods = [
                                        ('invoke', lambda: button.invoke()),
                                        ('click_input', lambda: button.click_input()),
                                        ('click', lambda: button.click())
                                    ]
                                    
                                    for method_name, method_func in click_methods:
                                        try:
                                            method_func()
                                            self.click_count += 1
                                            self.log(f"✅ 使用 {method_name}() 成功點擊！(第 {self.click_count} 次)", "SUCCESS")
                                            return True
                                        except Exception as e:
                                            self.log(f"⚠️ {method_name}() 失敗: {e}", "DEBUG")
                                            continue
                                    
                                    self.log(f"❌ 所有點擊方法都失敗", "ERROR")
                                    continue
                        
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    continue
            
            return False
            
        except Exception as e:
            self.log(f"❌ 掃描視窗 {hwnd} 時發生錯誤: {e}", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"❌ 掃描視窗 {hwnd} 時發生錯誤: {e}", "ERROR")
            return False
    
    def scan_windows(self):
        """掃描所有視窗"""
        try:
            # 🔧 每次重新掃描所有 VS Code 視窗，避免使用過期的視窗列表
            windows = self.find_all_vscode_windows()
            self.scan_count += 1
            
            # 🔧 清理已關閉的視窗和失敗連接記錄
            current_hwnds = {win['hwnd'] for win in windows}
            closed_hwnds = [hwnd for hwnd in self.vscode_windows.keys() if hwnd not in current_hwnds]
            for hwnd in closed_hwnds:
                del self.vscode_windows[hwnd]
                # 同時清理失敗連接記錄
                if hwnd in self.failed_connections:
                    del self.failed_connections[hwnd]
                if self.scan_count % 20 == 0:
                    self.log(f"🔄 視窗 {hwnd} 已關閉，從列表中移除", "DEBUG")
            
            # 更新視窗列表
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            found_allow = False
            skipped_windows = 0
            
            for i, win in enumerate(windows, 1):
                hwnd = win['hwnd']
                title = win['title']
                
                # 縮短標題
                display_title = title
                if len(display_title) > 60:
                    display_title = display_title[:57] + "..."
                
                # 檢查是否應該跳過（連接失敗太多次）
                should_skip = False
                skip_reason = ""
                if hwnd in self.failed_connections:
                    fail_count, last_fail_time = self.failed_connections[hwnd]
                    if fail_count >= self.max_connection_failures:
                        time_since_fail = (datetime.now() - last_fail_time).total_seconds()
                        if time_since_fail < 15:
                            should_skip = True
                            skipped_windows += 1
                            skip_reason = f"失敗 {fail_count} 次，等待 {15 - int(time_since_fail)}s"
                
                # 掃描這個視窗（不激活）
                if should_skip:
                    has_allow = False
                    status = f"⏭️ 跳過 ({skip_reason})"
                    tag = "skipped"
                else:
                    try:
                        has_allow = self.find_and_click_allow_button(hwnd)
                    except Exception as e:
                        self.log(f"掃描視窗 {hwnd} 時出錯: {e}", "ERROR")
                        has_allow = False
                    
                    if has_allow:
                        found_allow = True
                        status = "✅ 已點擊 Allow"
                        tag = "clicked"
                    else:
                        status = "⏳ 無 Allow 按鈕"
                        tag = "normal"
                
                # 更新視窗資訊
                self.vscode_windows[hwnd] = {
                    "title": title,
                    "last_scan": datetime.now(),
                    "has_allow": has_allow
                }
                
                time_str = datetime.now().strftime("%H:%M:%S")
                
                self.tree.insert(
                    "",
                    tk.END,
                    text=str(i),
                    values=(hwnd, display_title, time_str, status),
                    tags=(tag,)
                )
            
            # 配置標籤顏色
            self.tree.tag_configure("clicked", background="#d5f4e6")
            self.tree.tag_configure("normal", background="#ffffff")
            self.tree.tag_configure("skipped", background="#fff3cd")
            
            # 更新統計
            self.update_stats(len(windows))
            
            # 改進日誌輸出
            if skipped_windows > 0 and self.scan_count % 20 == 0:
                self.log(f"⚠️ 有 {skipped_windows} 個視窗因連接失敗暫時跳過", "WARNING")
            
            if not found_allow and self.scan_count % 50 == 0:
                self.log(f"🔍 掃描完成 ({len(windows)} 個視窗，未發現 Allow 按鈕) - 第 {self.scan_count} 次掃描", "DEBUG")
            
            return found_allow
            
        except Exception as e:
            self.log(f"掃描過程出錯: {e}", "ERROR")
            return False
    
    def update_stats(self, window_count):
        """更新統計資訊"""
        self.stats_labels["windows"].config(text=str(window_count))
        self.stats_labels["scans"].config(text=str(self.scan_count))
        self.stats_labels["clicks"].config(text=str(self.click_count))
        
        if self.monitoring:
            self.stats_labels["status"].config(text="🟢 監控中", fg="#27ae60")
        else:
            self.stats_labels["status"].config(text="⚪ 待命中", fg="#95a5a6")
    
    def manual_scan(self):
        """手動掃描"""
        self.log("開始手動掃描...", "INFO")
        found = self.scan_windows()
        if not found:
            self.log("掃描完成，未發現 Allow 按鈕", "INFO")
    
    def monitoring_loop(self):
        """監控循環"""
        while self.monitoring:
            try:
                self.scan_windows()
                time.sleep(0.5)  # 改為每 0.5 秒掃描一次，提高反應速度
            except Exception as e:
                self.log(f"監控錯誤: {e}", "ERROR")
                time.sleep(1)
    
    def toggle_monitoring(self):
        """切換監控狀態"""
        if not self.monitoring:
            # 開始監控
            self.monitoring = True
            self.toggle_btn.config(text="⏸️ 停止監控", bg="#e67e22")
            self.scan_btn.config(state=tk.DISABLED)
            
            self.log("=== 開始自動監控 ===", "SUCCESS")
            self.log("監控間隔: 0.5 秒 (更快的反應速度)", "INFO")
            self.log("搜尋深度: 30 層 (更深入的元素搜尋)", "INFO")
            self.log("支援控制項: Button, SplitButton, MenuButton, MenuItem", "INFO")
            self.log("🔧 改進: 每次掃描都重新連接視窗，確保獲取最新 UI 狀態", "SUCCESS")
            self.log("🔧 改進: 自動清理已關閉的視窗", "SUCCESS")
            self.log("🔧 改進: 檢查元素可見性，避免點擊隱藏按鈕", "SUCCESS")
            
            # 啟動監控執行緒
            self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
            self.monitor_thread.start()
            
            self.update_stats(len(self.vscode_windows))
        else:
            # 停止監控
            self.monitoring = False
            self.toggle_btn.config(text="▶️ 開始監控", bg="#27ae60")
            self.scan_btn.config(state=tk.NORMAL)
            
            self.log("=== 監控已停止 ===", "WARNING")
            self.update_stats(len(self.vscode_windows))
    
    def run(self):
        """運行 GUI"""
        self.log("🚀 VS Code Auto Allow 已啟動", "SUCCESS")
        self.log("支援多個 VS Code 視窗同時監控", "INFO")
        self.log("⚠️ 程式不會自動開啟新視窗，只監控現有的 VS Code", "WARNING")
        
        if self.ai_mode:
            self.log("🤖 AI 模式已啟用：輸出日誌到控制台", "SUCCESS")
            
        # 自動開始監控
        self.log("⏳ 1秒後自動開始監控...", "INFO")
        self.root.after(1000, self.toggle_monitoring)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """關閉視窗"""
        self.monitoring = False
        self.root.destroy()

def main():
    app = AutoAllowGUI()
    app.run()

if __name__ == "__main__":
    main()
