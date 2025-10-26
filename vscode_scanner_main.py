"""
VS Code UI 物件掃描工具 - 主動掃描版本
直接掃描已開啟的 VS Code 視窗中的所有 UI 物件
"""

import win32gui
import win32process
import psutil
from pywinauto import Desktop
import tkinter as tk
from tkinter import scrolledtext
import json
from datetime import datetime
from collections import defaultdict


class VSCodeScannerActive:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VS Code 主動掃描工具")
        self.root.geometry("1600x900")
        
        # 標題
        header = tk.Frame(self.root, bg="#1a1a2e", height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="🔥 VS Code UI 物件主動掃描工具",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg="#00ff00",
            bg="#1a1a2e"
        ).pack(pady=15)
        
        # 控制面板
        control = tk.Frame(self.root, bg="#2a2a3e")
        control.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            control,
            text="🚀 掃描所有視窗",
            command=self.scan_all,
            font=("Arial", 11, "bold"),
            bg="#ff6600",
            fg="white",
            padx=20,
            pady=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            control,
            text="💾 導出",
            command=self.export,
            font=("Arial", 11, "bold"),
            bg="#9b59b6",
            fg="white",
            padx=20,
            pady=10
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            control,
            text="🗑️ 清空",
            command=self.clear,
            font=("Arial", 11, "bold"),
            bg="#e74c3c",
            fg="white",
            padx=20,
            pady=10
        ).pack(side=tk.LEFT, padx=5)
        
        # 結果顯示
        self.text = scrolledtext.ScrolledText(
            self.root,
            font=("Consolas", 10),
            wrap=tk.WORD,
            bg="#1a1a2e",
            fg="#00ff00"
        )
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.all_data = []
        
        self.log("✅ 掃描工具已啟動")
        self.log("📌 點擊「掃描所有視窗」開始")
        self.log("")
    
    def log(self, msg):
        self.text.insert(tk.END, f"{msg}\n")
        self.text.see(tk.END)
        self.root.update()
    
    def clear(self):
        self.text.delete(1.0, tk.END)
        self.all_data = []
    
    def get_vscode_windows(self):
        """找到所有 VS Code 視窗"""
        windows = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid).name().lower().replace(".exe", "")
                    if proc == "code" and title.strip():
                        windows.append((hwnd, title))
                except:
                    pass
            return True
        win32gui.EnumWindows(cb, None)
        return windows
    
    def get_element_info(self, elem):
        """獲取元素資訊"""
        try:
            info = elem.element_info
            data = {
                "type": getattr(info, 'control_type', ''),
                "name": getattr(info, 'name', ''),
                "id": getattr(info, 'automation_id', ''),
                "class": getattr(info, 'class_name', ''),
            }
            
            try:
                data["enabled"] = elem.is_enabled()
            except:
                pass
            
            try:
                data["visible"] = elem.is_visible()
            except:
                pass
            
            try:
                rect = elem.rectangle()
                data["pos"] = f"({rect.left},{rect.top})"
                data["size"] = f"{rect.width()}x{rect.height()}"
            except:
                pass
            
            return data
        except:
            return None
    
    def scan_recursive(self, elem, depth=0, max_depth=15):
        """遞迴掃描"""
        if depth > max_depth:
            return []
        
        results = []
        try:
            data = self.get_element_info(elem)
            if data:
                data["depth"] = depth
                results.append(data)
            
            try:
                for child in elem.children():
                    results.extend(self.scan_recursive(child, depth + 1, max_depth))
            except:
                pass
        except:
            pass
        
        return results
    
    def scan_all(self):
        """掃描所有視窗"""
        self.clear()
        self.log("="*150)
        self.log(f"🚀 開始掃描 - {datetime.now().strftime('%H:%M:%S')}")
        self.log("="*150)
        self.log("")
        
        windows = self.get_vscode_windows()
        self.log(f"找到 {len(windows)} 個 VS Code 視窗\n")
        
        total_elements = 0
        
        for idx, (hwnd, title) in enumerate(windows, 1):
            self.log(f"\n【視窗 {idx}】{title}")
            self.log(f"HWND: {hwnd}")
            self.log("-" * 150)
            
            try:
                window = Desktop(backend="uia").window(handle=hwnd)
                
                # 掃描所有元素
                elements = self.scan_recursive(window, 0)
                self.log(f"✅ 找到 {len(elements)} 個元素\n")
                
                total_elements += len(elements)
                
                # 按類型統計
                types = defaultdict(int)
                for e in elements:
                    types[e.get('type', 'Unknown')] += 1
                
                self.log("【類型統計】")
                for t, count in sorted(types.items(), key=lambda x: x[1], reverse=True)[:20]:
                    bar = "█" * min(count // 5, 40)
                    self.log(f"  {t:30s}: {count:5d} {bar}")
                
                # 顯示【所有元素】的詳細資訊
                self.log(f"\n【所有元素詳細列表】 ({len(elements)} 個)")
                self.log("")
                
                for idx, e in enumerate(elements, 1):
                    indent = "  " * e['depth']
                    enabled = "✓啟用" if e.get('enabled') else "✗停用" if e.get('enabled') is False else "?未知"
                    visible = "👁可見" if e.get('visible') else "🔒隱藏" if e.get('visible') is False else "?未知"
                    
                    self.log(f"{idx:3d}. {indent}【深度 {e['depth']}】")
                    self.log(f"     {indent}類型: {e.get('type', 'Unknown')}")
                    
                    if e.get('name'):
                        self.log(f"     {indent}名稱: {e['name']}")
                    
                    if e.get('id'):
                        self.log(f"     {indent}AutoID: {e['id']}")
                    
                    if e.get('class'):
                        self.log(f"     {indent}類別: {e['class']}")
                    
                    self.log(f"     {indent}狀態: {enabled}, {visible}")
                    
                    if e.get('pos'):
                        self.log(f"     {indent}位置: {e['pos']}")
                    
                    if e.get('size'):
                        self.log(f"     {indent}大小: {e['size']}")
                    
                    self.log("")
                
                # 儲存資料
                self.all_data.append({
                    "hwnd": hwnd,
                    "title": title,
                    "elements": elements
                })
                
            except Exception as e:
                self.log(f"❌ 錯誤: {e}")
        
        self.log("")
        self.log("="*150)
        self.log(f"✅ 掃描完成！共 {total_elements} 個元素")
        self.log("="*150)
    
    def export(self):
        """導出 JSON"""
        if not self.all_data:
            self.log("⚠️ 先執行掃描")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"c:\\Aking\\AutoAllow\\python\\vscode_scan_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.all_data, f, ensure_ascii=False, indent=2)
            self.log(f"\n✅ 已導出到: {filename}")
        except Exception as e:
            self.log(f"❌ 導出失敗: {e}")
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = VSCodeScannerActive()
    app.run()
