# lyrics_service.py\n\n歌词服务模块 - 负责加载、解析和管理LRC格式的歌词文件
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class LyricLine:
    """歌词行对象"""
    
    def __init__(self, time_seconds: float, text: str):
        self.time_seconds = time_seconds
        self.text = text
        self.is_current = False  # 是否为当前播放的歌词行
        
    def __str__(self):
        return f"[{self.time_seconds:.2f}s] {self.text}"
    
    def __repr__(self):
        return f"LyricLine(time={self.time_seconds}, text='{self.text}')"


class LyricsService:
    """歌词服务 - 负责加载、解析和管理LRC格式的歌词文件"""
    
    def __init__(self, config_manager=None, nextcloud_client=None, music_library=None):
        self.config_manager = config_manager
        self.nextcloud_client = nextcloud_client
        self.music_library = music_library
        self.current_lyrics = None  # 当前加载的歌词数据
        self.current_song_name = None  # 当前歌曲名称
        self.lyrics_cache = {}  # 歌词缓存
        
        # LRC时间标签正则表达式 [mm:ss.xx] 或 [mm:ss]
        self.time_pattern = re.compile(r'\[(\d{1,2}):(\d{2})(?:\.(\d{2}))?\]')
        
        logger.info("歌词服务初始化完成")
    
    def update_clients(self, nextcloud_client=None, music_library=None):
        """更新客户端实例"""
        if nextcloud_client:
            self.nextcloud_client = nextcloud_client
        if music_library:
            self.music_library = music_library
        logger.debug("歌词服务客户端已更新")
    
    def get_remote_lyrics_path(self, song_name: str, song_remote_path: str = None) -> str:
        """
        根据歌曲名称或远程路径生成歌词文件的远程路径
        
        Args:
            song_name: 歌曲名称
            song_remote_path: 歌曲的远程路径（可选）
            
        Returns:
            歌词文件的远程路径
        """
        if song_remote_path:
            # 基于歌曲的远程路径生成歌词路径
            base_path = os.path.splitext(song_remote_path)[0]
            return f"{base_path}.lrc"
        else:
            # 使用歌曲名生成默认路径
            base_name = os.path.splitext(song_name)[0]
            return f"{base_name}.lrc"
    
    async def download_lyrics(self, song_name: str, song_remote_path: str = None) -> bool:
        """
        从NextCloud下载歌词文件
        
        Args:
            song_name: 歌曲名称
            song_remote_path: 歌曲的远程路径（可选，用于定位歌词文件）
        
        Returns:
            bool: 下载是否成功
        """
        try:
            if not self.nextcloud_client:
                logger.warning("NextCloud客户端不可用，无法下载歌词")
                return False
            
            # 获取远程歌词文件路径
            remote_lyrics_path = self.get_remote_lyrics_path(song_name, song_remote_path)
            
            # 获取本地歌词保存路径 - 保存到和音乐文件同目录
            music_dir = ""
            if self.config_manager:
                music_dir = str(self.config_manager.get_music_directory())
            
            if not music_dir or not os.path.exists(music_dir):
                logger.warning("音乐目录不存在，无法下载歌词")
                return False
            
            # 生成本地歌词文件名
            base_name = os.path.splitext(song_name)[0]
            local_lyrics_filename = f"{base_name}.lrc"
            local_lyrics_path = os.path.join(music_dir, local_lyrics_filename)
            
            logger.info(f"尝试下载歌词: {remote_lyrics_path} -> {local_lyrics_path}")
            
            # 检查远程文件是否存在
            try:
                file_info = await self.nextcloud_client.get_file_info(remote_lyrics_path)
                if not file_info:
                    logger.info(f"远程歌词文件不存在: {remote_lyrics_path}")
                    return False
            except Exception as e:
                logger.info(f"检查远程歌词文件失败: {e}")
                return False
            
            # 下载歌词文件
            success = await self.nextcloud_client.download_file(remote_lyrics_path, local_lyrics_filename, local_lyrics_path)
            
            if success:
                logger.info(f"歌词下载成功: {song_name}")
                # 清除缓存，强制重新加载
                if song_name in self.lyrics_cache:
                    del self.lyrics_cache[song_name]
                return True
            else:
                logger.warning(f"歌词下载失败: {song_name}")
                return False
                
        except Exception as e:
            logger.error(f"下载歌词时发生错误: {e}")
            return False
    
    def get_lyrics_file_path(self, song_name: str) -> Optional[str]:
        """
        根据歌曲名称获取对应的歌词文件路径
        
        Args:
            song_name: 歌曲名称（包含扩展名）
            
        Returns:
            歌词文件的完整路径，如果不存在则返回None
        """
        try:
            if not song_name:
                return None
            
            # 移除音频文件扩展名，添加.lrc扩展名
            base_name = os.path.splitext(song_name)[0]
            lyrics_filename = f"{base_name}.lrc"
            
            # 获取音乐目录 - 歌词文件和音乐文件同目录
            if self.config_manager:
                music_dir = str(self.config_manager.get_music_directory())
                if music_dir and os.path.exists(music_dir):
                    lyrics_path = os.path.join(music_dir, lyrics_filename)
                    if os.path.exists(lyrics_path):
                        logger.debug(f"找到歌词文件: {lyrics_path}")
                        return lyrics_path
            
            # 在当前目录查找
            if os.path.exists(lyrics_filename):
                logger.debug(f"在当前目录找到歌词文件: {lyrics_filename}")
                return os.path.abspath(lyrics_filename)
            
            logger.debug(f"未找到歌词文件: {lyrics_filename}")
            return None
            
        except Exception as e:
            logger.error(f"获取歌词文件路径失败: {e}")
            return None
    
    def parse_lrc_content(self, content: str) -> Tuple[List[LyricLine], Dict[str, str]]:
        """
        解析LRC歌词内容
        
        Args:
            content: LRC文件内容
            
        Returns:
            (歌词行列表, 元数据字典)
        """
        lyrics_lines = []
        metadata = {}
        
        try:
            lines = content.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 解析元数据标签 [tag:value]
                if line.startswith('[') and ':' in line and not self.time_pattern.match(line):
                    try:
                        tag_match = re.match(r'\[([^:]+):([^\]]*)\]', line)
                        if tag_match:
                            tag = tag_match.group(1).lower()
                            value = tag_match.group(2).strip()
                            metadata[tag] = value
                            logger.debug(f"解析元数据: {tag} = {value}")
                            continue
                    except Exception as e:
                        logger.warning(f"解析元数据标签失败: {line}, 错误: {e}")
                
                # 解析时间标签和歌词
                time_matches = self.time_pattern.findall(line)
                if time_matches:
                    # 提取歌词文本（移除所有时间标签）
                    lyric_text = self.time_pattern.sub('', line).strip()
                    
                    # 为每个时间标签创建歌词行
                    for time_match in time_matches:
                        try:
                            minutes = int(time_match[0])
                            seconds = int(time_match[1])
                            centiseconds = int(time_match[2]) if time_match[2] else 0
                            
                            # 转换为总秒数
                            total_seconds = minutes * 60 + seconds + centiseconds / 100.0
                            
                            # 创建歌词行对象
                            lyric_line = LyricLine(total_seconds, lyric_text)
                            lyrics_lines.append(lyric_line)
                            
                        except (ValueError, IndexError) as e:
                            logger.warning(f"解析时间标签失败: {time_match}, 错误: {e}")
            
            # 按时间排序
            lyrics_lines.sort(key=lambda x: x.time_seconds)
            
            logger.info(f"成功解析歌词: {len(lyrics_lines)} 行歌词, {len(metadata)} 个元数据")
            
        except Exception as e:
            logger.error(f"解析LRC内容失败: {e}")
        
        return lyrics_lines, metadata
    
    def load_lyrics(self, song_name: str, auto_download: bool = True) -> bool:
        """
        加载指定歌曲的歌词
        
        Args:
            song_name: 歌曲名称
            auto_download: 如果本地没有歌词文件，是否自动尝试下载
            
        Returns:
            是否成功加载歌词
        """
        try:
            # 检查缓存
            if song_name in self.lyrics_cache:
                self.current_lyrics = self.lyrics_cache[song_name]
                self.current_song_name = song_name
                logger.debug(f"从缓存加载歌词: {song_name}")
                return True
            
            # 获取歌词文件路径
            lyrics_path = self.get_lyrics_file_path(song_name)
            if lyrics_path:
                # 本地文件存在，直接加载
                return self._load_lyrics_from_file(song_name, lyrics_path)
            
            # 本地文件不存在，尝试自动下载
            if auto_download and self.nextcloud_client:
                logger.info(f"本地无歌词文件，尝试自动下载: {song_name}")
                
                # 获取歌曲的远程路径信息
                song_remote_path = None
                if self.music_library:
                    song_info = self.music_library.get_song_info(song_name)
                    if song_info:
                        song_remote_path = song_info.get('remote_path')
                
                # 创建异步任务下载歌词
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，创建任务
                    task = loop.create_task(self._download_and_load_lyrics(song_name, song_remote_path))
                    # 注意：这里不能等待任务完成，因为会阻塞UI
                    logger.info(f"已创建歌词下载任务: {song_name}")
                else:
                    # 如果没有事件循环，同步执行
                    asyncio.run(self._download_and_load_lyrics(song_name, song_remote_path))
            
            # 无论是否启动下载，都先返回无歌词状态
            logger.info(f"暂无歌词文件: {song_name}")
            self.current_lyrics = None
            self.current_song_name = song_name
            return False
            
        except Exception as e:
            logger.error(f"加载歌词失败: {song_name}, 错误: {e}")
            self.current_lyrics = None
            self.current_song_name = song_name
            return False
    
    def _load_lyrics_from_file(self, song_name: str, lyrics_path: str) -> bool:
        """从文件加载歌词的内部方法"""
        try:
            # 读取歌词文件
            with open(lyrics_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析歌词内容
            lyrics_lines, metadata = self.parse_lrc_content(content)
            
            if not lyrics_lines:
                logger.warning(f"歌词文件为空或格式错误: {lyrics_path}")
                self.current_lyrics = None
                self.current_song_name = song_name
                return False
            
            # 创建歌词数据对象
            lyrics_data = {
                'song_name': song_name,
                'file_path': lyrics_path,
                'lines': lyrics_lines,
                'metadata': metadata,
                'loaded_at': datetime.now().isoformat()
            }
            
            # 缓存歌词数据
            self.lyrics_cache[song_name] = lyrics_data
            self.current_lyrics = lyrics_data
            self.current_song_name = song_name
            
            logger.info(f"成功加载歌词: {song_name}, 共 {len(lyrics_lines)} 行")
            return True
            
        except Exception as e:
            logger.error(f"从文件加载歌词失败: {lyrics_path}, 错误: {e}")
            return False
    
    async def _download_and_load_lyrics(self, song_name: str, song_remote_path: str = None):
        """下载并加载歌词的异步方法"""
        try:
            # 尝试下载歌词
            download_success = await self.download_lyrics(song_name, song_remote_path)
            
            if download_success:
                # 下载成功，重新尝试加载
                lyrics_path = self.get_lyrics_file_path(song_name)
                if lyrics_path:
                    success = self._load_lyrics_from_file(song_name, lyrics_path)
                    if success:
                        logger.info(f"歌词下载并加载成功: {song_name}")
                    else:
                        logger.warning(f"歌词下载成功但加载失败: {song_name}")
                else:
                    logger.warning(f"歌词下载成功但找不到本地文件: {song_name}")
            else:
                logger.info(f"歌词下载失败，可能远程不存在: {song_name}")
                
        except Exception as e:
            logger.error(f"下载并加载歌词失败: {song_name}, 错误: {e}")
    
    def get_current_lyric_line(self, position_seconds: float) -> Optional[LyricLine]:
        """
        根据播放位置获取当前应显示的歌词行
        
        Args:
            position_seconds: 播放位置（秒）
            
        Returns:
            当前歌词行，如果没有则返回None
        """
        if not self.current_lyrics or not self.current_lyrics.get('lines'):
            return None
        
        lyrics_lines = self.current_lyrics['lines']
        
        # 找到当前时间对应的歌词行
        current_line = None
        for lyric_line in lyrics_lines:
            if lyric_line.time_seconds <= position_seconds:
                current_line = lyric_line
            else:
                break
        
        return current_line
    
    def get_lyrics_around_position(self, position_seconds: float, context_lines: int = 2) -> List[LyricLine]:
        """
        获取指定位置周围的歌词行（用于显示上下文）
        
        Args:
            position_seconds: 播放位置（秒）
            context_lines: 上下文行数
            
        Returns:
            歌词行列表，当前行会被标记
        """
        if not self.current_lyrics or not self.current_lyrics.get('lines'):
            return []
        
        lyrics_lines = self.current_lyrics['lines']
        
        # 重置所有行的当前状态
        for line in lyrics_lines:
            line.is_current = False
        
        # 找到当前歌词行的索引
        current_index = -1
        for i, lyric_line in enumerate(lyrics_lines):
            if lyric_line.time_seconds <= position_seconds:
                current_index = i
            else:
                break
        
        if current_index == -1:
            # 播放位置在第一行之前
            end_index = min(context_lines * 2 + 1, len(lyrics_lines))
            return lyrics_lines[:end_index]
        
        # 标记当前行
        if current_index < len(lyrics_lines):
            lyrics_lines[current_index].is_current = True
        
        # 计算显示范围
        start_index = max(0, current_index - context_lines)
        end_index = min(len(lyrics_lines), current_index + context_lines + 1)
        
        return lyrics_lines[start_index:end_index]
    
    def get_all_lyrics_lines(self) -> List[LyricLine]:
        """
        获取当前歌曲的所有歌词行
        
        Returns:
            所有歌词行列表
        """
        if not self.current_lyrics or not self.current_lyrics.get('lines'):
            return []
        
        return self.current_lyrics['lines'].copy()
    
    def get_lyrics_metadata(self) -> Dict[str, str]:
        """
        获取当前歌词的元数据
        
        Returns:
            元数据字典
        """
        if not self.current_lyrics:
            return {}
        
        return self.current_lyrics.get('metadata', {}).copy()
    
    def has_lyrics(self, song_name: str = None) -> bool:
        """
        检查是否有歌词可用
        
        Args:
            song_name: 歌曲名称，如果不提供则检查当前歌曲
            
        Returns:
            是否有歌词
        """
        if song_name:
            return self.get_lyrics_file_path(song_name) is not None
        else:
            return self.current_lyrics is not None and bool(self.current_lyrics.get('lines'))
    
    def clear_lyrics(self):
        """清除当前歌词数据"""
        self.current_lyrics = None
        self.current_song_name = None
        logger.debug("已清除当前歌词数据")
    
    def clear_cache(self):
        """清除歌词缓存"""
        self.lyrics_cache.clear()
        logger.info("已清除歌词缓存")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取缓存信息
        
        Returns:
            缓存信息字典
        """
        return {
            'cached_songs': list(self.lyrics_cache.keys()),
            'cache_size': len(self.lyrics_cache),
            'current_song': self.current_song_name,
            'has_current_lyrics': self.current_lyrics is not None
        }\n\n