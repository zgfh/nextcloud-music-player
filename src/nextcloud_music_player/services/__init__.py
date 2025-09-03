"""
服务层模块 - 提供业务逻辑的抽象接口
"""

from .music_service import MusicService
from .lyrics_service import LyricsService

__all__ = ['MusicService', 'LyricsService']
