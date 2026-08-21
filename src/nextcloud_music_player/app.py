"""
NextCloud Music Player - Flet 主入口
"""

import flet as ft
import asyncio
import logging
from typing import Optional

from .config_manager import ConfigManager
from .music_library import MusicLibrary

logger = logging.getLogger(__name__)

# 全局应用上下文
app_context = {}


def setup_logging():
    """设置日志系统"""
    try:
        config_manager = ConfigManager()
        log_dir = config_manager.get_log_directory()
        log_file = log_dir / 'nextcloud_music_player.log'

        handlers = [logging.StreamHandler()]
        try:
            handlers.append(logging.FileHandler(str(log_file)))
        except (PermissionError, OSError):
            pass

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        logger.info("日志系统初始化完成")
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logger.error(f"设置日志系统失败: {e}")


async def main(page: ft.Page):
    """Flet 应用主入口"""
    # 页面配置
    page.title = "NextCloud Music Player"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = ft.Colors.GREY_50

    # 设置日志
    setup_logging()

    # 初始化服务层
    config_manager = ConfigManager()
    config_manager.check_and_create_persistent_directories()
    config_manager.migrate_music_files_to_persistent_storage()

    music_library = MusicLibrary()

    # 保存到全局上下文
    app_context['config_manager'] = config_manager
    app_context['music_library'] = music_library
    app_context['nextcloud_client'] = None
    app_context['page'] = page

    # 创建视图管理器
    from .views.view_manager import ViewManager
    view_manager = ViewManager(page, app_context)

    # 恢复上次视图
    last_view = config_manager.get("app.last_view", "playback")
    view_manager.switch_to_view(last_view)
