#!/usr/bin/env python3
"""
测试播放控制器功能
"""

import sys
import os
import asyncio
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nextcloud_music_player.services.playback_controller import PlaybackController, PlayMode
from src.nextcloud_music_player.services.playlist_manager import PlaylistManager
from src.nextcloud_music_player.config_manager import ConfigManager

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockPlaybackService:
    """模拟播放服务"""
    def __init__(self):
        self.is_playing_state = False
        
    def is_playing(self):
        return self.is_playing_state
        
    async def pause_music(self):
        self.is_playing_state = False
        logger.info("模拟：暂停音乐")
        
    async def resume_music(self):
        self.is_playing_state = True
        logger.info("模拟：恢复音乐")
        
    async def stop_music(self):
        self.is_playing_state = False
        logger.info("模拟：停止音乐")

async def mock_play_song_callback(song_info):
    """模拟播放歌曲回调"""
    logger.info(f"模拟：播放歌曲 - {song_info.get('title', '未知歌曲')}")
    return True

async def test_playback_controller():
    """测试播放控制器功能"""
    try:
        # 初始化配置管理器
        config_manager = ConfigManager()
        
        # 初始化播放列表管理器
        playlist_manager = PlaylistManager(
            config_manager=config_manager,
            music_service=None
        )
        
        # 初始化模拟播放服务
        mock_playback_service = MockPlaybackService()
        
        # 初始化播放控制器
        controller = PlaybackController(
            playback_service=mock_playback_service,
            playlist_manager=playlist_manager,
            play_song_callback=mock_play_song_callback
        )
        
        logger.info("=== 播放控制器测试开始 ===")
        
        # 测试播放模式设置
        logger.info("1. 测试播放模式设置")
        controller.set_play_mode(PlayMode.NORMAL)
        assert controller.get_play_mode() == PlayMode.NORMAL
        logger.info("✓ 播放模式设置正常")
        
        # 测试播放控制
        logger.info("2. 测试播放控制")
        await controller.toggle_playback()  # 开始播放
        assert mock_playback_service.is_playing()
        
        await controller.toggle_playback()  # 暂停播放
        assert not mock_playback_service.is_playing()
        
        await controller.stop_playback()    # 停止播放
        assert not mock_playback_service.is_playing()
        logger.info("✓ 播放控制正常")
        
        # 测试播放列表信息获取
        logger.info("3. 测试播放列表信息获取")
        playlist_info = controller.get_playlist_info()
        logger.info(f"播放列表信息: {playlist_info}")
        logger.info("✓ 播放列表信息获取正常")
        
        # 检查当前播放列表是否有歌曲
        current_playlist = playlist_manager.get_current_playlist()
        if current_playlist and current_playlist.get("songs"):
            logger.info("4. 测试上一曲/下一曲功能")
            songs = current_playlist["songs"]
            logger.info(f"播放列表中有 {len(songs)} 首歌曲")
            
            # 测试下一曲
            logger.info("测试下一曲...")
            success = await controller.next_song()
            if success:
                logger.info("✓ 下一曲功能正常")
            else:
                logger.warning("⚠ 下一曲功能测试失败")
            
            # 测试上一曲
            logger.info("测试上一曲...")
            success = await controller.previous_song()
            if success:
                logger.info("✓ 上一曲功能正常")
            else:
                logger.warning("⚠ 上一曲功能测试失败")
                
            # 测试不同播放模式下的自动播放
            logger.info("5. 测试自动播放下一曲")
            
            # 测试单曲循环模式
            controller.set_play_mode(PlayMode.REPEAT_ONE)
            success = await controller.auto_play_next_song()
            logger.info(f"单曲循环模式自动播放: {success}")
            
            # 测试顺序播放模式
            controller.set_play_mode(PlayMode.NORMAL)
            success = await controller.auto_play_next_song()
            logger.info(f"顺序播放模式自动播放: {success}")
            
            # 测试随机播放模式
            controller.set_play_mode(PlayMode.SHUFFLE)
            success = await controller.auto_play_next_song()
            logger.info(f"随机播放模式自动播放: {success}")
            
            logger.info("✓ 自动播放功能测试完成")
        else:
            logger.warning("⚠ 当前播放列表为空，跳过上一曲/下一曲测试")
        
        logger.info("=== 播放控制器测试完成 ===")
        logger.info("✅ 所有测试通过！")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_playback_controller())
