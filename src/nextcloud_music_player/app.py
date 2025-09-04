"""
NextCloud Music Player - 主应用类

这个文件包含应用的核心逻辑。
UI界面由视图管理器（ViewManager）和各个视图（View）负责。
音乐播放功能由播放服务（PlaybackService）负责。

主要职责：
1. 应用初始化和配置

"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import os
from pathlib import Path
import tempfile
import threading
import time
import logging
import random
from typing import Optional

try:
    import pygame
except ImportError:
    pygame = None

from .nextcloud_client import NextCloudClient
from .music_library import MusicLibrary
from .config_manager import ConfigManager



class NextCloudMusicPlayer(toga.App):
    """NextCloud音乐播放器主应用类"""
    
    def __init__(self):
        super().__init__(
            formal_name="NextCloud Music Player",
            app_id="com.example.nextcloud-music-player",
            app_name="nextcloud-music-player",
            description="A cross-platform music player with NextCloud integration",
            author="Your Name",
            version="0.1.0"
        )

    def startup(self):
        """应用启动初始化"""
        # 设置日志系统
        self.setup_logging()
        
        # 初始化配置管理器
        from .config_manager import ConfigManager
        self.config_manager = ConfigManager()
        
        # 🎵 iOS持久化检查和迁移
        self.config_manager.check_and_create_persistent_directories()
        
        # 尝试迁移音乐文件到持久化存储（iOS升级后首次启动）
        migration_success = self.config_manager.migrate_music_files_to_persistent_storage()
        if migration_success:
            self.logger.info("✅ 音乐文件持久化迁移检查完成")
        else:
            self.logger.warning("⚠️ 音乐文件迁移过程中出现问题")
        
        # 初始化核心组件
        self.nextcloud_client = None
        self.music_library = MusicLibrary()
        
        # UI 更新队列（线程安全）
        self._pending_ui_updates = []
        
        # 创建主窗口
        self.main_window = toga.MainWindow(title=self.formal_name)
        
        # 检测iOS平台并进行适配
        try:
            import platform
            current_platform = platform.system()
            if hasattr(self, 'app_context') and hasattr(self.app_context, 'platform'):
                # 如果有app_context，使用其中的平台信息
                platform_info = str(self.app_context.platform)
                if 'iOS' in platform_info:
                    self.logger.info("检测到iOS平台，启用移动设备适配")
            elif current_platform == 'Darwin':
                # 在macOS上运行，可能是iOS模拟器
                self.logger.info("在Darwin平台运行，可能是iOS模拟器")
        except Exception as e:
            self.logger.warning(f"平台检测失败: {e}")
            self.logger.info("使用通用移动设备适配")
        
        # 创建视图管理器
        from .views.view_manager import ViewManager
        self.view_manager = ViewManager(self)
        
        # 设置主窗口内容
        self.main_window.content = self.view_manager.main_container
        self.main_window.show()
       
        # 恢复上次的视图状态，默认显示播放界面
        last_view = self.config_manager.get("app.last_view", "playback")
        self.view_manager.switch_to_view(last_view)
        

    # ============================================
    # 核心功能方法区域
    # ============================================

    def setup_logging(self):
        """设置日志系统"""
        try:
            # 创建配置管理器实例来获取日志目录
            config_manager = ConfigManager()
            log_dir = config_manager.get_log_directory()
            log_file = log_dir / 'nextcloud_music_player.log'
            
            # 尝试设置文件日志
            handlers = [logging.StreamHandler()]  # 至少保证控制台输出
            
            try:
                handlers.append(logging.FileHandler(str(log_file)))
            except (PermissionError, OSError) as e:
                # 此时还没有logger，暂时使用print，但后面会被logger替代
                logging.warning(f"⚠️ 无法创建日志文件 {log_file}: {e}")
                logging.info("📝 将仅使用控制台日志输出")
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=handlers
            )
            self.logger = logging.getLogger(__name__)
            self.logger.info("✅ 日志系统初始化完成")
            
        except Exception as e:
            # 如果所有日志设置都失败，至少设置基本控制台日志
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"❌ 设置日志系统失败: {e}")
            self.logger.error(f"日志系统设置失败，使用基本配置: {e}")


    def add_background_task(self, task):
        """添加后台任务到主线程."""
        try:
            # 尝试使用 asyncio 事件循环调度到主线程
            import asyncio
            import inspect
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 检查task是否是协程函数
                    if inspect.iscoroutinefunction(task):
                        # 如果是协程函数，创建任务
                        loop.create_task(task())
                        self.logger.debug("已创建协程任务")
                        return
                    elif inspect.iscoroutine(task):
                        # 如果是协程对象，直接创建任务
                        loop.create_task(task)
                        self.logger.debug("已创建协程对象任务")
                        return
                    else:
                        # 如果是普通函数，使用call_soon_threadsafe
                        loop.call_soon_threadsafe(task)
                        self.logger.debug("已安排普通函数执行")
                        return
            except Exception as loop_error:
                self.logger.error(f"事件循环处理失败: {loop_error}")
            
            # 降级方案：标记需要更新UI，在主线程中处理
            self._pending_ui_updates.append(task)
            self.logger.debug("已添加到待处理更新列表")
        except Exception as e:
            self.logger.error(f"❌ [TASK] 无法执行后台任务: {e}")



def main():
    return NextCloudMusicPlayer()
