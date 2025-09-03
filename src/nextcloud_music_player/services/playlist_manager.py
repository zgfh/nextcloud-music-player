"""
播放列表管理服务 - 专门处理播放列表的创建、加载、保存和管理
将播放列表逻辑从播放视图中分离出来，提供独立的管理功能
"""

import os
import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class PlaylistManager:
    """播放列表管理器 - 负责播放列表的生命周期管理"""
    
    def __init__(self, config_manager, music_service=None):
        """
        初始化播放列表管理器
        
        Args:
            config_manager: 配置管理器实例
            music_service: 音乐服务实例（用于获取歌曲信息）
        """
        self.config_manager = config_manager
        self.music_service = music_service
        
        # 缓存当前播放列表数据
        self._current_playlist_cache = None
        self._playlists_cache = None
        
    def load_playlists_data(self) -> Dict[str, Any]:
        """加载所有播放列表数据（带缓存）"""
        if self._playlists_cache is None:
            self._playlists_cache = self.config_manager.load_playlists()
        return self._playlists_cache
    
    def save_playlists_data(self, playlists_data: Dict[str, Any]):
        """保存播放列表数据并更新缓存"""
        self.config_manager.save_playlists(playlists_data)
        self._playlists_cache = playlists_data
        
    def invalidate_cache(self):
        """清除缓存，强制重新加载"""
        self._playlists_cache = None
        self._current_playlist_cache = None
        
    def get_current_playlist_id(self) -> Optional[int]:
        """获取当前播放列表ID"""
        playlists_data = self.load_playlists_data()
        return playlists_data.get("current_playlist_id")
    
    def set_current_playlist_id(self, playlist_id: int):
        """设置当前播放列表ID"""
        playlists_data = self.load_playlists_data()
        playlists_data["current_playlist_id"] = playlist_id
        self.save_playlists_data(playlists_data)
        self._current_playlist_cache = None  # 清除当前播放列表缓存
        
    def get_current_playlist(self) -> Optional[Dict[str, Any]]:
        """获取当前播放列表（带缓存）"""
        if self._current_playlist_cache is not None:
            return self._current_playlist_cache
            
        current_id = self.get_current_playlist_id()
        if current_id is not None:
            self._current_playlist_cache = self.get_playlist_by_id(current_id)
            return self._current_playlist_cache
        
        return None
    
    def get_playlist_by_id(self, playlist_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取播放列表"""
        playlists_data = self.load_playlists_data()
        for playlist in playlists_data.get("playlists", []):
            if playlist.get("id") == playlist_id:
                return playlist
        return None
    
    def create_default_playlist_if_needed(self) -> Dict[str, Any]:
        """如果没有当前播放列表，创建默认播放列表"""
        current_playlist = self.get_current_playlist()
        
        if current_playlist is None:
            # 尝试从现有播放列表中选择第一个
            playlists_data = self.load_playlists_data()
            existing_playlists = playlists_data.get("playlists", [])
            
            if existing_playlists:
                # 使用第一个播放列表作为当前播放列表
                first_playlist = existing_playlists[0]
                self.set_current_playlist_id(first_playlist["id"])
                current_playlist = first_playlist
                logger.info(f"使用现有播放列表作为当前播放列表: {first_playlist['name']}")
            else:
                # 创建新的默认播放列表
                current_playlist = self.create_empty_playlist("默认播放列表")
                logger.info("创建新的默认播放列表")
        
        return current_playlist
    
    def create_empty_playlist(self, name: str = "新播放列表", folder_path: str = "") -> Dict[str, Any]:
        """创建空的播放列表"""
        playlists_data = self.load_playlists_data()
        
        # 生成新ID
        next_id = playlists_data.get("next_id", 1)
        
        # 创建新播放列表
        new_playlist = {
            "id": next_id,
            "name": name,
            "songs": [],
            "folder_path": folder_path,
            "created_at": datetime.now().isoformat(),
            "last_played": None,
            "play_count": 0,
            "current_index": 0
        }
        
        # 添加到播放列表数组
        playlists_data.setdefault("playlists", []).insert(0, new_playlist)
        playlists_data["next_id"] = next_id + 1
        playlists_data["current_playlist_id"] = next_id
        
        # 保存数据
        self.save_playlists_data(playlists_data)
        
        # 更新缓存
        self._current_playlist_cache = new_playlist
        
        logger.info(f"创建新播放列表: {name} (ID: {next_id})")
        return new_playlist
    
    def create_playlist_from_folder(self, folder_path: str, name: str = None) -> Dict[str, Any]:
        """从文件夹创建播放列表"""
        if not name:
            name = f"来自 {os.path.basename(folder_path)} 的播放列表"
        
        # 获取文件夹中的音乐文件
        songs = []
        if self.music_service:
            try:
                # 使用音乐服务获取文件列表
                music_list = self.music_service.load_music_list()
                
                # 筛选属于该文件夹的歌曲
                for song_info in music_list:
                    song_folder = song_info.get('folder_path', '')
                    if song_folder == folder_path:
                        song_entry = {
                            "name": song_info.get('name', ''),
                            "info": song_info,
                            "state": {
                                "play_count": 0,
                                "is_favorite": False,
                                "last_played": None
                            }
                        }
                        songs.append(song_entry)
                        
            except Exception as e:
                logger.error(f"从音乐服务获取文件列表失败: {e}")
        
        # 创建播放列表
        playlists_data = self.load_playlists_data()
        next_id = playlists_data.get("next_id", 1)
        
        new_playlist = {
            "id": next_id,
            "name": name,
            "songs": songs,
            "folder_path": folder_path,
            "created_at": datetime.now().isoformat(),
            "last_played": None,
            "play_count": 0,
            "current_index": 0
        }
        
        # 添加到播放列表数组
        playlists_data.setdefault("playlists", []).insert(0, new_playlist)
        playlists_data["next_id"] = next_id + 1
        playlists_data["current_playlist_id"] = next_id
        
        # 保存数据
        self.save_playlists_data(playlists_data)
        
        # 更新缓存
        self._current_playlist_cache = new_playlist
        
        logger.info(f"从文件夹创建播放列表: {name} (ID: {next_id}, 歌曲数: {len(songs)})")
        return new_playlist
    
    def add_song_to_current_playlist(self, song_info: Dict[str, Any]) -> bool:
        """添加歌曲到当前播放列表"""
        try:
            current_playlist = self.get_current_playlist()
            if not current_playlist:
                current_playlist = self.create_default_playlist_if_needed()
            
            # 检查歌曲是否已存在
            song_name = song_info.get('name', '')
            existing_songs = current_playlist.get('songs', [])
            
            for existing_song in existing_songs:
                if existing_song.get('name') == song_name:
                    logger.info(f"歌曲已存在于播放列表中: {song_name}")
                    return False
            
            # 创建歌曲条目
            song_entry = {
                "name": song_name,
                "info": song_info,
                "state": {
                    "play_count": 0,
                    "is_favorite": False,
                    "last_played": None
                }
            }
            
            # 添加到播放列表
            current_playlist.setdefault('songs', []).append(song_entry)
            
            # 保存播放列表
            self.save_current_playlist(current_playlist)
            
            logger.info(f"添加歌曲到播放列表: {song_name}")
            return True
            
        except Exception as e:
            logger.error(f"添加歌曲到播放列表失败: {e}")
            return False

    def add_songs_to_current_playlist_batch(self, song_infos: List[Dict[str, Any]]) -> int:
        """批量添加歌曲到当前播放列表，返回实际添加的歌曲数量"""
        try:
            current_playlist = self.get_current_playlist()
            if not current_playlist:
                current_playlist = self.create_default_playlist_if_needed()
            
            existing_songs = current_playlist.get('songs', [])
            existing_names = {song.get('name', '') for song in existing_songs}
            
            added_count = 0
            
            # 批量添加歌曲
            for song_info in song_infos:
                song_name = song_info.get('name', '')
                
                # 检查歌曲是否已存在
                if song_name in existing_names:
                    logger.debug(f"歌曲已存在于播放列表中，跳过: {song_name}")
                    continue
                
                # 创建歌曲条目
                song_entry = {
                    "name": song_name,
                    "info": song_info,
                    "state": {
                        "play_count": 0,
                        "is_favorite": False,
                        "last_played": None
                    }
                }
                
                # 添加到播放列表
                current_playlist.setdefault('songs', []).append(song_entry)
                existing_names.add(song_name)
                added_count += 1
            
            # 只保存一次播放列表
            if added_count > 0:
                self.save_current_playlist(current_playlist)
                logger.info(f"批量添加 {added_count} 首歌曲到播放列表")
            
            return added_count
            
        except Exception as e:
            logger.error(f"批量添加歌曲到播放列表失败: {e}")
            return 0
    
    def remove_song_from_current_playlist(self, index: int) -> bool:
        """从当前播放列表移除歌曲"""
        try:
            current_playlist = self.get_current_playlist()
            if not current_playlist:
                return False
            
            songs = current_playlist.get('songs', [])
            if 0 <= index < len(songs):
                removed_song = songs.pop(index)
                
                # 调整当前播放索引
                current_index = current_playlist.get('current_index', 0)
                if index <= current_index and current_index > 0:
                    current_playlist['current_index'] = current_index - 1
                elif index == current_index and index >= len(songs):
                    current_playlist['current_index'] = max(0, len(songs) - 1)
                
                # 保存播放列表
                self.save_current_playlist(current_playlist)
                
                logger.info(f"从播放列表移除歌曲: {removed_song.get('name', '未知')}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"移除歌曲失败: {e}")
            return False
    
    def clear_current_playlist(self) -> bool:
        """清空当前播放列表"""
        try:
            current_playlist = self.get_current_playlist()
            if not current_playlist:
                return False
            
            current_playlist['songs'] = []
            current_playlist['current_index'] = 0
            
            # 保存播放列表
            self.save_current_playlist(current_playlist)
            
            logger.info("已清空当前播放列表")
            return True
            
        except Exception as e:
            logger.error(f"清空播放列表失败: {e}")
            return False
    
    def save_current_playlist(self, playlist_data: Dict[str, Any] = None):
        """保存当前播放列表"""
        try:
            if playlist_data is None:
                playlist_data = self._current_playlist_cache
            
            if not playlist_data:
                return
            
            # 更新播放列表数据
            playlists_data = self.load_playlists_data()
            playlist_id = playlist_data.get('id')
            
            # 查找并更新对应的播放列表
            for i, playlist in enumerate(playlists_data.get("playlists", [])):
                if playlist.get("id") == playlist_id:
                    playlists_data["playlists"][i] = playlist_data
                    break
            
            # 保存数据
            self.save_playlists_data(playlists_data)
            
            # 更新缓存
            self._current_playlist_cache = playlist_data
            
        except Exception as e:
            logger.error(f"保存当前播放列表失败: {e}")
    
    def get_all_playlists(self) -> List[Dict[str, Any]]:
        """获取所有播放列表"""
        playlists_data = self.load_playlists_data()
        return playlists_data.get("playlists", [])
    
    def delete_playlist(self, playlist_id: int) -> bool:
        """删除播放列表"""
        try:
            playlists_data = self.load_playlists_data()
            playlists = playlists_data.get("playlists", [])
            
            # 查找并删除播放列表
            for i, playlist in enumerate(playlists):
                if playlist.get("id") == playlist_id:
                    deleted_playlist = playlists.pop(i)
                    
                    # 如果删除的是当前播放列表，选择新的当前播放列表
                    if playlists_data.get("current_playlist_id") == playlist_id:
                        if playlists:
                            playlists_data["current_playlist_id"] = playlists[0]["id"]
                        else:
                            playlists_data["current_playlist_id"] = None
                        self._current_playlist_cache = None
                    
                    # 保存数据
                    self.save_playlists_data(playlists_data)
                    
                    logger.info(f"删除播放列表: {deleted_playlist.get('name', '未知')}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"删除播放列表失败: {e}")
            return False
    
    def update_song_state(self, song_name: str, state_updates: Dict[str, Any]) -> bool:
        """更新歌曲状态"""
        try:
            current_playlist = self.get_current_playlist()
            if not current_playlist:
                return False
            
            songs = current_playlist.get('songs', [])
            for song_entry in songs:
                if song_entry.get('name') == song_name:
                    song_state = song_entry.setdefault('state', {})
                    song_state.update(state_updates)
                    
                    # 保存播放列表
                    self.save_current_playlist(current_playlist)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"更新歌曲状态失败: {e}")
            return False
    
    def get_playlist_stats(self) -> Dict[str, Any]:
        """获取播放列表统计信息"""
        try:
            current_playlist = self.get_current_playlist()
            if not current_playlist:
                return {
                    "total_songs": 0,
                    "current_index": 0,
                    "playlist_name": "无播放列表"
                }
            
            songs = current_playlist.get('songs', [])
            current_index = current_playlist.get('current_index', 0)
            
            return {
                "total_songs": len(songs),
                "current_index": current_index + 1 if songs else 0,
                "playlist_name": current_playlist.get('name', '未知播放列表'),
                "playlist_id": current_playlist.get('id'),
                "created_at": current_playlist.get('created_at'),
                "folder_path": current_playlist.get('folder_path', '')
            }
            
        except Exception as e:
            logger.error(f"获取播放列表统计失败: {e}")
            return {
                "total_songs": 0,
                "current_index": 0,
                "playlist_name": "错误"
            }
