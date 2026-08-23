"""
服务层模块 - 提供业务逻辑的抽象接口
"""

from .lyrics_service import LyricsService
from .music_service import MusicService

__all__ = ["MusicService", "LyricsService"]
