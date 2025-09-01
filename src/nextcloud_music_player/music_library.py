"""
Music library management for the NextCloud Music Player.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from .config_manager import ConfigManager


class MusicLibrary:
    """Manages the local music library with metadata support."""

    def __init__(self):
        """Initialize the music library."""
        self.songs: Dict[str, Dict] = {}  # song_name -> song_info mapping

        # 使用ConfigManager来获取配置目录
        config_manager = ConfigManager()
        config_dir = config_manager.config_dir

        # 设置音乐下载目录
        self.music_dir = config_dir / "music"
        self.music_dir.mkdir(parents=True, exist_ok=True)

        # 统一使用 music_list.json 管理音乐信息
        self.music_list_file = config_dir / "music_list.json"

        self.load_music_list()

    def add_song_with_info(self, song_name: str, file_path: str, song_info: Dict) -> None:
        """Add a song with metadata to the library."""
        if os.path.exists(file_path):
            self.songs[song_name] = {
                **song_info,
                'filepath': file_path,
                'is_downloaded': True,
                'download_time': datetime.now().isoformat()
            }
            self.save_music_list()

    def add_remote_song(self, song_name: str, remote_path: str, size: int = 0, modified: str = '', etag: str = '') -> None:
        """Add a remote song to the library (not yet downloaded)."""
        song_info = self.extract_song_info_from_filename(song_name)
        # 如果不存在则更新
        if song_name in self.songs:
            return
        self.songs[song_name] = {
            **song_info,
            'filename': song_name,
            'remote_path': remote_path,
            'size': size,
            'modified': modified,
            'etag': etag,
            'is_downloaded': False,
            'filepath': None  # Will be set when downloaded
        }
        self.save_music_list()

    def update_remote_song(self, song_name: str, file_info: Dict) -> None:
        """Update remote song information."""
        if song_name in self.songs:
            self.songs[song_name].update({
                'remote_path': file_info['path'],
                'size': file_info.get('size', 0),
                'modified': file_info.get('modified', ''),
                'etag': file_info.get('etag', ''),
                'is_downloaded': False,  # Mark for re-download
                'filepath': None
            })
            self.save_music_list()

    def mark_song_downloaded(self, song_name: str, local_path: str) -> None:
        """Mark a song as downloaded and set its local path."""
        if song_name in self.songs:
            self.songs[song_name]['is_downloaded'] = True
            self.songs[song_name]['filepath'] = local_path
            self.songs[song_name]['download_time'] = datetime.now().isoformat()
            self.save_music_list()

    def is_song_downloaded(self, song_name: str) -> bool:
        """Check if a song is downloaded locally."""
        song = self.songs.get(song_name)
        if not song:
            return False

        # Check if marked as downloaded and file exists
        is_downloaded = song.get('is_downloaded', False)
        filepath = song.get('filepath')

        if is_downloaded and filepath and os.path.exists(filepath):
            return True

        # If file doesn't exist, mark as not downloaded
        if song_name in self.songs:
            self.songs[song_name]['is_downloaded'] = False
            self.songs[song_name]['filepath'] = None
            self.save_music_list()

        return False

    def is_file_cached(self, song_name: str) -> bool:
        """Check if a song file is cached (downloaded) locally."""
        return self.is_song_downloaded(song_name)

    def get_song_info(self, song_name: str) -> Optional[Dict]:
        """Get song information."""
        return self.songs.get(song_name)

    def extract_song_info_from_filename(self, filename: str) -> Dict:
        """Extract song info from filename."""
        # Remove file extension
        name_without_ext = os.path.splitext(filename)[0]

        # Try to parse "Artist - Title" format
        if ' - ' in name_without_ext:
            parts = name_without_ext.split(' - ', 1)
            return {
                'title': parts[1].strip(),
                'artist': parts[0].strip(),
                'album': '未知专辑'
            }
        else:
            return {
                'title': name_without_ext,
                'artist': '未知艺术家',
                'album': '未知专辑'
            }

    def has_song(self, song_name: str) -> bool:
        """Check if a song exists in the library."""
        return song_name in self.songs

    def remove_song(self, song_name: str) -> None:
        """Remove a song from the library."""
        if song_name in self.songs:
            del self.songs[song_name]
            self.save_music_list()

    def get_song_path(self, song_name: str) -> str:
        """Get the file path for a song."""
        song_info = self.songs.get(song_name, {})
        return song_info.get('filepath', "")

    def get_local_file_path(self, song_name: str) -> Optional[str]:
        """Get the local file path for a song if it's downloaded."""
        song_info = self.songs.get(song_name, {})
        if song_info.get('is_downloaded', False):
            return song_info.get('filepath', "")
        return None

    def get_song_info(self, song_name: str) -> Dict:
        """Get the metadata for a song."""
        return self.songs.get(song_name, {})

    def list_songs(self) -> List[str]:
        """Get a list of all song names in the library."""
        return list(self.songs.keys())

    def search_songs(self, query: str) -> List[str]:
        """Search for songs by title, artist, or album."""
        query = query.lower()
        results = []

        for song_name, song_info in self.songs.items():
            if (query in song_info.get('title', '').lower() or
                query in song_info.get('artist', '').lower() or
                query in song_info.get('album', '').lower() or
                    query in song_name.lower()):
                results.append(song_name)

        return results

    def get_artists(self) -> List[str]:
        """Get a list of all artists."""
        artists = set()
        for song_info in self.songs.values():
            artists.add(song_info.get('artist', '未知艺术家'))
        return sorted(list(artists))

    def get_albums(self) -> List[str]:
        """Get a list of all albums."""
        albums = set()
        for song_info in self.songs.values():
            albums.add(song_info.get('album', '未知专辑'))
        return sorted(list(albums))

    def get_songs_by_artist(self, artist: str) -> List[str]:
        """Get all songs by a specific artist."""
        return [name for name, info in self.songs.items()
                if info.get('artist', '未知艺术家') == artist]

    def get_songs_by_album(self, album: str) -> List[str]:
        """Get all songs from a specific album."""
        return [name for name, info in self.songs.items()
                if info.get('album', '未知专辑') == album]

    def clear(self) -> None:
        """Clear all songs from the library."""
        self.songs.clear()
        self.save_music_list()

    def clear_cache(self) -> None:
        """Clear the library cache and reset."""
        self.songs.clear()
        # 删除音乐列表文件
        if self.music_list_file.exists():
            try:
                self.music_list_file.unlink()
            except Exception as e:
                print(f"Failed to delete music list file: {e}")

    def get_songs_count(self) -> int:
        """Get the number of songs in the library."""
        return len(self.songs)

    def save_music_list(self) -> None:
        """Save the music list to file."""
        try:
            music_data = {
                "music_list": self.songs,
                "last_sync": datetime.now().isoformat(),
                "sync_folder": getattr(self, 'sync_folder', ''),
                "cache_stats": {
                    "total_songs": len(self.songs),
                    "downloaded_songs": len([s for s in self.songs.values() if s.get('is_downloaded', False)]),
                    "cache_size": self._calculate_cache_size()
                }
            }

            with open(self.music_list_file, 'w', encoding='utf-8') as f:
                json.dump(music_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save music list: {e}")

    def load_music_list(self) -> None:
        """Load the music list from file."""
        try:
            if self.music_list_file.exists():
                with open(self.music_list_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 兼容旧格式 - 如果直接是歌曲字典，转换为新格式
                if isinstance(data, dict) and "music_list" in data:
                    self.songs = data["music_list"]
                    self.sync_folder = data.get("sync_folder", "")
                else:
                    # 旧格式，直接是歌曲字典
                    self.songs = data
                    self.sync_folder = ""

                # 验证缓存的文件是否仍然存在（仅检查已下载的文件）
                valid_songs = {}
                for name, info in self.songs.items():
                    # 如果是已下载的歌曲，检查文件是否存在
                    if info.get('is_downloaded', False):
                        if os.path.exists(info.get('filepath', '')):
                            valid_songs[name] = info
                        else:
                            # 文件不存在，标记为未下载
                            info['is_downloaded'] = False
                            info['filepath'] = None
                            valid_songs[name] = info
                    else:
                        # 未下载的远程歌曲，保留在库中
                        valid_songs[name] = info

                if len(valid_songs) != len(self.songs):
                    self.songs = valid_songs
                    self.save_music_list()

        except Exception as e:
            print(f"Failed to load music list: {e}")
            self.songs = {}
            self.sync_folder = ""

    def get_all_songs(self) -> Dict[str, Dict]:
        """获取所有歌曲信息"""
        return self.songs.copy()

    def _calculate_cache_size(self) -> int:
        """Calculate total size of downloaded music files."""
        total_size = 0
        for song_info in self.songs.values():
            if song_info.get('is_downloaded', False):
                filepath = song_info.get('filepath')
                if filepath and os.path.exists(filepath):
                    try:
                        total_size += os.path.getsize(filepath)
                    except OSError:
                        pass
        return total_size
