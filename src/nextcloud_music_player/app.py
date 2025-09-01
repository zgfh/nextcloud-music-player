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
from enum import Enum
import random
from typing import Optional

try:
    import pygame
except ImportError:
    pygame = None

from .nextcloud_client import NextCloudClient
from .music_library import MusicLibrary
from .config_manager import ConfigManager


class PlayMode(Enum):
    """播放模式枚举"""
    NORMAL = "normal"
    REPEAT_ONE = "repeat_one"
    REPEAT_ALL = "repeat_all"
    SHUFFLE = "shuffle"


class NextCloudMusicPlayer(toga.App):
    """NextCloud音乐播放器主应用类"""

    def startup(self):
        """应用启动初始化"""
        # 设置日志系统
        self.setup_logging()
        
        # 注意：pygame初始化现在由播放服务处理
        
        # 初始化配置管理器
        from .config_manager import ConfigManager
        self.config_manager = ConfigManager()
        
        # 初始化核心组件
        self.nextcloud_client = None
        self.music_library = MusicLibrary()
        
        # 播放状态管理（保留用于兼容性和UI显示）
        self.current_song = None
        self.current_song_index = 0
        self.playlist = []
        self.is_playing = False  # 保留用于兼容性
        self.is_paused = False   # 保留用于兼容性
        self.play_mode = PlayMode.REPEAT_ONE
        self.volume = self.config_manager.get("player.volume", 70) / 100.0
        self.position = 0  # 播放位置（秒）
        self.duration = 0  # 歌曲总时长（秒）
        
        # 下载状态管理
        self.selected_song_name = None
        self._downloading_songs = set()
        self._download_queue = []
        self._download_stats = {
            'total_count': 0,
            'downloaded_count': 0,
            'downloading_count': 0,
            'queue_count': 0
        }
        
        # UI 更新队列（线程安全）
        self._pending_ui_updates = []
        self._ui_needs_play_update = False
        self._ui_needs_position_update = False
        
        # 创建主窗口
        self.main_window = toga.MainWindow(title=self.formal_name)
        
        # 创建视图管理器
        from .views.view_manager import ViewManager
        self.view_manager = ViewManager(self)
        
        # 设置主窗口内容
        self.main_window.content = self.view_manager.main_container
        self.main_window.show()
        
        # TODO: 实现播放位置监控定时器
        # self.start_position_timer()
        
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
                print(f"⚠️ 无法创建日志文件 {log_file}: {e}")
                print("📝 将仅使用控制台日志输出")
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=handlers
            )
            self.logger = logging.getLogger(__name__)
            self.logger.info("✅ 日志系统初始化完成")
            
        except Exception as e:
            # 如果所有日志设置都失败，至少设置基本控制台日志
            print(f"❌ 设置日志系统失败: {e}")
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"日志系统设置失败，使用基本配置: {e}")


    def add_background_task(self, task):
        """添加后台任务到主线程."""
        try:
            # 尝试使用 asyncio 事件循环调度到主线程
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(task)
                    return
            except:
                pass
            
            # 降级方案：标记需要更新UI，在主线程中处理
            self._pending_ui_updates.append(task)
        except Exception as e:
            print(f"❌ [TASK] 无法执行后台任务: {e}")



def main():
    return NextCloudMusicPlayer()
