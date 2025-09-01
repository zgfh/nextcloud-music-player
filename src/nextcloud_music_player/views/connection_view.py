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
        password_container = toga.Box(style=Pack(direction=ROW, alignment="center", padding=(0, 0, 8, 0)))
        
        self.password_input = toga.PasswordInput(
            placeholder="输入密码",
            style=Pack(flex=1, padding=(0, 3, 0, 0), font_size=12)
        )
        
        self.password_text_input = toga.TextInput(
            placeholder="输入密码",
            style=Pack(flex=1, padding=(0, 3, 0, 0), font_size=12)
        )
        self.password_text_input.style.display = "none"
        
        self.show_password_button = toga.Button(
            "👁️",
            on_press=self.toggle_password_visibility,
            style=Pack(width=30, height=25, font_size=10)
        )
        
        password_container.add(self.password_input)
        password_container.add(self.password_text_input)
        password_container.add(self.show_password_button)
        
        # 同步文件夹
        folder_label = toga.Label("同步文件夹路径 (可选):", style=Pack(padding=(0, 0, 3, 0), color="#495057", font_size=12))
        self.sync_folder_input = toga.TextInput(
            placeholder="/Music 或留空表示根目录",
            style=Pack(padding=(0, 0, 8, 0), font_size=12)
        )
        
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
        form_box.add(password_container)
        form_box.add(folder_label)
        form_box.add(self.sync_folder_input)
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
            
            logger.info("连接配置已保存")
        except Exception as e:
            logger.error(f"保存连接配置失败: {e}")
    
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
        
        if self.password_visible:
            self.password_input.style.display = "none"
            self.password_text_input.style.display = "block"
            self.show_password_button.text = "🙈"
        else:
            self.password_input.style.display = "block"
            self.password_text_input.style.display = "none"
            self.show_password_button.text = "👁️"
        
        # 同步密码值
        if self.password_visible:
            self.password_text_input.value = self.password_input.value
        else:
            self.password_input.value = self.password_text_input.value
    
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
    