"""
连接配置视图 - NextCloud连接设置和管理
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConnectionView:
    """NextCloud连接配置视图"""
    
    def __init__(self, app, view_manager):
        self.app = app
        self.view_manager = view_manager
        self.password_visible = False
        self.is_connected = False
        
        # 创建滚动视图容器以适配iOS设备
        self.container = toga.ScrollContainer(
            content=toga.Box(style=Pack(direction=COLUMN, padding=10)),
            style=Pack(flex=1)
        )
        
        # 构建界面
        self.build_interface()
        
        # 加载保存的配置
        self.load_saved_config()
    
    def build_interface(self):
        """构建连接配置界面 - iOS优化版本"""
        # 获取容器内容
        content_box = self.container.content
        
        # 标题 - 减小字体和填充
        title = toga.Label(
            "🌐 NextCloud 连接配置",
            style=Pack(
                padding=(0, 0, 10, 0),
                font_size=16,
                font_weight="bold",
                text_align="center",
                color="#212529"
            )
        )
        
        # 连接状态显示 - 减少填充
        self.status_box = toga.Box(style=Pack(
            direction=ROW,
            padding=5,
            background_color="#f0f0f0"
        ))
        
        self.status_label = toga.Label(
            "状态: 未连接",
            style=Pack(
                flex=1, 
                font_weight="bold",
                color="#495057"  # 深色文字，确保可见性
            )
        )
        
        self.status_box.add(self.status_label)
        
        # 配置表单 - 减少填充
        form_box = toga.Box(style=Pack(direction=COLUMN, padding=5))
        
        # 服务器地址 - 减小宽度以适应移动设备
        url_label = toga.Label("服务器地址:", style=Pack(padding=(0, 0, 3, 0), color="#495057", font_size=12))
        self.url_input = toga.TextInput(
            placeholder="https://your-nextcloud.com",
            style=Pack(padding=(0, 0, 8, 0), font_size=12)
        )
        
        # 用户名
        username_label = toga.Label("用户名:", style=Pack(padding=(0, 0, 3, 0), color="#495057", font_size=12))
        self.username_input = toga.TextInput(
            placeholder="输入用户名",
            style=Pack(padding=(0, 0, 8, 0), font_size=12)
        )
        
        # 密码
        password_label = toga.Label("密码:", style=Pack(padding=(0, 0, 3, 0), color="#495057", font_size=12))
        self.password_container = toga.Box(style=Pack(direction=ROW, alignment="center", padding=(0, 0, 8, 0)))
        
        self.password_input = toga.PasswordInput(
            placeholder="输入密码",
            style=Pack(flex=1, padding=(0, 3, 0, 0), font_size=12)
        )
        
        self.password_text_input = toga.TextInput(
            placeholder="输入密码",
            style=Pack(flex=1, padding=(0, 3, 0, 0), font_size=12)
        )
        
        self.show_password_button = toga.Button(
            "👁️",
            on_press=self.toggle_password_visibility,
            style=Pack(width=30, height=25, font_size=10)
        )
        
        # 初始状态只添加密码输入框
        self.password_container.add(self.password_input)
        self.password_container.add(self.show_password_button)
        
        # 同步文件夹
        folder_label = toga.Label("同步文件夹路径 (可选):", style=Pack(padding=(0, 0, 3, 0), color="#495057", font_size=12))
        
        # 文件夹选择容器
        folder_container = toga.Box(style=Pack(direction=ROW, padding=(0, 0, 8, 0)))
        
        self.sync_folder_input = toga.TextInput(
            placeholder="/Music 或留空表示根目录",
            style=Pack(flex=1, padding=(0, 3, 0, 0), font_size=12),
            on_change=self.on_sync_folder_changed
        )
        
        self.browse_folder_button = toga.Button(
            "📁 浏览",
            on_press=self.browse_folder,
            style=Pack(
                width=60,
                height=25,
                padding=3,
                background_color="#17a2b8",
                color="white",
                font_size=10
            )
        )
        
        folder_container.add(self.sync_folder_input)
        folder_container.add(self.browse_folder_button)
        
        # 配置选项 - 减少填充
        options_box = toga.Box(style=Pack(direction=COLUMN, padding=3))
        
        # 记住密码选项
        self.remember_password_switch = toga.Switch(
            text="记住密码",
            value=True,
            style=Pack(padding=(0, 0, 5, 0), font_size=11)
        )
        
        # 自动连接选项
        self.auto_connect_switch = toga.Switch(
            text="启动时自动连接",
            value=False,
            style=Pack(padding=(0, 0, 5, 0), font_size=11)
        )
        
        options_box.add(self.remember_password_switch)
        options_box.add(self.auto_connect_switch)
        
        # 按钮组 - 减少填充和按钮尺寸
        button_box = toga.Box(style=Pack(direction=ROW, padding=5))
        
        self.connect_button = toga.Button(
            "🔗 连接",
            on_press=self.connect_to_nextcloud,
            style=Pack(
                padding=3,
                background_color="#007AFF",
                color="white",
                width=80,
                height=30,
                font_size=12
            )
        )
        
        self.disconnect_button = toga.Button(
            "🔌 断开",
            on_press=self.disconnect_from_nextcloud,
            enabled=False,
            style=Pack(padding=3, width=80, height=30, font_size=12)
        )
        
        self.test_button = toga.Button(
            "🔍 测试",
            on_press=self.test_connection,
            style=Pack(
                padding=3,
                background_color="#FF9500",
                color="white",
                width=80,
                height=30,
                font_size=12
            )
        )
        
        button_box.add(self.connect_button)
        button_box.add(self.disconnect_button)
        button_box.add(self.test_button)
        
        # 消息显示区域 - 减少填充
        self.message_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=5,
            background_color="#f9f9f9"
        ))
        
        # 组装界面 - 使用滚动容器的内容
        form_box.add(url_label)
        form_box.add(self.url_input)
        form_box.add(username_label)
        form_box.add(self.username_input)
        form_box.add(password_label)
        form_box.add(self.password_container)
        form_box.add(folder_label)
        form_box.add(folder_container)
        form_box.add(options_box)
        form_box.add(button_box)
        
        # 添加到滚动容器的内容中
        content_box.add(title)
        content_box.add(self.status_box)
        content_box.add(form_box)
        content_box.add(self.message_box)
    
    def load_saved_config(self):
        """加载保存的配置"""
        try:
            # 从配置管理器加载连接配置
            config = self.app.config_manager.get("connection", {})
            
            self.url_input.value = config.get("server_url", "http://cloud.home.daozzg.com")
            self.username_input.value = config.get("username", "guest")
            
            # 如果记住密码选项开启，则加载密码
            if config.get("remember_credentials", True):
                self.password_input.value = config.get("password", "")
                self.password_text_input.value = config.get("password", "")
            
            self.sync_folder_input.value = config.get("default_sync_folder", "/mp3/音乐/当月抖音热播流行歌曲484首/")
            self.auto_connect_switch.value = config.get("auto_connect", False)
            self.remember_password_switch.value = config.get("remember_credentials", True)
            
            # 如果开启了自动连接，尝试连接
            if config.get("auto_connect", False):
                self.app.add_background_task(self.auto_connect)
                
            logger.info("连接配置已加载")
        except Exception as e:
            logger.error(f"加载连接配置失败: {e}")
    
    def save_config(self):
        """保存连接配置"""
        try:
            connection_config = {
                "server_url": self.url_input.value,
                "username": self.username_input.value,
                "default_sync_folder": self.sync_folder_input.value,
                "auto_connect": self.auto_connect_switch.value,
                "remember_credentials": self.remember_password_switch.value
            }
            
            # 如果记住密码选项开启，保存密码
            if self.remember_password_switch.value:
                if self.password_visible:
                    connection_config["password"] = self.password_text_input.value
                else:
                    connection_config["password"] = self.password_input.value
            else:
                connection_config["password"] = ""
            
            # 保存到配置管理器
            for key, value in connection_config.items():
                self.app.config_manager.set(f"connection.{key}", value)
            
            # 重要：将配置保存到文件
            success = self.app.config_manager.save_config()
            if success:
                logger.info("连接配置已保存到文件")
            else:
                logger.error("连接配置保存到文件失败")
        except Exception as e:
            logger.error(f"保存连接配置失败: {e}")
    
    def on_sync_folder_changed(self, widget):
        """当同步文件夹输入发生变化时自动保存"""
        try:
            # 延迟保存，避免用户快速输入时频繁保存
            import threading
            def delayed_save():
                import time
                time.sleep(2)  # 等待2秒，如果用户继续输入则重置计时器
                try:
                    new_value = widget.value.strip()
                    current_value = self.app.config_manager.get("connection.default_sync_folder", "")
                    if new_value != current_value:
                        self.app.config_manager.set("connection.default_sync_folder", new_value)
                        success = self.app.config_manager.save_config()
                        if success:
                            logger.info(f"同步目录已自动保存: {new_value}")
                        else:
                            logger.error("同步目录自动保存失败")
                except Exception as e:
                    logger.error(f"自动保存同步目录失败: {e}")
            
            # 取消之前的延迟保存任务
            if hasattr(self, '_save_timer'):
                self._save_timer.cancel()
            
            # 启动新的延迟保存任务
            self._save_timer = threading.Timer(2.0, delayed_save)
            self._save_timer.start()
            
        except Exception as e:
            logger.error(f"处理同步文件夹变化失败: {e}")
    
    async def auto_connect(self):
        """自动连接"""
        try:
            await asyncio.sleep(1)  # 等待界面完全加载
            await self.connect_to_nextcloud(None)
        except Exception as e:
            logger.error(f"自动连接失败: {e}")
    
    def toggle_password_visibility(self, widget):
        """切换密码显示/隐藏"""
        self.password_visible = not self.password_visible
        
        # 获取密码容器（password_container）
        password_container = self.password_container
        
        if self.password_visible:
            # 显示明文密码：移除密码输入框，添加文本输入框
            if self.password_input in password_container.children:
                # 同步密码值
                self.password_text_input.value = self.password_input.value
                password_container.remove(self.password_input)
                password_container.insert(0, self.password_text_input)
            self.show_password_button.text = "�"
        else:
            # 隐藏明文密码：移除文本输入框，添加密码输入框
            if self.password_text_input in password_container.children:
                # 同步密码值
                self.password_input.value = self.password_text_input.value
                password_container.remove(self.password_text_input)
                password_container.insert(0, self.password_input)
            self.show_password_button.text = "👁️"
    
    async def connect_to_nextcloud(self, widget):
        """连接到NextCloud"""
        try:
            # 获取输入值
            server_url = self.url_input.value.strip()
            username = self.username_input.value.strip()
            password = self.password_input.value if not self.password_visible else self.password_text_input.value
            sync_folder = self.sync_folder_input.value.strip()
            
            # 验证输入
            if not server_url or not username or not password:
                self.show_message("请填写完整的连接信息", "error")
                return
            
            self.show_message("正在连接...", "info")
            self.connect_button.enabled = False
            
            # 创建NextCloud客户端
            from ..nextcloud_client import NextCloudClient
            self.app.nextcloud_client = NextCloudClient(server_url, username, password)
            
            # 更新音乐服务中的NextCloud客户端
            if hasattr(self.app, 'music_service'):
                self.app.music_service.update_nextcloud_client(self.app.nextcloud_client)
            
            # 更新歌词服务中的NextCloud客户端
            if hasattr(self.app, 'lyrics_service'):
                self.app.lyrics_service.update_clients(nextcloud_client=self.app.nextcloud_client)
            
            # 测试连接
            success = await self.app.nextcloud_client.test_connection()
            
            if success:
                self.is_connected = True
                self.update_connection_status(True)
                self.show_message("连接成功！", "success")
                
                # 保存配置
                self.save_config()
                
                # 切换到文件列表视图
                self.view_manager.switch_to_view("file_list")
                
            else:
                self.show_message("连接失败，请检查服务器地址和凭据", "error")
                self.update_connection_status(False)
                
        except Exception as e:
            logger.error(f"连接NextCloud失败: {e}")
            self.show_message(f"连接错误: {str(e)}", "error")
            self.update_connection_status(False)
        finally:
            self.connect_button.enabled = True
    
    async def disconnect_from_nextcloud(self, widget):
        """断开NextCloud连接"""
        try:
            self.app.nextcloud_client = None
            
            # 更新音乐服务中的NextCloud客户端
            if hasattr(self.app, 'music_service'):
                self.app.music_service.update_nextcloud_client(None)
            
            # 更新歌词服务中的NextCloud客户端
            if hasattr(self.app, 'lyrics_service'):
                self.app.lyrics_service.update_clients(nextcloud_client=None)
           
            self.is_connected = False
            self.update_connection_status(False)
            self.show_message("已断开连接", "info")

        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            self.show_message(f"断开连接错误: {str(e)}", "error")
    
    async def test_connection(self, widget):
        """测试连接"""
        try:
            server_url = self.url_input.value.strip()
            username = self.username_input.value.strip()
            password = self.password_input.value if not self.password_visible else self.password_text_input.value
            
            if not server_url or not username or not password:
                self.show_message("请填写完整的连接信息", "error")
                return
            
            self.show_message("正在测试连接...", "info")
            self.test_button.enabled = False
            
            # 创建临时客户端测试
            from ..nextcloud_client import NextCloudClient
            temp_client = NextCloudClient(server_url, username, password)
            
            success = await temp_client.test_connection()
            
            if success:
                self.show_message("连接测试成功！", "success")
            else:
                self.show_message("连接测试失败", "error")
                
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            self.show_message(f"测试错误: {str(e)}", "error")
        finally:
            self.test_button.enabled = True
    
    def update_connection_status(self, connected: bool):
        """更新连接状态显示"""
        if connected:
            self.status_label.text = "状态: ✅ 已连接"
            self.status_box.style.background_color = "#d4edda"
            self.connect_button.enabled = False
            self.disconnect_button.enabled = True
        else:
            self.status_label.text = "状态: ❌ 未连接"
            self.status_box.style.background_color = "#f8d7da"
            self.connect_button.enabled = True
            self.disconnect_button.enabled = False
    
    def show_message(self, message: str, message_type: str = "info"):
        """显示消息"""
        # 清空之前的消息
        self.message_box.clear()
        
        # 根据消息类型设置样式
        if message_type == "success":
            bg_color = "#d4edda"
            text_color = "#155724"
            icon = "✅"
        elif message_type == "error":
            bg_color = "#f8d7da"
            text_color = "#721c24"
            icon = "❌"
        else:  # info
            bg_color = "#d1ecf1"
            text_color = "#0c5460"
            icon = "ℹ️"
        
        message_label = toga.Label(
            f"{icon} {message}",
            style=Pack(
                padding=10,
                background_color=bg_color,
                color=text_color,
                text_align="center"
            )
        )
        
        self.message_box.add(message_label)
        logger.info(f"[{message_type.upper()}] {message}")
    
    def on_view_activated(self):
        """当视图被激活时调用"""
        # 检查连接状态
        if self.app.nextcloud_client:
            self.update_connection_status(True)
        else:
            self.update_connection_status(False)
    
    def browse_folder(self, widget):
        """浏览文件夹"""
        try:
            # 检查是否已连接
            if not self.app.nextcloud_client:
                self.show_message("请先连接到NextCloud服务器", "error")
                return
            
            # 导入文件夹选择器
            from .folder_selector import FolderSelector
            
            # 创建文件夹选择器
            current_folder = self.sync_folder_input.value.strip()
            folder_selector = FolderSelector(
                app=self.app,
                nextcloud_client=self.app.nextcloud_client,
                initial_path=current_folder
            )
            
            # 设置回调函数
            def on_folder_selected(selected_path):
                self.sync_folder_input.value = selected_path
                self.show_message(f"已选择文件夹: {selected_path or '/'}", "success")
                
                # 自动保存同步目录配置
                try:
                    self.app.config_manager.set("connection.default_sync_folder", selected_path)
                    success = self.app.config_manager.save_config()
                    if success:
                        logger.info(f"同步目录已保存: {selected_path}")
                    else:
                        logger.error("同步目录保存失败")
                except Exception as e:
                    logger.error(f"保存同步目录配置失败: {e}")
                
                # 清空嵌入的选择器
                self.message_box.clear()
            
            # 尝试显示文件夹选择器
            success = folder_selector.show_dialog(on_folder_selected)
            if not success:
                # 如果不支持对话框，在当前视图中显示选择器
                self.show_embedded_folder_selector(folder_selector, on_folder_selected)
                
        except Exception as e:
            logger.error(f"打开文件夹浏览器失败: {e}")
            self.show_message(f"无法打开文件夹浏览器: {str(e)}", "error")
    
    def show_embedded_folder_selector(self, folder_selector, callback):
        """在当前视图中嵌入显示文件夹选择器"""
        try:
            # 清空消息区域，用于显示文件夹选择器
            self.message_box.clear()
            
            # 设置回调
            folder_selector.on_path_selected = callback
            
            # 添加文件夹选择器到消息区域
            self.message_box.add(folder_selector.container)
            
            self.show_message("请在下方选择文件夹", "info")
            
        except Exception as e:
            logger.error(f"嵌入文件夹选择器失败: {e}")
            self.show_message("无法显示文件夹选择器", "error")
    