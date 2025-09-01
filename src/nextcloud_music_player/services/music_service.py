"""
音乐服务层 - 封装音乐播放、列表管理等业务逻辑
提供给视图层使用的抽象接口，解耦视图与应用核心逻辑
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class MusicService:
    """音乐服务 - 处理音乐文件、播放列表、同步等业务逻辑"""
    
    def __init__(self, music_library, nextcloud_client, config_manager):
        """
        初始化音乐服务
        
        Args:
            music_library: 音乐库实例
            nextcloud_client: NextCloud客户端实例（可以为None）
            config_manager: 配置管理器实例
        """
        self.music_library = music_library
        self.nextcloud_client = nextcloud_client
        self.config_manager = config_manager
        
        # 回调函数
        self._playlist_change_callback: Optional[Callable[[List[str], int], None]] = None
        self._sync_folder_change_callback: Optional[Callable[[str], None]] = None
    
    def set_playlist_change_callback(self, callback: Callable[[List[str], int], None]):
        """设置播放列表变化的回调函数"""
        self._playlist_change_callback = callback
    
    def set_sync_folder_change_callback(self, callback: Callable[[str], None]):
        """设置同步文件夹变化的回调函数"""
        self._sync_folder_change_callback = callback
    
    def update_nextcloud_client(self, nextcloud_client):
        """更新NextCloud客户端实例"""
        self.nextcloud_client = nextcloud_client
        logger.info("NextCloud客户端已更新")
    
    def get_all_songs(self) -> List[Dict[str, Any]]:
        """获取所有歌曲列表"""
        try:
            songs_dict = self.music_library.get_all_songs()
            songs_list = []
            
            for song_name, song_info in songs_dict.items():
                # 确保每个歌曲信息都包含名称
                song_data = song_info.copy() if isinstance(song_info, dict) else {}
                song_data['name'] = song_name
                songs_list.append(song_data)
                
            return songs_list
        except Exception as e:
            logger.error(f"获取歌曲列表失败: {e}")
            return []
    
    def is_file_cached(self, filename: str) -> bool:
        """检查文件是否已缓存"""
        try:
            return self.music_library.is_file_cached(filename)
        except Exception as e:
            logger.error(f"检查文件缓存状态失败: {e}")
            return False
    
    async def sync_music_files(self, sync_folder: str = "") -> List[Dict[str, Any]]:
        """
        同步音乐文件
        
        Args:
            sync_folder: 指定的同步文件夹路径
            
        Returns:
            同步后的音乐文件列表
        """
        if not self.nextcloud_client:
            raise Exception("NextCloud客户端未连接")
        
        try:
            # 如果没有指定文件夹，使用默认配置
            if not sync_folder.strip():
                sync_folder = self.config_manager.get("connection.default_sync_folder", "")
            
            logger.info(f"开始同步音乐文件，文件夹: {sync_folder}")
            
            # 获取远程文件列表
            music_files = await self.nextcloud_client.list_music_files(sync_folder)
            
            # 通知同步文件夹变化
            if self._sync_folder_change_callback:
                self._sync_folder_change_callback(sync_folder)
            
            # 更新音乐库
            if music_files:
                for file_info in music_files:
                    self.music_library.add_remote_song(
                        file_info['name'],
                        file_info.get('path', ''),
                        file_info.get('size', 0),
                        file_info.get('modified', ''),
                        file_info.get('sync_folder', sync_folder)
                    )
                
                # 保存同步文件夹信息
                self.music_library.sync_folder = sync_folder
            
            logger.info(f"同步完成，共获得 {len(music_files)} 个音乐文件")
            return music_files
            
        except Exception as e:
            logger.error(f"同步音乐文件失败: {e}")
            raise
    
    def set_playlist_from_files(self, music_files: List[Dict[str, Any]], start_index: int = 0):
        """
        从音乐文件列表设置播放列表
        
        Args:
            music_files: 音乐文件列表
            start_index: 开始播放的索引
        """
        try:
            # 提取文件名列表
            playlist = [file_info['name'] for file_info in music_files]
            
            # 通知播放列表变化
            if self._playlist_change_callback:
                self._playlist_change_callback(playlist, start_index)
                
            logger.info(f"设置播放列表，共 {len(playlist)} 首歌曲，开始索引: {start_index}")
            
        except Exception as e:
            logger.error(f"设置播放列表失败: {e}")
            raise
    
    def remove_song(self, song_name: str):
        """删除歌曲"""
        try:
            if self.music_library.has_song(song_name):
                self.music_library.remove_song(song_name)
                logger.info(f"删除歌曲: {song_name}")
            else:
                logger.warning(f"歌曲不存在: {song_name}")
        except Exception as e:
            logger.error(f"删除歌曲失败: {e}")
            raise
    
    def get_song_info(self, song_name: str) -> Dict[str, Any]:
        """获取歌曲信息"""
        try:
            return self.music_library.get_song_info(song_name)
        except Exception as e:
            logger.error(f"获取歌曲信息失败: {e}")
            return {}
    
    def update_song_info(self, song_name: str, updated_info: Dict[str, Any]):
        """更新歌曲信息"""
        try:
            self.music_library.songs[song_name] = updated_info
            self.music_library.save_music_list()
            logger.info(f"更新歌曲信息: {song_name}")
        except Exception as e:
            logger.error(f"更新歌曲信息失败: {e}")
            raise
    
    def search_songs(self, query: str) -> List[Dict[str, Any]]:
        """搜索歌曲"""
        try:
            if query.strip():
                # search_songs 返回的是歌曲名称列表
                search_results = self.music_library.search_songs(query)
                all_songs_dict = self.music_library.get_all_songs()
                
                result_list = []
                for song_name in search_results:
                    if song_name in all_songs_dict:
                        song_data = all_songs_dict[song_name].copy()
                        song_data['name'] = song_name
                        result_list.append(song_data)
                
                return result_list
            else:
                return self.get_all_songs()
        except Exception as e:
            logger.error(f"搜索歌曲失败: {e}")
            return []
    
    def has_song(self, song_name: str) -> bool:
        """检查是否存在指定歌曲"""
        try:
            return self.music_library.has_song(song_name)
        except Exception as e:
            logger.error(f"检查歌曲存在性失败: {e}")
            return False
    
    def get_local_file_path(self, song_name: str) -> str:
        """获取歌曲的本地文件路径"""
        try:
            return self.music_library.get_local_file_path(song_name)
        except Exception as e:
            logger.error(f"获取本地文件路径失败: {e}")
            return ""

    async def download_file(self, file_path: str, filename: str) -> bool:
        """下载文件"""
        try:
            local_path = self.music_library.music_dir / filename
            if not self.nextcloud_client:
                raise Exception("NextCloud客户端未连接")
            
            success = await self.nextcloud_client.download_file(file_path, filename,local_path)
            
            if success:
                # 更新音乐库中的下载状态
                
                self.music_library.mark_song_downloaded(filename, str(local_path))
                logger.info(f"下载成功并更新状态: {filename}")
            
            return success
            
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            raise
    
    def has_nextcloud_client(self) -> bool:
        """检查是否有NextCloud客户端连接"""
        return self.nextcloud_client is not None
    
    def clear_cache(self):
        """清除缓存"""
        try:
            self.config_manager.clear_cache()
            if self.music_library:
                self.music_library.clear_cache()
            logger.info("缓存已清除")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            raise
    
    def get_connection_config(self) -> dict:
        """获取连接配置"""
        try:
            return self.config_manager.get_connection_config()
        except Exception as e:
            logger.error(f"获取连接配置失败: {e}")
            return {}
