"""
文件夹选择器 - 用于选择NextCloud中的文件夹
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class FolderSelector:
    """文件夹选择器组件"""
    
    def __init__(self, app, nextcloud_client, initial_path: str = ""):
        self.app = app
        self.nextcloud_client = nextcloud_client
        self.current_path = initial_path
        self.selected_path = initial_path
        self.on_path_selected = None  # 回调函数
        
        # 创建对话框容器
        self.dialog_window = None
        self.create_dialog()
    
    def create_dialog(self):
        """创建文件夹选择对话框"""
        
        # 主容器
        main_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=15,
            background_color="white"
        ))
        
        # 标题
        title = toga.Label(
            "📁 选择同步文件夹",
            style=Pack(
                padding=(0, 0, 15, 0),
                font_size=16,
                font_weight="bold",
                text_align="center",
                color="#212529"
            )
        )
        
        # 当前路径显示
        path_box = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        
        path_label = toga.Label(
            "当前路径:",
            style=Pack(padding=(0, 5, 0, 0), font_size=12, color="#495057")
        )
        
        self.path_display = toga.Label(
            self.current_path or "/",
            style=Pack(
                flex=1,
                padding=(0, 0, 0, 5),
                font_size=12,
                color="#007AFF",
                background_color="#f8f9fa"
            )
        )
        
        path_box.add(path_label)
        path_box.add(self.path_display)
        
        # 导航按钮
        nav_box = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 10, 0)))
        
        self.back_button = toga.Button(
            "⬆️ 返回上级",
            on_press=self.go_back,
            enabled=bool(self.current_path),
            style=Pack(
                padding=3,
                background_color="#6c757d",
                color="white",
                width=80,
                height=30,
                font_size=11
            )
        )
        
        self.root_button = toga.Button(
            "🏠 根目录",
            on_press=self.go_root,
            style=Pack(
                padding=3,
                background_color="#28a745",
                color="white",
                width=80,
                height=30,
                font_size=11
            )
        )
        
        self.refresh_button = toga.Button(
            "🔄 刷新",
            on_press=self.refresh_folders,
            style=Pack(
                padding=3,
                background_color="#17a2b8",
                color="white",
                width=60,
                height=30,
                font_size=11
            )
        )
        
        nav_box.add(self.back_button)
        nav_box.add(self.root_button)
        nav_box.add(self.refresh_button)
        
        # 文件夹列表
        self.folder_list = toga.DetailedList(
            data=[],
            style=Pack(flex=1, height=300),
            on_select=self.on_folder_select
        )
        
        # 加载状态
        self.loading_box = toga.Box(style=Pack(
            direction=ROW,
            padding=10,
            background_color="#f8f9fa"
        ))
        
        self.loading_label = toga.Label(
            "正在加载文件夹...",
            style=Pack(flex=1, text_align="center", color="#6c757d")
        )
        
        self.loading_box.add(self.loading_label)
        
        # 操作按钮
        button_box = toga.Box(style=Pack(direction=ROW, padding=(10, 0, 0, 0)))
        
        self.select_button = toga.Button(
            "✅ 选择当前目录",
            on_press=self.select_current_folder,
            style=Pack(
                padding=5,
                background_color="#007AFF",
                color="white",
                flex=1,
                height=35,
                font_size=12
            )
        )
        
        self.cancel_button = toga.Button(
            "❌ 取消",
            on_press=self.cancel_selection,
            style=Pack(
                padding=5,
                background_color="#dc3545",
                color="white",
                width=80,
                height=35,
                font_size=12
            )
        )
        
        button_box.add(self.select_button)
        button_box.add(self.cancel_button)
        
        # 组装界面
        main_box.add(title)
        main_box.add(path_box)
        main_box.add(nav_box)
        main_box.add(self.folder_list)
        main_box.add(self.loading_box)
        main_box.add(button_box)
        
        # 创建滚动容器
        self.container = toga.ScrollContainer(
            content=main_box,
            style=Pack(width=400, height=500)
        )
        
        # 初始加载文件夹（使用app的后台任务）
        self.app.add_background_task(self.load_folders())
    
    async def load_folders(self):
        """加载当前路径下的文件夹"""
        try:
            self.show_loading(True)
            
            # 获取文件夹列表
            folders = await self.get_folders(self.current_path)
            
            # 清空现有列表
            self.folder_list.data.clear()
            
            # 添加文件夹到列表
            for folder in folders:
                self.folder_list.data.append({
                    'icon': None,  # 修复：移除不存在的 Icon.DEFAULT
                    'title': f"📁 {folder['name']}",
                    'subtitle': folder.get('modified', ''),
                    'data': folder
                })
            
            # 更新路径显示
            self.path_display.text = self.current_path or "/"
            
            # 更新返回按钮状态
            self.back_button.enabled = bool(self.current_path)
            
            self.show_loading(False)
            
            # 显示成功消息
            if folders:
                self.show_message(f"✅ 已加载 {len(folders)} 个文件夹", "success")
            else:
                self.show_message("� 当前目录无子文件夹", "info")
            
        except Exception as e:
            logger.error(f"加载文件夹失败: {e}")
            self.show_loading(False)
            
            # 根据错误类型显示不同的用户友好提示
            error_msg = str(e)
            if "无法连接到NextCloud服务器" in error_msg:
                user_msg = "❌ 无法连接到NextCloud服务器，请检查网络连接和服务器配置"
            elif "服务器响应格式错误" in error_msg:
                user_msg = "❌ 服务器响应异常，请稍后重试"
            elif "无法获取文件夹列表" in error_msg:
                user_msg = "❌ 无法获取文件夹列表，请检查权限设置"
            else:
                user_msg = f"❌ 连接失败: {error_msg}"
            
            self.show_message(user_msg, "error")
            
            # 清空文件夹列表，避免显示过期数据
            self.folder_list.data.clear()
    
    async def get_folders(self, path: str) -> List[Dict]:
        """获取指定路径下的文件夹列表"""
        try:
            if not self.nextcloud_client:
                return []
            
            # 直接调用 nextcloud_client 的 list_directories 方法
            folders = await self.nextcloud_client.list_directories(path)
            return sorted(folders, key=lambda x: x['name'].lower())
            
        except Exception as e:
            logger.error(f"获取文件夹列表失败: {e}")
            return []
    
    def on_folder_select(self, widget):
        """文件夹选择事件"""
        selection = widget.selection
        if selection:
            folder_data = selection.data
            folder_path = folder_data.get('path', '')
            
            # 使用WebDAV响应中的完整路径，如果没有则构建路径
            if folder_path:
                new_path = folder_path
            else:
                folder_name = folder_data['name']
                # 构建新路径
                if self.current_path:
                    new_path = f"{self.current_path.rstrip('/')}/{folder_name}"
                else:
                    new_path = folder_name
            
            # 进入子目录
            self.app.add_background_task(self.enter_folder(new_path))
    
    async def enter_folder(self, folder_path: str):
        """进入指定文件夹"""
        self.current_path = folder_path
        await self.load_folders()
    
    def go_back(self, widget):
        """返回上级目录"""
        if self.current_path:
            parent_path = str(Path(self.current_path).parent)
            if parent_path == '.':
                parent_path = ""
            self.current_path = parent_path
            self.app.add_background_task(self.load_folders())
    
    def go_root(self, widget):
        """返回根目录"""
        self.current_path = ""
        self.app.add_background_task(self.load_folders())
    
    def refresh_folders(self, widget):
        """刷新文件夹列表"""
        # 清除之前的错误消息
        self.loading_label.text = ""
        self.loading_box.style.background_color = "transparent"
        # 重新加载
        self.app.add_background_task(self.load_folders())
    
    def select_current_folder(self, widget):
        """选择当前文件夹"""
        self.selected_path = self.current_path
        
        # 调用回调函数
        if self.on_path_selected:
            self.on_path_selected(self.selected_path)
        
        # 关闭对话框
        self.close_dialog()
    
    def cancel_selection(self, widget):
        """取消选择"""
        self.close_dialog()
    
    def show_loading(self, loading: bool):
        """显示/隐藏加载状态"""
        if loading:
            self.loading_label.text = "正在加载文件夹..."
            self.loading_box.style.background_color = "#f8f9fa"
            self.loading_label.style.color = "#6c757d"
            # 加载时禁用操作按钮
            self.select_button.enabled = False
            self.refresh_button.enabled = False
        else:
            self.loading_label.text = ""
            self.loading_box.style.background_color = "transparent"
            # 加载完成时重新启用按钮
            self.select_button.enabled = True
            self.refresh_button.enabled = True
    
    def show_message(self, message: str, msg_type: str = "info"):
        """显示消息"""
        self.loading_label.text = message
        
        if msg_type == "error":
            self.loading_box.style.background_color = "#f8d7da"
            self.loading_label.style.color = "#721c24"
            # 对于错误消息，禁用一些按钮直到用户手动刷新
            self.select_button.enabled = False
        elif msg_type == "success":
            self.loading_box.style.background_color = "#d4edda"
            self.loading_label.style.color = "#155724"
            self.select_button.enabled = True
        else:
            self.loading_box.style.background_color = "#d1ecf1"
            self.loading_label.style.color = "#0c5460"
            self.select_button.enabled = True
    
    def close_dialog(self):
        """关闭对话框"""
        if self.dialog_window:
            self.dialog_window.close()
    
    def show_dialog(self, on_path_selected_callback=None):
        """显示文件夹选择对话框"""
        self.on_path_selected = on_path_selected_callback
        
        # 创建模态窗口（在支持的平台上）
        try:
            # 检查是否支持窗口
            if hasattr(toga, 'Window'):
                self.dialog_window = toga.Window(
                    title="选择文件夹",
                    size=(450, 550),
                    resizable=False
                )
                self.dialog_window.content = self.container
                self.dialog_window.show()
                return True
            else:
                # 平台不支持窗口，返回False以便使用嵌入模式
                return False
        except Exception as e:
            logger.warning(f"无法创建模态窗口: {e}")
            # 如果不支持对话框，返回False
            return False
