"""
播放控制器 - 专门处理播放控制逻辑
包括上一曲、下一曲、播放模式控制等功能
"""

import logging
from typing import Optional, Dict, List, Any
from enum import Enum
import random

logger = logging.getLogger(__name__)

class PlayMode(Enum):
    """播放模式枚举"""
    NORMAL = "normal"
    REPEAT_ONE = "repeat_one"
    REPEAT_ALL = "repeat_all"
    SHUFFLE = "shuffle"

class PlaybackController:
    """播放控制器 - 负责播放逻辑控制"""
    
    def __init__(self, playback_service, playlist_manager, play_song_callback=None):
        """
        初始化播放控制器
        
        Args:
            playback_service: 播放服务实例
            playlist_manager: 播放列表管理器实例
            play_song_callback: 播放歌曲的回调函数
        """
        self.playback_service = playback_service
        self.playlist_manager = playlist_manager
        self.play_song_callback = play_song_callback
        self.play_mode = PlayMode.REPEAT_ONE
        
        logger.info("播放控制器初始化完成")
    
    def set_play_mode(self, mode: PlayMode):
        """设置播放模式"""
        self.play_mode = mode
        logger.info(f"播放模式已设置为: {mode.value}")
    
    def get_play_mode(self) -> PlayMode:
        """获取当前播放模式"""
        return self.play_mode
    
    async def toggle_playback(self):
        """切换播放/暂停状态"""
        try:
            if self.playback_service.is_playing():
                await self.playback_service.pause_music()
                logger.info("播放已暂停")
            else:
                await self.playback_service.resume_music()
                logger.info("播放已恢复")
        except Exception as e:
            logger.error(f"切换播放状态失败: {e}")
            raise
    
    async def stop_playback(self):
        """停止播放"""
        try:
            await self.playback_service.stop_music()
            logger.info("播放已停止")
        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            raise
    
    async def previous_song(self):
        """播放上一曲"""
        try:
            logger.info("开始切换到上一曲")
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist or not current_playlist.get("songs"):
                logger.warning("播放列表为空，无法切换到上一曲")
                return False
            
            current_index = current_playlist.get("current_index", 0)
            songs = current_playlist["songs"]
            
            # 根据播放模式确定上一首歌曲
            new_index = self._calculate_previous_index(current_index, len(songs))
            
            # 更新播放列表索引
            current_playlist["current_index"] = new_index
            self.playlist_manager.save_current_playlist(current_playlist)
            
            # 播放选中的歌曲 - 添加保护机制
            selected_song = songs[new_index]
            if self.play_song_callback:
                try:
                    logger.info(f"准备播放上一曲: {selected_song['info'].get('title', '未知')}")
                    await self.play_song_callback(selected_song["info"])
                    logger.info(f"已切换到上一曲: {selected_song['info'].get('title', '未知')}")
                except Exception as callback_error:
                    logger.error(f"播放回调失败: {callback_error}")
                    # 即使播放失败，也要返回True，因为索引已经更新了
                    return True
            
            return True
            
        except Exception as e:
            logger.error(f"上一曲失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    async def next_song(self):
        """播放下一曲"""
        try:
            logger.info("开始切换到下一曲")
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist or not current_playlist.get("songs"):
                logger.warning("播放列表为空，无法切换到下一曲")
                return False
            
            current_index = current_playlist.get("current_index", 0)
            songs = current_playlist["songs"]
            
            # 根据播放模式确定下一首歌曲
            new_index = self._calculate_next_index(current_index, len(songs))
            
            # 更新播放列表索引
            current_playlist["current_index"] = new_index
            self.playlist_manager.save_current_playlist(current_playlist)
            
            # 播放选中的歌曲 - 添加保护机制
            selected_song = songs[new_index]
            if self.play_song_callback:
                try:
                    logger.info(f"准备播放下一曲: {selected_song['info'].get('title', '未知')}")
                    await self.play_song_callback(selected_song["info"])
                    logger.info(f"已切换到下一曲: {selected_song['info'].get('title', '未知')}")
                except Exception as callback_error:
                    logger.error(f"播放回调失败: {callback_error}")
                    # 即使播放失败，也要返回True，因为索引已经更新了
                    return True
            
            return True
            
        except Exception as e:
            logger.error(f"下一曲失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    async def auto_play_next_song(self):
        """自动播放下一曲（歌曲结束时调用）"""
        try:
            logger.info("开始自动播放下一曲逻辑")
            
            # 根据播放模式决定是否自动播放下一曲
            if self.play_mode == PlayMode.REPEAT_ONE:
                # 单曲循环：重新播放当前歌曲
                logger.info("单曲循环模式：重新播放当前歌曲")
                current_playlist = self.playlist_manager.get_current_playlist()
                if current_playlist and current_playlist.get("songs"):
                    current_index = current_playlist.get("current_index", 0)
                    songs = current_playlist["songs"]
                    if 0 <= current_index < len(songs):
                        selected_song = songs[current_index]
                        if self.play_song_callback:
                            await self.play_song_callback(selected_song["info"])
                        return True
            else:
                # 其他模式：播放下一曲
                logger.info(f"{self.play_mode.value}模式：播放下一曲")
                return await self.next_song()
                
            return False
            
        except Exception as e:
            logger.error(f"自动播放下一曲失败: {e}")
            return False
    
    def _calculate_previous_index(self, current_index: int, total_songs: int) -> int:
        """计算上一首歌曲的索引"""
        if total_songs == 0:
            return 0
            
        if self.play_mode == PlayMode.SHUFFLE:
            # 随机模式：随机选择一首（排除当前）
            available_indices = [i for i in range(total_songs) if i != current_index]
            if available_indices:
                return random.choice(available_indices)
            else:
                return current_index
        else:
            # 顺序模式：上一首
            return (current_index - 1) % total_songs
    
    def _calculate_next_index(self, current_index: int, total_songs: int) -> int:
        """计算下一首歌曲的索引"""
        if total_songs == 0:
            return 0
            
        if self.play_mode == PlayMode.SHUFFLE:
            # 随机模式：随机选择一首（排除当前）
            available_indices = [i for i in range(total_songs) if i != current_index]
            if available_indices:
                return random.choice(available_indices)
            else:
                return current_index
        elif self.play_mode == PlayMode.REPEAT_ONE:
            # 单曲循环：保持当前歌曲（在手动切换时仍然切换到下一首）
            return (current_index + 1) % total_songs
        else:
            # 顺序播放或列表循环
            return (current_index + 1) % total_songs
    
    def get_current_song_info(self) -> Optional[Dict[str, Any]]:
        """获取当前歌曲信息"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist or not current_playlist.get("songs"):
                return None
            
            current_index = current_playlist.get("current_index", 0)
            songs = current_playlist["songs"]
            
            if 0 <= current_index < len(songs):
                return songs[current_index]["info"]
            
            return None
            
        except Exception as e:
            logger.error(f"获取当前歌曲信息失败: {e}")
            return None
    
    def get_playlist_info(self) -> Dict[str, Any]:
        """获取播放列表信息"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist:
                return {
                    "total_songs": 0,
                    "current_index": 0,
                    "current_song": None,
                    "has_previous": False,
                    "has_next": False
                }
            
            songs = current_playlist.get("songs", [])
            current_index = current_playlist.get("current_index", 0)
            total_songs = len(songs)
            
            return {
                "total_songs": total_songs,
                "current_index": current_index,
                "current_song": songs[current_index]["info"] if 0 <= current_index < total_songs else None,
                "has_previous": total_songs > 1,
                "has_next": total_songs > 1
            }
            
        except Exception as e:
            logger.error(f"获取播放列表信息失败: {e}")
            return {
                "total_songs": 0,
                "current_index": 0,
                "current_song": None,
                "has_previous": False,
                "has_next": False
            }
    
    async def play_song_by_index(self, index: int):
        """根据索引播放歌曲"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist or not current_playlist.get("songs"):
                logger.warning("播放列表为空，无法播放歌曲")
                return False
            
            songs = current_playlist["songs"]
            if 0 <= index < len(songs):
                # 更新播放列表索引
                current_playlist["current_index"] = index
                self.playlist_manager.save_current_playlist(current_playlist)
                
                # 播放选中的歌曲
                selected_song = songs[index]
                if self.play_song_callback:
                    await self.play_song_callback(selected_song["info"])
                
                logger.info(f"已播放索引 {index} 的歌曲: {selected_song['info'].get('title', '未知')}")
                return True
            else:
                logger.warning(f"歌曲索引 {index} 超出范围（总共 {len(songs)} 首歌曲）")
                return False
                
        except Exception as e:
            logger.error(f"根据索引播放歌曲失败: {e}")
            return False
