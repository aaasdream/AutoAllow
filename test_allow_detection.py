"""
Allow 按钮检测诊断工具
直接测试能否找到 Allow 按钮
"""

import win32gui
import win32process
import psutil
from pywinauto import Desktop
from datetime import datetime

def get_vscode_windows():
    """找到所有 VS Code 视窗"""
    windows = []
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid).name().lower().replace(".exe", "")
                if proc == "code" and title.strip() and "Extension Development Host" not in title:
                    windows.append((hwnd, title))
            except:
                pass
        return True
    win32gui.EnumWindows(cb, None)
    return windows

def test_window_connection(hwnd, title):
    """测试窗口连接"""
    print(f"\n{'='*100}")
    print(f"测试窗口: {title}")
    print(f"HWND: {hwnd}")
    print(f"{'='*100}")
    
    # 测试窗口是否存在
    if not win32gui.IsWindow(hwnd):
        print("❌ 窗口不存在")
        return False
    
    print("✅ 窗口存在")
    
    # 测试 UI Automation 连接
    try:
        desktop = Desktop(backend="uia")
        window = desktop.window(handle=hwnd)
        print("✅ 成功连接到窗口")
    except Exception as e:
        print(f"❌ 无法连接到窗口: {e}")
        return False
    
    # 搜索所有按钮类型
    button_types = ["Button", "SplitButton", "MenuButton", "MenuItem"]
    
    print(f"\n开始搜索按钮...")
    all_buttons = []
    
    for btn_type in button_types:
        try:
            print(f"  搜索 {btn_type}...", end="")
            buttons = window.descendants(control_type=btn_type, depth=30)
            count = len(buttons)
            print(f" 找到 {count} 个")
            all_buttons.extend([(btn, btn_type) for btn in buttons])
        except Exception as e:
            print(f" 失败: {e}")
    
    print(f"\n总共找到 {len(all_buttons)} 个按钮")
    
    # 查找 Allow 按钮
    print(f"\n{'='*100}")
    print("开始查找 Allow 相关按钮...")
    print(f"{'='*100}\n")
    
    allow_keywords = ['allow', '允許', 'accept', 'confirm']
    exclude_keywords = ['section', 'explorer', 'autoallow', 'folder', 'directory']
    
    found_allow = False
    
    for idx, (button, btn_type) in enumerate(all_buttons, 1):
        try:
            element_info = button.element_info
            name = getattr(element_info, 'name', '').lower()
            
            # 检查是否包含 allow 关键字
            has_allow = any(keyword in name for keyword in allow_keywords)
            should_exclude = any(ex in name for ex in exclude_keywords)
            
            if has_allow or 'allow' in name:
                button_name = getattr(element_info, 'name', '')
                
                # 获取更多信息
                try:
                    is_enabled = button.is_enabled()
                except:
                    is_enabled = "Unknown"
                
                try:
                    is_visible = button.is_visible()
                except:
                    is_visible = "Unknown"
                
                try:
                    automation_id = getattr(element_info, 'automation_id', '')
                except:
                    automation_id = ""
                
                try:
                    class_name = getattr(element_info, 'class_name', '')
                except:
                    class_name = ""
                
                print(f"{'🎯' if not should_exclude else '⚠️'} 找到按钮 #{idx}:")
                print(f"   名称: {button_name}")
                print(f"   类型: {btn_type}")
                print(f"   可用: {is_enabled}")
                print(f"   可见: {is_visible}")
                if automation_id:
                    print(f"   AutoID: {automation_id}")
                if class_name:
                    print(f"   Class: {class_name}")
                
                if should_exclude:
                    print(f"   ❌ 被排除（匹配排除关键字）")
                else:
                    print(f"   ✅ 符合条件！")
                    found_allow = True
                    
                    # 尝试点击
                    print(f"\n   尝试点击...")
                    click_success = False
                    
                    methods = [
                        ('invoke', lambda: button.invoke()),
                        ('click_input', lambda: button.click_input()),
                        ('click', lambda: button.click())
                    ]
                    
                    for method_name, method_func in methods:
                        try:
                            print(f"      尝试 {method_name}()...", end="")
                            method_func()
                            print(f" ✅ 成功！")
                            click_success = True
                            break
                        except Exception as e:
                            print(f" ❌ 失败: {e}")
                    
                    if not click_success:
                        print(f"      ❌ 所有点击方法都失败")
                
                print()
        
        except Exception as e:
            continue
    
    if not found_allow:
        print("❌ 未找到符合条件的 Allow 按钮")
        print("\n显示所有按钮名称供参考：")
        print("-" * 100)
        for idx, (button, btn_type) in enumerate(all_buttons[:50], 1):  # 只显示前50个
            try:
                element_info = button.element_info
                name = getattr(element_info, 'name', '')
                if name:
                    print(f"{idx:3d}. [{btn_type:15s}] {name}")
            except:
                pass
        
        if len(all_buttons) > 50:
            print(f"\n... 还有 {len(all_buttons) - 50} 个按钮未显示")
    
    return found_allow

def main():
    print("="*100)
    print("Allow 按钮检测诊断工具")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    windows = get_vscode_windows()
    print(f"\n找到 {len(windows)} 个 VS Code 窗口\n")
    
    if not windows:
        print("❌ 没有找到任何 VS Code 窗口")
        return
    
    total_found = 0
    
    for hwnd, title in windows:
        if test_window_connection(hwnd, title):
            total_found += 1
    
    print("\n" + "="*100)
    print(f"诊断完成！在 {len(windows)} 个窗口中找到 {total_found} 个 Allow 按钮")
    print("="*100)
    
    input("\n按 Enter 键退出...")

if __name__ == "__main__":
    main()
