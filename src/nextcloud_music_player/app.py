"""
Cloud Music Player - Flet 主入口
"""

import logging

import flet as ft

from .config_manager import ConfigManager
from .music_library import MusicLibrary
from .utils.log_buffer import (
    LOG_FILE_NAME,
    LOG_FORMAT,
    RingBufferHandler,
    install_exception_hooks,
)
from .utils.theme import Color

logger = logging.getLogger(__name__)


def setup_logging():
    """设置日志系统（控制台 + 文件 + 内存环形缓冲，未捕获异常也落日志）"""
    try:
        config_manager = ConfigManager()
        log_dir = config_manager.get_log_directory()
        log_file = log_dir / LOG_FILE_NAME

        level_name = str(config_manager.get("app.log_level", "INFO")).upper()
        level = getattr(logging, level_name, logging.INFO)

        handlers: list[logging.Handler] = [logging.StreamHandler()]
        try:
            handlers.append(logging.FileHandler(str(log_file)))
        except (PermissionError, OSError):
            pass
        handlers.append(RingBufferHandler())

        logging.basicConfig(
            level=level,
            format=LOG_FORMAT,
            handlers=handlers,
        )
        install_exception_hooks()
        logger.info(f"日志系统初始化完成 (level={level_name})")
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logger.error(f"设置日志系统失败: {e}")


async def main(page: ft.Page):
    """Flet 应用主入口"""
    # 页面配置 - 深空霓虹主题
    page.title = "Cloud Music Player"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.bgcolor = Color.BG_APP

    # 全局主题（青色种子 + 深色表面）
    color_scheme = ft.ColorScheme(
        primary=Color.PRIMARY,
        on_primary=Color.PRIMARY_TEXT,
        secondary=Color.ACCENT,
        surface=Color.BG_SURFACE,
        surface_dim=Color.BG_APP,
        surface_container=Color.BG_SURFACE,
        surface_container_low=Color.BG_SURFACE_ALT,
        surface_container_high=Color.BG_ELEVATED,
        on_surface=Color.TEXT_PRIMARY,
        on_surface_variant=Color.TEXT_SECONDARY,
        outline=Color.BORDER,
        outline_variant=Color.BORDER,
    )
    page.theme = ft.Theme(color_scheme=color_scheme)
    page.dark_theme = page.theme

    # 设置日志
    setup_logging()

    # 初始化服务层
    config_manager = ConfigManager()
    config_manager.check_and_create_persistent_directories()
    config_manager.migrate_music_files_to_persistent_storage()

    music_library = MusicLibrary()

    # 每个会话独立的上下文（Web 模式下多个浏览器标签页 = 多个会话，
    # 共用模块级全局字典会导致 A 会话连接的客户端被 B 会话覆盖/清空）
    app_context = {
        "config_manager": config_manager,
        "music_library": music_library,
        "nextcloud_client": None,
        # 多来源客户端注册表；nextcloud_client 保留为兼容旧视图/服务的活动客户端。
        "source_clients": {},
        "page": page,
    }

    # 创建视图管理器
    from .views.view_manager import ViewManager

    view_manager = ViewManager(page, app_context)

    # iOS：立即重建原生后台下载会话。系统会因后台下载完成而唤醒甚至
    # 重启应用，每次启动用同一 identifier 重建会话，被杀前已提交的任务
    # 才能交付结果并落库；非 iOS 平台为 no-op
    from .ios_background_download import activate

    activate(view_manager.music_service)

    # 恢复上次视图
    last_view = config_manager.get("app.last_view", "playback")
    view_manager.switch_to_view(last_view)
