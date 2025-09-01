"""
配置管理器 - 负责保存和加载用户配置和数据
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器，负责持久化配置和数据"""
    
    def __init__(self, app_name: str = "nextcloud_music_player"):
        self.app_name = app_name
        self.config_dir = self._get_config_directory()
        self.config_file = self.config_dir / "config.json"
        
        # 确保配置目录存在，处理权限问题
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"配置目录: {self.config_dir}")
        except (PermissionError, OSError) as e:
            logger.warning(f"无法创建配置目录 {self.config_dir}: {e}")
            # 如果无法创建配置目录，使用临时目录
            import tempfile
            import sys
            
            if sys.platform == 'ios' or 'iOS' in str(sys.platform):
                # iOS特殊处理：使用相对路径
                self.config_dir = Path('.') / f'{self.app_name}_config'
                try:
                    self.config_dir.mkdir(parents=True, exist_ok=True)
                    self.config_file = self.config_dir / "config.json"
                    logger.info(f"iOS备用配置目录: {self.config_dir}")
                except Exception as e2:
                    logger.warning(f"iOS备用方案也失败: {e2}")
                    # 最后的备用方案：使用当前目录的配置文件
                    self.config_dir = Path('.')
                    self.config_file = Path(f'{self.app_name}_config.json')
                    logger.info(f"最终备用配置文件: {self.config_file}")
            else:
                # 桌面平台使用临时目录
                self.config_dir = Path(tempfile.gettempdir()) / f'{self.app_name}_config'
                try:
                    self.config_dir.mkdir(parents=True, exist_ok=True)
                    self.config_file = self.config_dir / "config.json"
                    logger.info(f"临时配置目录: {self.config_dir}")
                except:
                    # 最后的后备方案：使用当前目录
                    self.config_dir = Path('.')
                    self.config_file = Path(f'{self.app_name}_config.json')
                    logger.info(f"当前目录配置文件: {self.config_file}")
        
        # 默认配置
        self.default_config = {
            "connection": {
                "server_url": "http://cloud.home.daozzg.com",
                "username": "guest", 
                "password": "",
                "default_sync_folder": "/mp3/音乐/01.周杰伦%20%20%20170首/",
                "auto_connect": False,
                "remember_credentials": True
            },
            "player": {
                "volume": 70,
                "play_mode": "repeat_one",
                "auto_play_on_select": True
            },
            "app": {
                "last_view": "playback",
                "window_size": [800, 600],
                "cache_max_size": 1073741824  # 1GB
            }
        }
        
        # 加载配置
        self.config = self.load_config()
        
    def get_config_directory(self) -> Path:
        """获取配置目录路径"""
        return self.config_dir
        
    def _get_config_directory(self) -> Path:
        """获取配置目录路径"""
        # 检查是否在iOS环境中运行
        try:
            import sys
            
            # 检测iOS环境
            if sys.platform == 'ios' or 'iOS' in str(sys.platform):
                # 在iOS中，使用Documents目录存储配置（更稳定的访问权限）
                try:
                    import toga
                    if hasattr(toga.App, 'app') and toga.App.app and hasattr(toga.App.app, 'paths'):
                        if hasattr(toga.App.app.paths, 'data'):
                            config_dir = toga.App.app.paths.data / self.app_name
                            return config_dir
                        elif hasattr(toga.App.app.paths, 'app'):
                            # 使用Documents目录而不是Library/Application Support
                            config_dir = toga.App.app.paths.app / 'Documents' / self.app_name
                            return config_dir
                except Exception as e:
                    logger.warning(f"无法获取Toga路径: {e}")
                    
                # iOS备用方案：使用相对路径
                try:
                    # 直接使用当前应用目录下的Documents文件夹
                    current_dir = Path.cwd()
                    config_dir = current_dir / 'Documents' / self.app_name
                    return config_dir
                except Exception as e:
                    logger.warning(f"iOS备用方案失败: {e}")
                    # 最终的iOS备用方案
                    return Path('.') / self.app_name
            
            # 尝试使用Toga的应用路径（适用于桌面平台）
            import toga
            if hasattr(toga.App, 'app') and toga.App.app and hasattr(toga.App.app, 'paths'):
                try:
                    # 对于桌面平台，使用用户数据目录
                    if hasattr(toga.App.app.paths, 'data'):
                        app_data_dir = toga.App.app.paths.data
                        config_dir = app_data_dir / self.app_name
                        return config_dir
                except:
                    pass
                    
        except (ImportError, AttributeError):
            pass
            
        # 传统平台的目录选择
        if os.name == 'nt':  # Windows
            config_dir = Path(os.environ.get('APPDATA', '')) / self.app_name
        elif os.name == 'posix':  # macOS/Linux
            if 'darwin' in os.sys.platform:  # macOS
                config_dir = Path.home() / 'Library' / 'Application Support' / self.app_name
            else:  # Linux
                config_dir = Path.home() / '.config' / self.app_name
        else:
            config_dir = Path.home() / f'.{self.app_name}'
            
        return config_dir
    
    def get_log_directory(self) -> Path:
        """获取日志目录路径"""
        try:
            # 日志目录通常与配置目录在同一级别
            log_dir = self.config_dir / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
        except (PermissionError, OSError) as e:
            # 如果无法创建日志目录，使用临时目录
            import tempfile
            temp_log_dir = Path(tempfile.gettempdir()) / f'{self.app_name}_logs'
            try:
                temp_log_dir.mkdir(parents=True, exist_ok=True)
                return temp_log_dir
            except:
                # 最后的后备方案：返回当前目录
                return Path('.')

    def get_cache_directory(self) -> Path:
        """获取缓存目录路径 - 用于存储下载的音乐文件"""
        try:
            import sys
            
            # iOS环境中使用Documents/Cache目录（更稳定的访问权限）
            if sys.platform == 'ios' or 'iOS' in str(sys.platform):
                try:
                    import toga
                    if hasattr(toga.App, 'app') and toga.App.app and hasattr(toga.App.app, 'paths'):
                        if hasattr(toga.App.app.paths, 'cache'):
                            cache_dir = toga.App.app.paths.cache / self.app_name
                            cache_dir.mkdir(parents=True, exist_ok=True)
                            return cache_dir
                        elif hasattr(toga.App.app.paths, 'data'):
                            cache_dir = toga.App.app.paths.data / self.app_name / 'cache'
                            cache_dir.mkdir(parents=True, exist_ok=True)
                            return cache_dir
                        elif hasattr(toga.App.app.paths, 'app'):
                            # 使用Documents/cache目录
                            cache_dir = toga.App.app.paths.app / 'Documents' / self.app_name / 'cache'
                            cache_dir.mkdir(parents=True, exist_ok=True)
                            return cache_dir
                except Exception as e:
                    logger.warning(f"无法获取iOS缓存路径: {e}")
                
                # iOS备用方案：使用相对路径
                try:
                    current_dir = Path.cwd()
                    cache_dir = current_dir / 'Documents' / self.app_name / 'cache'
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    return cache_dir
                except Exception as e:
                    logger.warning(f"iOS缓存备用方案失败: {e}")
                    # 最终备用方案
                    cache_dir = Path('.') / f'{self.app_name}_cache'
                    try:
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        return cache_dir
                    except:
                        return Path('.')
            
            # 桌面平台的缓存目录
            if os.name == 'nt':  # Windows
                cache_dir = Path(os.environ.get('LOCALAPPDATA', '')) / self.app_name / 'Cache'
            elif os.name == 'posix':  # macOS/Linux
                if 'darwin' in sys.platform:  # macOS
                    cache_dir = Path.home() / 'Library' / 'Caches' / self.app_name
                else:  # Linux
                    cache_dir = Path.home() / '.cache' / self.app_name
            else:
                cache_dir = self.config_dir / 'cache'
                
            cache_dir.mkdir(parents=True, exist_ok=True)
            return cache_dir
            
        except Exception as e:
            logger.warning(f"无法创建缓存目录，使用临时目录: {e}")
            # 备用方案：使用临时目录
            import tempfile
            temp_cache_dir = Path(tempfile.gettempdir()) / f'{self.app_name}_cache'
            try:
                temp_cache_dir.mkdir(parents=True, exist_ok=True)
                return temp_cache_dir
            except:
                return Path('.')

    def get_documents_directory(self) -> Path:
        """获取文档目录路径 - 用于存储用户数据（播放列表、用户设置等）"""
        try:
            import sys
            
            # iOS环境中使用Documents目录
            if sys.platform == 'ios' or 'iOS' in str(sys.platform):
                try:
                    # 备用方案：使用Toga路径
                    try:
                        import toga
                        if hasattr(toga.App, 'app') and toga.App.app and hasattr(toga.App.app, 'paths'):
                            if hasattr(toga.App.app.paths, 'data'):
                                docs_dir = toga.App.app.paths.data / self.app_name
                                docs_dir.mkdir(parents=True, exist_ok=True)
                                return docs_dir
                    except Exception:
                        pass
                except:
                    pass
            
            # 桌面平台的文档目录
            if os.name == 'nt':  # Windows
                docs_dir = Path.home() / 'Documents' / self.app_name
            elif os.name == 'posix':  # macOS/Linux
                docs_dir = Path.home() / 'Documents' / self.app_name
            else:
                docs_dir = self.config_dir / 'documents'
                
            docs_dir.mkdir(parents=True, exist_ok=True)
            return docs_dir
            
        except Exception as e:
            logger.warning(f"无法创建文档目录，使用配置目录: {e}")
            # 备用方案：使用配置目录
            docs_dir = self.config_dir / 'documents'
            try:
                docs_dir.mkdir(parents=True, exist_ok=True)
                return docs_dir
            except:
                return self.config_dir

    def get_temp_directory(self) -> Path:
        """获取临时目录路径 - 用于临时文件和正在下载的文件"""
        try:
            import tempfile
            import sys
            
            # iOS环境中使用tmp目录
            if sys.platform == 'ios' or 'iOS' in str(sys.platform):
                temp_dir = Path(tempfile.gettempdir()) / self.app_name
            else:
                temp_dir = Path(tempfile.gettempdir()) / self.app_name
                
            temp_dir.mkdir(parents=True, exist_ok=True)
            return temp_dir
            
        except Exception as e:
            logger.warning(f"无法创建临时目录: {e}")
            return Path('.')
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    
                # 合并默认配置和加载的配置
                config = self.default_config.copy()
                self._deep_merge(config, loaded_config)
                logger.info(f"配置文件已加载: {self.config_file}")
                return config
            else:
                logger.info("配置文件不存在，使用默认配置")
                return self.default_config.copy()
                
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return self.default_config.copy()
    
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"配置文件已保存: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key_path: str, default=None) -> Any:
        """获取配置值，支持点号路径如 'connection.server_url'"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """设置配置值，支持点号路径"""
        keys = key_path.split('.')
        config = self.config
        
        # 导航到倒数第二层
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 设置最后一层的值
        config[keys[-1]] = value
        
    def get_connection_config(self) -> Dict[str, str]:
        """获取连接配置"""
        return self.config.get("connection", {})
    
    def save_connection_config(self, server_url: str, username: str, password: str,
                             sync_folder: str = "", remember: bool = True) -> None:
        """保存连接配置"""
        connection_config = {
            "server_url": server_url,
            "username": username,
            "default_sync_folder": sync_folder,
            "remember_credentials": remember
        }
        
        # 只有在选择记住凭据时才保存密码
        if remember:
            connection_config["password"] = password
        else:
            connection_config["password"] = ""
            
        self.config["connection"].update(connection_config)
        self.save_config()
    
    def get_player_config(self) -> Dict[str, Any]:
        """获取播放器配置"""
        return self.config.get("player", {})
    
    def save_player_config(self, volume: int = None, play_mode: str = None,
                          auto_play: bool = None) -> None:
        """保存播放器配置"""
        player_config = {}
        if volume is not None:
            player_config["volume"] = volume
        if play_mode is not None:
            player_config["play_mode"] = play_mode
        if auto_play is not None:
            player_config["auto_play_on_select"] = auto_play
            
        self.config["player"].update(player_config)
        self.save_config()
    
    def load_playlists(self) -> Dict[str, Any]:
        """加载播放列表缓存"""
        try:
            playlist_file = self.config_dir / "playlists.json"
            if playlist_file.exists():
                with open(playlist_file, 'r', encoding='utf-8') as f:
                    playlists_data = json.load(f)
                logger.info("播放列表缓存已加载")
                return playlists_data
        except Exception as e:
            logger.error(f"加载播放列表缓存失败: {e}")
        
        return {
            "playlists": [],
            "current_playlist_id": None,
            "next_id": 1
        }

    def save_playlists(self, playlists_data: Dict[str, Any]) -> None:
        """保存播放列表缓存"""
        try:
            from datetime import datetime
            # 更新保存时间
            playlists_data["last_updated"] = datetime.now().isoformat()
            
            playlist_file = self.config_dir / "playlists.json"
            with open(playlist_file, 'w', encoding='utf-8') as f:
                json.dump(playlists_data, f, indent=2, ensure_ascii=False)
            logger.info("播放列表缓存已保存")
        except Exception as e:
            logger.error(f"保存播放列表缓存失败: {e}")

    def add_playlist(self, name: str, songs: list, folder_path: str = "") -> int:
        """添加新的播放列表"""
        try:
            from datetime import datetime
            playlists_data = self.load_playlists()
            
            # 创建新播放列表
            playlist_id = playlists_data["next_id"]
            new_playlist = {
                "id": playlist_id,
                "name": name,
                "songs": songs,
                "folder_path": folder_path,
                "created_at": datetime.now().isoformat(),
                "last_played": None,
                "play_count": 0
            }
            
            # 添加到列表开头（最新的在前面）
            playlists_data["playlists"].insert(0, new_playlist)
            playlists_data["next_id"] = playlist_id + 1
            playlists_data["current_playlist_id"] = playlist_id
            
            # 保存
            self.save_playlists(playlists_data)
            logger.info(f"已添加新播放列表: {name} (ID: {playlist_id})")
            return playlist_id
            
        except Exception as e:
            logger.error(f"添加播放列表失败: {e}")
            return -1

    def get_playlist_by_id(self, playlist_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取播放列表"""
        try:
            playlists_data = self.load_playlists()
            for playlist in playlists_data["playlists"]:
                if playlist["id"] == playlist_id:
                    return playlist
            return None
        except Exception as e:
            logger.error(f"获取播放列表失败: {e}")
            return None

    def update_playlist_play_info(self, playlist_id: int) -> None:
        """更新播放列表的播放信息"""
        try:
            from datetime import datetime
            playlists_data = self.load_playlists()
            
            for playlist in playlists_data["playlists"]:
                if playlist["id"] == playlist_id:
                    playlist["last_played"] = datetime.now().isoformat()
                    playlist["play_count"] = playlist.get("play_count", 0) + 1
                    break
            
            playlists_data["current_playlist_id"] = playlist_id
            self.save_playlists(playlists_data)
            
        except Exception as e:
            logger.error(f"更新播放列表信息失败: {e}")

    def delete_playlist(self, playlist_id: int) -> bool:
        """删除播放列表"""
        try:
            playlists_data = self.load_playlists()
            
            # 查找并删除播放列表
            for i, playlist in enumerate(playlists_data["playlists"]):
                if playlist["id"] == playlist_id:
                    del playlists_data["playlists"][i]
                    logger.info(f"已删除播放列表: {playlist['name']} (ID: {playlist_id})")
                    
                    # 如果删除的是当前播放列表，清除当前播放列表ID
                    if playlists_data["current_playlist_id"] == playlist_id:
                        playlists_data["current_playlist_id"] = None
                    
                    self.save_playlists(playlists_data)
                    return True
            
            logger.warning(f"未找到播放列表 ID: {playlist_id}")
            return False
            
        except Exception as e:
            logger.error(f"删除播放列表失败: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """清除所有缓存文件（音乐列表、播放列表等）"""
        try:
            # 清除音乐列表缓存（现在由 music_library 管理）
            music_list_file = self.config_dir / "music_list.json"
            if music_list_file.exists():
                music_list_file.unlink()
                logger.info("音乐列表缓存已清除")
            
            # 清除播放列表缓存
            playlists_file = self.config_dir / "playlists.json"
            if playlists_file.exists():
                playlists_file.unlink()
                logger.info("播放列表缓存已清除")
                
            return True
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            return False
    
    def _deep_merge(self, target: dict, source: dict) -> None:
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
