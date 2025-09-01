"""
播放服务层 - 封装音乐播放控制逻辑
提供给视图层使用的抽象接口，解耦视图与应用核心逻辑
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime

try:
    import pygame
except ImportError:
    pygame = None

from ..platform_audio import create_audio_player, is_ios, is_mobile

logger = logging.getLogger(__name__)

class PlaybackService:
    """播放服务 - 处理音乐播放控制、播放列表管理等业务逻辑"""
    
    def __init__(self, config_manager, music_service, play_music_callback=None, add_background_task_callback=None):
        """
        初始化播放服务
        
        Args:
            config_manager: 配置管理器实例
            music_service: 音乐服务实例（用于获取歌曲信息、下载等操作）
            play_music_callback: 播放音乐的回调函数（可选，为兼容性保留）
            add_background_task_callback: 添加后台任务的回调函数
        """
        self.config_manager = config_manager
        self.music_service = music_service
        self._play_music_callback = play_music_callback
        self._add_background_task_callback = add_background_task_callback
        
        # 创建平台特定的音频播放器
        self.audio_player = create_audio_player()
        logger.info(f"使用音频播放器: {type(self.audio_player).__name__}")
        
        # 向后兼容：初始化pygame音频系统（如果需要）
        if not is_mobile():
            self._init_audio_system()
        
        # 当前播放状态
        self.current_song = None
        self.current_playlist_data = None
        self.current_song_info = None
        self.current_song_state = {
            'is_playing': False,
            'is_paused': False,
            'position': 0,
            'duration': 0,
            'play_count': 0,
            'last_played': None
        }
        
        # 播放状态回调
        self._pause_music_callback = None
        self._stop_music_callback = None
        self._get_play_mode_callback = None
        self._get_is_playing_callback = None
        self._set_volume_callback = None
        self._seek_to_position_callback = None
        self._get_duration_callback = None
        self._set_play_mode_callback = None
        
    def _init_audio_system(self):
        """初始化音频系统"""
        try:
            if pygame is None:
                logger.warning("pygame 未安装，音频播放功能不可用")
                return
                
            # 初始化pygame mixer
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                logger.info("pygame音频系统初始化成功")
            else:
                logger.info("pygame音频系统已经初始化")
        except Exception as e:
            logger.error(f"初始化音频系统失败: {e}")
            # 尝试重新初始化
            try:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                logger.info("重新初始化pygame音频系统成功")
            except Exception as retry_error:
                logger.error(f"重新初始化音频系统也失败: {retry_error}")
            
    def _ensure_audio_system(self) -> bool:
        """确保音频系统可用"""
        # 优先使用新的平台音频播放器
        if self.audio_player:
            return True
            
        # 向后兼容：检查pygame（仅桌面平台）
        if is_mobile():
            logger.error("移动平台上pygame不可用")
            return False
            
        if pygame is None:
            logger.error("pygame 未安装，无法播放音频")
            return False
            
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                logger.info("重新初始化pygame音频系统")
        except Exception as e:
            logger.error(f"确保音频系统可用失败: {e}")
            return False
                
        return True
        
    def update_music_service(self, music_service):
        """更新音乐服务实例"""
        self.music_service = music_service
        logger.info("播放服务: 音乐服务已更新")
        
    def set_playback_callbacks(self, pause_callback, stop_callback, get_play_mode_callback, get_is_playing_callback,
                             set_volume_callback=None, seek_to_position_callback=None, get_duration_callback=None,
                             set_play_mode_callback=None):
        """设置播放控制回调函数"""
        self._pause_music_callback = pause_callback
        self._stop_music_callback = stop_callback
        self._get_play_mode_callback = get_play_mode_callback
        self._get_is_playing_callback = get_is_playing_callback
        self._set_volume_callback = set_volume_callback
        self._seek_to_position_callback = seek_to_position_callback
        self._get_duration_callback = get_duration_callback
        self._set_play_mode_callback = set_play_mode_callback
        
    
    def load_playlists(self) -> Dict[str, Any]:
        """加载播放列表数据"""
        return self.config_manager.load_playlists()
    
    def save_playlists(self, playlists_data: Dict[str, Any]):
        """保存播放列表数据"""
        self.config_manager.save_playlists(playlists_data)
    
    def get_playlist_by_id(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取播放列表"""
        return self.config_manager.get_playlist_by_id(playlist_id)
    
    def get_song_info(self, song_name: str) -> Optional[Dict[str, Any]]:
        """获取歌曲信息"""
        if self.music_service:
            return self.music_service.get_song_info(song_name)
        return None
    
    def get_volume(self) -> int:
        """获取音量设置"""
        return self.config_manager.get("player.volume", 70)
    
    def set_volume(self, volume: int):
        """设置音量"""
        self.config_manager.set("player.volume", volume)
        self.config_manager.save_config()
    
    def set_current_song(self, song_path: str):
        """设置当前播放歌曲"""
        self.current_song = song_path
    
    def get_current_song(self) -> Optional[str]:
        """获取当前播放歌曲路径"""
        return self.current_song
    
    def get_current_song_name(self) -> Optional[str]:
        """获取当前播放歌曲名称"""
        if self.current_song:
            return os.path.basename(self.current_song)
        return None
    
    async def play_music(self):
        """播放音乐"""
        try:
            if not self.current_song or not os.path.exists(self.current_song):
                logger.error(f"当前歌曲文件不存在: {self.current_song}")
                return
            
            # 使用新的平台音频播放器
            if self.audio_player:
                # 如果当前暂停状态，恢复播放
                if self.current_song_state['is_paused']:
                    success = self.audio_player.play()
                    if success:
                        self.current_song_state['is_paused'] = False
                        self.current_song_state['is_playing'] = True
                        logger.info("恢复播放音乐")
                    return
                
                logger.info(f"准备播放音乐: {self.current_song}")
                
                # 加载并播放新歌曲
                if self.audio_player.load(self.current_song):
                    if self.audio_player.play():
                        # 更新播放状态
                        self.current_song_state['is_playing'] = True
                        self.current_song_state['is_paused'] = False
                        self.current_song_state['last_played'] = datetime.now().isoformat()
                        
                        # 设置音量
                        volume = self.get_volume() / 100.0  # 转换为0.0-1.0范围
                        self.audio_player.set_volume(volume)
                        
                        logger.info(f"开始播放: {os.path.basename(self.current_song)}")
                        return
                    else:
                        logger.error("音频播放器播放失败")
                else:
                    logger.error("音频播放器加载文件失败")
            
            # 备用方案：使用pygame（向后兼容）
            if not self._ensure_audio_system():
                logger.error("音频系统不可用")
                return
                
            # 如果当前暂停状态，恢复播放
            if self.current_song_state['is_paused']:
                pygame.mixer.music.unpause()
                self.current_song_state['is_paused'] = False
                self.current_song_state['is_playing'] = True
                logger.info("恢复播放音乐")
                return
            
            logger.info(f"准备播放音乐: {self.current_song}")
            # 加载并播放新歌曲
            pygame.mixer.music.load(self.current_song)
            pygame.mixer.music.play()
            
            # 更新播放状态
            self.current_song_state['is_playing'] = True
            self.current_song_state['is_paused'] = False
            self.current_song_state['last_played'] = datetime.now().isoformat()
            
            logger.info(f"开始播放: {os.path.basename(self.current_song)}")
            
        except Exception as e:
            logger.error(f"播放音乐失败: {e}")
            # 如果内置播放失败，尝试使用回调
            if self._play_music_callback:
                try:
                    await self._play_music_callback()
                except Exception as callback_error:
                    logger.error(f"回调播放也失败: {callback_error}")
    
    def add_background_task(self, task):
        """添加后台任务"""
        if self._add_background_task_callback:
            self._add_background_task_callback(task)
    
    def update_playlist_current_song(self, song_name: str):
        """更新播放列表中的当前歌曲状态"""
        try:
            playlists_data = self.load_playlists()
            current_playlist_id = playlists_data.get('current_playlist')
            
            if current_playlist_id:
                for playlist in playlists_data.get('playlists', []):
                    if playlist.get('id') == current_playlist_id:
                        # 更新当前歌曲
                        playlist['current_song'] = song_name
                        playlist['last_played'] = datetime.now().isoformat()
                        
                        # 更新播放统计
                        for song in playlist.get('songs', []):
                            if song.get('name') == song_name:
                                song['play_count'] = song.get('play_count', 0) + 1
                                song['last_played'] = datetime.now().isoformat()
                                break
                        
                        break
                
                self.save_playlists(playlists_data)
                logger.info(f"已更新播放列表中的当前歌曲: {song_name}")
        except Exception as e:
            logger.error(f"更新播放列表当前歌曲失败: {e}")
    
    def is_nextcloud_connected(self) -> bool:
        """检查NextCloud是否连接"""
        return self.music_service and self.music_service.has_nextcloud_client()
    
    async def download_and_play_song(self, song_name: str, remote_path: str) -> bool:
        """下载并播放歌曲"""
        try:
            if not self.is_nextcloud_connected():
                logger.error("NextCloud客户端未连接")
                return False
            
            logger.info(f"正在下载歌曲: {song_name}")
            success = await self.music_service.download_file(remote_path, song_name)
            
            if success:
                # 获取更新后的歌曲信息
                updated_info = self.music_service.get_song_info(song_name)
                
                # 尝试多种方法获取本地文件路径
                local_path = None
                
                # 方法1: 从歌曲信息中获取filepath
                if updated_info and updated_info.get('filepath'):
                    potential_path = updated_info['filepath']
                    if os.path.exists(potential_path):
                        local_path = potential_path
                        logger.info(f"使用歌曲信息中的路径: {local_path}")
    
                if local_path:
                    # 设置为当前歌曲并播放
                    self.set_current_song(local_path)
                    await self.play_music()
                    logger.info(f"歌曲下载并播放成功: {song_name}")
                    return True
                else:
                    logger.error(f"找不到下载的歌曲文件: {song_name}")
                    return False
            else:
                logger.error(f"歌曲下载失败: {song_name}")
                return False
                
        except Exception as e:
            logger.error(f"下载并播放歌曲失败: {e}")
            return False
    
    async def play_song_from_playlist(self, song_name: str) -> bool:
        """从播放列表播放歌曲"""
        try:
            logger.info(f"准备播放歌曲: {song_name}")
            
            # 获取歌曲信息
            song_info = self.get_song_info(song_name)
            if not song_info:
                logger.error(f"未找到歌曲信息: {song_name}")
                return False
            
            # 检查是否已下载
            if song_info.get('downloaded', False):
                # 本地播放
                filepath = song_info.get('local_path', '')
                if os.path.exists(filepath):
                    self.set_current_song(filepath)
                    await self.play_music()
                    logger.info(f"本地播放歌曲: {song_name}")
                    return True
                else:
                    logger.warning(f"本地文件不存在: {filepath}")
            
            # 在线播放 - 需要下载
            remote_path = song_info.get('remote_path', '')
            if remote_path:
                return await self.download_and_play_song(song_name, remote_path)
            else:
                logger.error(f"歌曲缺少远程路径信息: {song_name}")
                return False
                
        except Exception as e:
            logger.error(f"播放歌曲失败: {e}")
            return False
    
    def load_current_playlist(self) -> Optional[Dict[str, Any]]:
        """加载当前播放列表"""
        try:
            playlists_data = self.load_playlists()
            current_playlist_id = playlists_data.get('current_playlist')
            
            if current_playlist_id:
                self.current_playlist_data = self.get_playlist_by_id(current_playlist_id)
                return self.current_playlist_data
            return None
        except Exception as e:
            logger.error(f"加载当前播放列表失败: {e}")
            return None
    
    def get_current_playlist_song_info(self, song_name: str) -> Optional[Dict[str, Any]]:
        """获取当前播放列表中歌曲的详细信息"""
        try:
            # 同时从音乐服务和播放列表获取信息
            song_info = {}
            
            # 从音乐服务获取基础信息
            if self.music_service:
                library_info = self.music_service.get_song_info(song_name)
                if library_info:
                    song_info.update(library_info)
            
            # 从当前播放列表获取播放统计等信息
            if self.current_playlist_data:
                for song in self.current_playlist_data.get('songs', []):
                    if song.get('name') == song_name:
                        song_info.update(song)
                        break
            
            return song_info if song_info else None
            
        except Exception as e:
            logger.error(f"获取播放列表歌曲信息失败: {e}")
            return None
    
    def sync_current_song_with_app(self) -> Optional[str]:
        """与应用当前歌曲状态同步"""
        if self.current_song:
            return os.path.basename(self.current_song)
        return None
    
    async def pause_music(self):
        """暂停音乐"""
        try:
            # 使用新的平台音频播放器
            if self.audio_player and self.current_song_state['is_playing'] and not self.current_song_state['is_paused']:
                if self.audio_player.pause():
                    self.current_song_state['is_paused'] = True
                    self.current_song_state['is_playing'] = False
                    logger.info("音乐已暂停")
                    return
                else:
                    logger.error("音频播放器暂停失败")
            
            # 备用方案：使用pygame（向后兼容）
            if not self._ensure_audio_system():
                return
                
            if self.current_song_state['is_playing'] and not self.current_song_state['is_paused']:
                pygame.mixer.music.pause()
                self.current_song_state['is_paused'] = True
                self.current_song_state['is_playing'] = False
                logger.info("音乐已暂停")
        except Exception as e:
            logger.error(f"暂停音乐失败: {e}")
            # 如果内置暂停失败，尝试使用回调
            if self._pause_music_callback:
                try:
                    await self._pause_music_callback()
                except Exception as callback_error:
                    logger.error(f"回调暂停也失败: {callback_error}")
    
    async def stop_music(self):
        """停止音乐"""
        try:
            # 使用新的平台音频播放器
            if self.audio_player and (self.current_song_state['is_playing'] or self.current_song_state['is_paused']):
                if self.audio_player.stop():
                    self.current_song_state['is_playing'] = False
                    self.current_song_state['is_paused'] = False
                    self.current_song_state['position'] = 0
                    logger.info("音乐已停止")
                    return
                else:
                    logger.error("音频播放器停止失败")
            
            # 备用方案：使用pygame（向后兼容）
            if not self._ensure_audio_system():
                return
                
            if self.current_song_state['is_playing'] or self.current_song_state['is_paused']:
                pygame.mixer.music.stop()
                self.current_song_state['is_playing'] = False
                self.current_song_state['is_paused'] = False
                self.current_song_state['position'] = 0
                logger.info("音乐已停止")
        except Exception as e:
            logger.error(f"停止音乐失败: {e}")
            # 如果内置停止失败，尝试使用回调
            if self._stop_music_callback:
                try:
                    await self._stop_music_callback()
                except Exception as callback_error:
                    logger.error(f"回调停止也失败: {callback_error}")
    
    def get_play_mode(self):
        """获取播放模式"""
        if self._get_play_mode_callback:
            return self._get_play_mode_callback()
        return None
    
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        try:
            # 优先使用新的平台音频播放器
            if self.audio_player:
                is_audio_playing = self.audio_player.is_playing()
                # 同步内部状态
                if is_audio_playing != self.current_song_state['is_playing']:
                    self.current_song_state['is_playing'] = is_audio_playing
                    if is_audio_playing:
                        self.current_song_state['is_paused'] = False
                return is_audio_playing
            
            # 备用方案：使用内部状态和pygame验证
            if self.current_song_state['is_playing']:
                # 如果pygame可用，验证实际播放状态
                if pygame and pygame.mixer.get_init():
                    pygame_playing = pygame.mixer.music.get_busy()
                    if not pygame_playing and not self.current_song_state['is_paused']:
                        # pygame显示未播放且未暂停，更新状态
                        self.current_song_state['is_playing'] = False
                        return False
                return True
                
            # 如果内部状态显示未播放，检查pygame状态作为备用
            if pygame and pygame.mixer.get_init():
                return pygame.mixer.music.get_busy()
                
            return False
        except Exception as e:
            logger.error(f"检查播放状态失败: {e}")
            # 如果检查失败，尝试使用回调
            if self._get_is_playing_callback:
                try:
                    return self._get_is_playing_callback()
                except Exception as callback_error:
                    logger.error(f"回调检查播放状态也失败: {callback_error}")
            return False
    
    def set_audio_volume(self, volume: float):
        """设置音频音量（0.0-1.0）"""
        try:
            # 使用新的平台音频播放器
            if self.audio_player:
                success = self.audio_player.set_volume(volume)
                if success:
                    logger.info(f"音量设置成功: {volume}")
                    return
                else:
                    logger.warning("音频播放器设置音量失败")
            
            # 备用方案：使用回调
            if self._set_volume_callback:
                self._set_volume_callback(volume)
            else:
                logger.warning("没有可用的音量设置方法")
                
        except Exception as e:
            logger.error(f"设置音量失败: {e}")
    
    def seek_to_position(self, position: float):
        """跳转到指定位置"""
        try:
            # 优先使用音频播放器的跳转功能
            if self.audio_player:
                success = self.audio_player.seek(position)
                if success:
                    logger.info(f"跳转到位置: {position:.2f}秒")
                    return True
                else:
                    logger.warning("音频播放器不支持跳转功能")
            
            # 备用：使用回调函数
            if self._seek_to_position_callback:
                self._seek_to_position_callback(position)
                return True
                
            logger.warning("无法跳转到指定位置：音频播放器和回调函数都不可用")
            return False
        except Exception as e:
            logger.error(f"跳转到指定位置失败: {e}")
            return False
    
    def get_duration(self) -> float:
        """获取音频总时长"""
        try:
            # 优先使用音频播放器的获取时长功能
            if self.audio_player:
                duration = self.audio_player.get_duration()
                if duration >= 0:  # 如果返回有效值
                    return duration
            
            # 备用：使用回调函数
            if self._get_duration_callback:
                return self._get_duration_callback()
                
            # 返回存储的时长
            return self.current_song_state.get('duration', 0.0)
        except Exception as e:
            logger.error(f"获取音频时长失败: {e}")
            return 0.0
    
    def set_play_mode(self, play_mode):
        """设置播放模式"""
        if self._set_play_mode_callback:
            self._set_play_mode_callback(play_mode)
    
    def set_play_mode_by_string(self, mode_string: str):
        """通过字符串设置播放模式"""
        # 导入播放模式枚举
        try:
            from ..views.playback_view import PlayMode
            
            # 模式映射
            mode_map = {
                "normal": PlayMode.NORMAL,
                "repeat_one": PlayMode.REPEAT_ONE,
                "repeat_all": PlayMode.REPEAT_ALL,
                "shuffle": PlayMode.SHUFFLE
            }
            
            if mode_string in mode_map:
                self.set_play_mode(mode_map[mode_string])
                
                # 保存播放模式到配置
                self.config_manager.set("player.play_mode", mode_string)
                self.config_manager.save_config()
                
                return True
            return False
        except Exception as e:
            logger.error(f"设置播放模式失败: {e}")
            return False
    
    def get_playback_state(self) -> Dict[str, Any]:
        """获取实时播放状态"""
        try:
            # 从音频播放器获取实时状态
            if self.audio_player:
                position = self.audio_player.get_position()
                duration = self.audio_player.get_duration()
                is_playing = self.audio_player.is_playing()
                
                # 如果返回的值为负数（表示不支持），使用存储的状态
                if position < 0:
                    position = self.current_song_state.get('position', 0)
                if duration < 0:
                    duration = self.current_song_state.get('duration', 0)
                
                # 更新存储的状态
                self.current_song_state['position'] = position
                self.current_song_state['duration'] = duration
                self.current_song_state['is_playing'] = is_playing
                
                return {
                    'position': position,
                    'duration': duration,
                    'is_playing': is_playing,
                    'is_paused': self.current_song_state.get('is_paused', False),
                    'current_song': self.current_song,
                    'play_count': self.current_song_state.get('play_count', 0),
                    'last_played': self.current_song_state.get('last_played', None)
                }
            else:
                # 返回存储的状态
                return dict(self.current_song_state)
                
        except Exception as e:
            logger.error(f"获取播放状态失败: {e}")
            return dict(self.current_song_state)
