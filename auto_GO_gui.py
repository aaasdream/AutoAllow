"""
VS Code / Antigravity Auto Allow - GUI 版本
支援多個 VS Code 或 Antigravity 視窗的自動 Allow 點擊
智慧掃描：優先掃描活躍視窗，減少資源消耗
"""

import win32gui
import win32process
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
        parser = argparse.ArgumentParser(description='VS Code / Antigravity Auto Allow')
        parser.add_argument('--ai-mode', action='store_true', help='啟用 AI 模式 (自動開始 + 控制台輸出)')
        args, _ = parser.parse_known_args()
        self.ai_mode = args.ai_mode
        
        # 🔧 記錄連接失敗的視窗，避免頻繁重試
        self.failed_connections = {}  # {hwnd: (fail_count, last_fail_time)}
        self.max_connection_failures = 5
        
        # 🆕 智慧掃描：記錄活躍視窗（曾找到 Allow 按鈕的視窗）
        self.active_windows = set()  # 曾經找到過 Allow 按鈕的視窗 hwnd
        self.last_full_scan_time = None  # 上次全掃描時間
        self.full_scan_interval = 3  # 全掃描間隔（秒）
        self.known_hwnds = set()  # 已知的所有視窗 hwnd
        
        # 🆕 掃描深度設定
        self.deep_scan_depth = 50  # 活躍視窗深度掃描
        self.shallow_scan_depth = 20  # 新視窗淺層掃描
        
        # 創建 GUI
        self.root = tk.Tk()
        self.root.title("VS Code / Antigravity Auto Allow - 智慧掃描")
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
            text="🤖 VS Code / Antigravity Auto Allow (智慧掃描版)",
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
            command=self.reset_all_states,
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
        
        # 統計標籤 - 新增活躍視窗計數
        self.stats_labels = {}
        
        stats_data = [
            ("windows", "監控視窗", "0"),
            ("active", "活躍視窗", "0"),
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
            text="📋 監控中的視窗 (VS Code / Antigravity) (🔥=活躍視窗，優先深度掃描)",
            font=("Microsoft YaHei UI", 11, "bold"),
            anchor=tk.W
        ).pack(fill=tk.X, pady=(0, 5))
        
        # Treeview - 新增掃描模式欄位
        columns = ("HWND", "標題", "掃描模式", "最後掃描", "狀態")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=8)
        
        self.tree.heading("#0", text="序號")
        self.tree.heading("HWND", text="視窗 ID")
        self.tree.heading("標題", text="視窗標題")
        self.tree.heading("掃描模式", text="掃描模式")
        self.tree.heading("最後掃描", text="最後掃描時間")
        self.tree.heading("狀態", text="狀態")
        
        self.tree.column("#0", width=60, anchor=tk.CENTER)
        self.tree.column("HWND", width=80, anchor=tk.CENTER)
        self.tree.column("標題", width=350)
        self.tree.column("掃描模式", width=120, anchor=tk.CENTER)
        self.tree.column("最後掃描", width=120, anchor=tk.CENTER)
        self.tree.column("狀態", width=180, anchor=tk.CENTER)
        
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
        """添加日誌 (線程安全)"""
        def _log_internal():
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            colors = {
                "INFO": "#3498db",
                "SUCCESS": "#27ae60",
                "WARNING": "#f39c12",
                "ERROR": "#e74c3c",
                "DEBUG": "#95a5a6"
            }
            
            # 自動清理：保留最近 1000 行日誌
            line_count = int(self.log_text.index('end-1c').split('.')[0])
            if line_count > 1000:
                self.log_text.delete('1.0', f'{line_count - 800}.0')
            
            self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.log_text.insert(tk.END, f"[{level}] ", level)
            self.log_text.insert(tk.END, f"{message}\n")
            
            # 配置標籤顏色
            self.log_text.tag_config("timestamp", foreground="#95a5a6")
            self.log_text.tag_config(level, foreground=colors.get(level, "#ecf0f1"))
            
            # 自動滾動到底部
            self.log_text.see(tk.END)
        
        # 確保在主線程執行 GUI 操作
        if threading.current_thread() is threading.main_thread():
            _log_internal()
        else:
            self.root.after(0, _log_internal)
        
        # 如果是 AI 模式，同時輸出到控制台
        if self.ai_mode:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")
    
    def clear_log(self):
        """清空日誌"""
        self.log_text.delete(1.0, tk.END)
        self.log("日誌已清空", "INFO")
    
    def reset_all_states(self):
        """重置所有狀態（包括活躍視窗和失敗連接）"""
        fail_count = len(self.failed_connections)
        active_count = len(self.active_windows)
        
        self.failed_connections.clear()
        self.active_windows.clear()
        self.known_hwnds.clear()
        self.last_full_scan_time = None
        
        self.log(f"🔄 已重置所有狀態：{fail_count} 個失敗連接、{active_count} 個活躍視窗", "SUCCESS")
        self.log("💡 下次掃描將對所有視窗進行全掃描", "INFO")
    
    def reset_failed_connections(self):
        """重置失敗連接記錄"""
        count = len(self.failed_connections)
        self.failed_connections.clear()
        self.log(f"🔄 已重置 {count} 個失敗連接記錄", "SUCCESS")
    
    def get_process_name_from_hwnd(self, hwnd):
        """獲取進程名稱"""
        if hwnd == 0:
            return ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name().lower().replace(".exe", "")
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            return ""
    
    def find_all_vscode_windows(self):
        """尋找所有 VS Code 視窗"""
        windows = []
        
        def enum_callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                process_name = self.get_process_name_from_hwnd(hwnd)
                
                # 排除 Extension Development Host
                if "Extension Development Host" in title:
                    return True
                
                # 排除空標題
                if not title or len(title.strip()) == 0:
                    return True
                
                # 支援 VS Code 和 Antigravity
                is_vscode = process_name == "code" and "Visual Studio Code" in title
                is_antigravity = "antigravity" in process_name or "Antigravity" in title
                
                if is_vscode or is_antigravity:
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "process": process_name
                    })
            return True
        
        win32gui.EnumWindows(enum_callback, None)
        return windows
    
    def find_and_click_allow_button(self, hwnd, deep_scan=False):
        """在指定視窗中尋找並點擊 Allow 按鈕
        
        Args:
            hwnd: 視窗句柄
            deep_scan: 是否進行深度掃描（活躍視窗使用）
        """
        try:
            # 檢查視窗是否存在
            if not win32gui.IsWindow(hwnd):
                if hwnd in self.vscode_windows:
                    self.log(f"⚠️ 視窗 {hwnd} 已不存在", "WARNING")
                # 從活躍視窗中移除
                self.active_windows.discard(hwnd)
                return False
            
            # 檢查是否應該跳過此視窗（連接失敗太多次）
            if hwnd in self.failed_connections:
                fail_count, last_fail_time = self.failed_connections[hwnd]
                if fail_count >= self.max_connection_failures:
                    if (datetime.now() - last_fail_time).total_seconds() < 15:
                        return False
                    else:
                        self.failed_connections[hwnd] = (0, datetime.now())
                        self.log(f"🔄 視窗 {hwnd} 重新嘗試連接", "INFO")
            
            # 連接到視窗
            try:
                desktop = Desktop(backend="uia")
                window = desktop.window(handle=hwnd)
                if hwnd in self.failed_connections:
                    del self.failed_connections[hwnd]
            except Exception as e:
                if hwnd in self.failed_connections:
                    fail_count, _ = self.failed_connections[hwnd]
                    self.failed_connections[hwnd] = (fail_count + 1, datetime.now())
                else:
                    self.failed_connections[hwnd] = (1, datetime.now())
                
                if self.scan_count % 50 == 0:
                    self.log(f"⚠️ 無法連接到視窗 {hwnd}: {e}", "DEBUG")
                return False
            
            # 🆕 根據掃描模式決定深度
            scan_depth = self.deep_scan_depth if deep_scan else self.shallow_scan_depth
            
            # 🔧 修改：只搜尋真正的按鈕類型，不搜尋 Text 和 Hyperlink
            # 這些類型最容易造成誤點擊
            button_types = [
                "Button",       # 主要目標
                "SplitButton",  # 分割按鈕
            ]
            
            for btn_type in button_types:
                try:
                    type_depth = scan_depth
                    buttons = window.descendants(control_type=btn_type, depth=type_depth)
                    
                    for button in buttons:
                        try:
                            try:
                                button.element_info.update()
                            except:
                                pass
                            
                            element_info = button.element_info
                            name = getattr(element_info, 'name', '')
                            name_lower = name.lower()
                            
                            # 🔧 加強排除邏輯
                            # 排除關鍵字（更全面）
                            exclude_keywords = [
                                # 檔案/資料夾相關
                                'section', 'explorer', 'folder', 'directory', 'file',
                                # 否定詞
                                'disallow', '不允許', 'deny', 'reject', 'cancel',
                                # 程式相關
                                'autoallow', 'auto_allow', 'auto-allow',
                                # 對話/聊天區域（避免點到聊天內容）
                                'chat', 'message', 'conversation', 'response',
                                # 編輯器相關
                                'editor', 'tab', 'panel', 'view', 'tree',
                                # 其他 UI 元素
                                'menu', 'toolbar', 'statusbar', 'sidebar',
                                # 長文字（通常是內容而非按鈕）
                            ]
                            
                            # 檢查是否應該排除
                            should_exclude = any(ex in name_lower for ex in exclude_keywords)
                            if should_exclude:
                                continue
                            
                            # 🔧 更嚴格的匹配：按鈕名稱必須簡短且精確
                            # Allow 按鈕通常很短，例如 "Allow", "允許", "Accept"
                            if len(name) > 50:  # 按鈕名稱太長，可能是內容而非按鈕
                                continue
                            
                            # 🔧 精確匹配 Allow 相關關鍵字
                            # 必須是按鈕的主要文字，而非包含在長句中
                            allow_patterns = [
                                'allow',    # 英文
                                '允許',     # 中文
                                'accept',   # 接受 (Antigravity)
                                '接受',
                                'confirm',  # 確認
                                '確認',
                                'yes',      # 是
                                '是',
                                'ok',       # OK
                                '確定',
                            ]
                            
                            # 檢查是否匹配（更嚴格）
                            is_allow_button = False
                            matched_pattern = None
                            
                            for pattern in allow_patterns:
                                # 精確匹配：名稱就是這個詞，或者以這個詞開頭/結尾
                                if name_lower == pattern:
                                    is_allow_button = True
                                    matched_pattern = pattern
                                    break
                                # 或者名稱中包含這個詞，但名稱很短（<20字元）
                                elif pattern in name_lower and len(name) < 20:
                                    is_allow_button = True
                                    matched_pattern = pattern
                                    break
                            
                            if not is_allow_button:
                                continue
                            
                            # 🔧 額外檢查：確保是真正的按鈕
                            try:
                                # 檢查按鈕是否可用
                                is_enabled = button.is_enabled()
                                if not is_enabled:
                                    continue
                            except:
                                pass
                            
                            try:
                                # 檢查按鈕是否可見
                                is_visible = button.is_visible()
                                if not is_visible:
                                    continue  # 跳過不可見的按鈕
                            except:
                                pass
                            
                            # 🔧 檢查按鈕的 automation_id 或 class_name
                            # VS Code 的真正按鈕通常有特定的 class
                            try:
                                class_name = getattr(element_info, 'class_name', '')
                                automation_id = getattr(element_info, 'automation_id', '')
                                
                                # 如果有 automation_id 包含可疑詞，跳過
                                suspicious_ids = ['editor', 'chat', 'message', 'text', 'content']
                                if any(s in automation_id.lower() for s in suspicious_ids):
                                    self.log(f"⏭️ 跳過可疑元素: '{name}' (automation_id: {automation_id})", "DEBUG")
                                    continue
                            except:
                                pass
                            
                            # 🔧 檢查按鈕的位置和大小（真正的按鈕通常有合理的大小）
                            try:
                                rect = button.rectangle()
                                width = rect.right - rect.left
                                height = rect.bottom - rect.top
                                
                                # 按鈕太小或太大都可能不是真正的按鈕
                                if width < 20 or height < 15:
                                    continue
                                if width > 500 or height > 100:
                                    continue
                            except:
                                pass
                            
                            # 通過所有檢查，準備點擊
                            scan_mode = "深度" if deep_scan else "淺層"
                            self.log(f"🎯 [{scan_mode}掃描] 找到 Allow 按鈕: '{name}' (類型: {btn_type}, 匹配: {matched_pattern}, HWND: {hwnd})", "SUCCESS")
                            
                            click_methods = ['invoke', 'click_input', 'click']
                            
                            for method_name in click_methods:
                                try:
                                    method = getattr(button, method_name, None)
                                    if method:
                                        method()
                                        self.click_count += 1
                                        self.log(f"✅ 使用 {method_name}() 成功點擊！(第 {self.click_count} 次)", "SUCCESS")
                                        
                                        # 🆕 標記此視窗為活躍視窗
                                        if hwnd not in self.active_windows:
                                            self.active_windows.add(hwnd)
                                            self.log(f"🔥 視窗 {hwnd} 已標記為活躍視窗，後續將優先深度掃描", "SUCCESS")
                                        
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
    
    def scan_windows(self):
        """智慧掃描所有視窗"""
        try:
            self.scan_count += 1
            current_time = datetime.now()
            
            # 🆕 判斷是否需要進行全掃描（發現新視窗）
            windows = self.find_all_vscode_windows()
            current_hwnds = {win['hwnd'] for win in windows}
            
            # 檢查是否有新視窗
            new_windows = current_hwnds - self.known_hwnds
            has_new_windows = len(new_windows) > 0
            
            # 檢查是否需要定期全掃描
            need_periodic_full_scan = (
                self.last_full_scan_time is None or 
                (current_time - self.last_full_scan_time).total_seconds() >= self.full_scan_interval
            )
            
            # 清理已關閉的視窗
            closed_hwnds = self.known_hwnds - current_hwnds
            for hwnd in closed_hwnds:
                if hwnd in self.vscode_windows:
                    del self.vscode_windows[hwnd]
                if hwnd in self.failed_connections:
                    del self.failed_connections[hwnd]
                self.active_windows.discard(hwnd)
            
            # 更新已知視窗列表
            self.known_hwnds = current_hwnds
            
            # 更新 Treeview
            def _update_tree():
                for item in self.tree.get_children():
                    self.tree.delete(item)
            
            if threading.current_thread() is threading.main_thread():
                _update_tree()
            else:
                self.root.after(0, _update_tree)
            
            found_allow = False
            skipped_windows = 0
            
            # 🆕 決定掃描策略
            if has_new_windows:
                self.log(f"🆕 發現 {len(new_windows)} 個新視窗，進行全掃描", "INFO")
                self.last_full_scan_time = current_time
            
            # 🆕 優先掃描活躍視窗（深度掃描）
            active_hwnds_to_scan = self.active_windows & current_hwnds
            other_hwnds_to_scan = current_hwnds - self.active_windows
            
            # 按照優先順序排列視窗：活躍視窗在前
            sorted_windows = []
            for win in windows:
                if win['hwnd'] in active_hwnds_to_scan:
                    sorted_windows.insert(0, win)  # 活躍視窗放前面
                else:
                    sorted_windows.append(win)
            
            for i, win in enumerate(sorted_windows, 1):
                hwnd = win['hwnd']
                title = win['title']
                
                display_title = title
                if len(display_title) > 50:
                    display_title = display_title[:47] + "..."
                
                # 檢查是否應該跳過
                should_skip = False
                skip_reason = ""
                if hwnd in self.failed_connections:
                    fail_count, last_fail_time = self.failed_connections[hwnd]
                    if fail_count >= self.max_connection_failures:
                        time_since_fail = (current_time - last_fail_time).total_seconds()
                        if time_since_fail < 15:
                            should_skip = True
                            skipped_windows += 1
                            skip_reason = f"等待 {15 - int(time_since_fail)}s"
                
                # 🆕 決定掃描模式
                is_active = hwnd in self.active_windows
                is_new = hwnd in new_windows
                
                # 活躍視窗：每次都深度掃描
                # 新視窗：淺層掃描
                # 其他視窗：只在定期全掃描時淺層掃描
                if should_skip:
                    has_allow = False
                    status = f"⏭️ 跳過 ({skip_reason})"
                    scan_mode = "跳過"
                    tag = "skipped"
                elif is_active:
                    # 活躍視窗：深度掃描
                    has_allow = self.find_and_click_allow_button(hwnd, deep_scan=True)
                    scan_mode = "🔥 深度"
                    if has_allow:
                        found_allow = True
                        status = "✅ 已點擊 Allow"
                        tag = "clicked"
                    else:
                        status = "⏳ 監控中"
                        tag = "active"
                elif is_new or need_periodic_full_scan:
                    # 新視窗或定期全掃描：淺層掃描
                    has_allow = self.find_and_click_allow_button(hwnd, deep_scan=False)
                    scan_mode = "🔍 淺層"
                    if has_allow:
                        found_allow = True
                        status = "✅ 已點擊 Allow"
                        tag = "clicked"
                    else:
                        status = "⏳ 無 Allow"
                        tag = "normal"
                else:
                    # 非活躍視窗且非全掃描週期：跳過
                    has_allow = False
                    scan_mode = "⏸️ 待命"
                    status = "⏸️ 等待全掃描"
                    tag = "waiting"
                
                # 更新視窗資訊
                self.vscode_windows[hwnd] = {
                    "title": title,
                    "last_scan": current_time,
                    "has_allow": has_allow,
                    "is_active": is_active
                }
                
                time_str = current_time.strftime("%H:%M:%S")
                
                # Treeview 插入
                def _insert_item(idx=i, h=hwnd, dt=display_title, sm=scan_mode, ts=time_str, st=status, tg=tag):
                    self.tree.insert(
                        "",
                        tk.END,
                        text=str(idx),
                        values=(h, dt, sm, ts, st),
                        tags=(tg,)
                    )
                
                if threading.current_thread() is threading.main_thread():
                    _insert_item()
                else:
                    self.root.after(0, _insert_item)
            
            # 如果進行了全掃描，更新時間
            if need_periodic_full_scan and not has_new_windows:
                self.last_full_scan_time = current_time
            
            # 配置標籤顏色
            def _configure_tags():
                self.tree.tag_configure("clicked", background="#d5f4e6")
                self.tree.tag_configure("active", background="#fff3cd")  # 活躍視窗黃色
                self.tree.tag_configure("normal", background="#ffffff")
                self.tree.tag_configure("skipped", background="#f8d7da")
                self.tree.tag_configure("waiting", background="#e2e3e5")
            
            if threading.current_thread() is threading.main_thread():
                _configure_tags()
            else:
                self.root.after(0, _configure_tags)
            
            # 更新統計
            self.update_stats(len(windows))
            
            # 日誌輸出（減少頻率）
            if skipped_windows > 0 and self.scan_count % 30 == 0:
                self.log(f"⚠️ 有 {skipped_windows} 個視窗暫時跳過", "WARNING")
            
            if self.scan_count % 100 == 0:
                active_count = len(self.active_windows & current_hwnds)
                self.log(f"📊 掃描統計：{len(windows)} 視窗，{active_count} 活躍，第 {self.scan_count} 次掃描", "DEBUG")
            
            return found_allow
            
        except Exception as e:
            self.log(f"掃描過程出錯: {e}", "ERROR")
            return False
    
    def update_stats(self, window_count):
        """更新統計資訊 (線程安全)"""
        def _update():
            self.stats_labels["windows"].config(text=str(window_count))
            self.stats_labels["active"].config(text=str(len(self.active_windows)))
            self.stats_labels["scans"].config(text=str(self.scan_count))
            self.stats_labels["clicks"].config(text=str(self.click_count))
            
            if self.monitoring:
                self.stats_labels["status"].config(text="🟢 監控中", fg="#27ae60")
            else:
                self.stats_labels["status"].config(text="⚪ 待命中", fg="#95a5a6")
        
        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            self.root.after(0, _update)
    
    def manual_scan(self):
        """手動掃描（強制全掃描）"""
        self.log("開始手動全掃描...", "INFO")
        self.last_full_scan_time = None  # 強制下次全掃描
        found = self.scan_windows()
        if not found:
            self.log("掃描完成，未發現 Allow 按鈕", "INFO")
    
    def monitoring_loop(self):
        """監控循環"""
        while self.monitoring:
            try:
                self.scan_windows()
                # 🆕 智慧休眠：如果有活躍視窗，掃描更頻繁
                if self.active_windows:
                    time.sleep(0.3)  # 有活躍視窗時，0.3 秒掃描一次
                else:
                    time.sleep(0.8)  # 無活躍視窗時，0.8 秒掃描一次
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
            
            self.log("=== 開始智慧監控 ===", "SUCCESS")
            self.log(f"🔥 活躍視窗深度掃描: {self.deep_scan_depth} 層", "INFO")
            self.log(f"🔍 新視窗淺層掃描: {self.shallow_scan_depth} 層", "INFO")
            self.log(f"⏱️ 全掃描間隔: {self.full_scan_interval} 秒", "INFO")
            self.log("💡 提示：找到 Allow 按鈕的視窗會被標記為活躍視窗", "INFO")
            self.log("💡 活躍視窗會優先進行深度掃描，節省資源", "INFO")
            
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
        self.log("🚀 VS Code / Antigravity Auto Allow (智慧掃描版) 已啟動", "SUCCESS")
        self.log("✨ 新功能：智慧分層掃描，優先掃描活躍視窗", "INFO")
        self.log("⚠️ 程式不會自動開啟新視窗，只監控現有的 VS Code / Antigravity", "WARNING")
        
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
