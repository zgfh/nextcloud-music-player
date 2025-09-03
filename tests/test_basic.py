"""
基础测试用例
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestBasic(unittest.TestCase):
    """基础测试用例"""
    
    def test_import(self):
        """测试模块导入"""
        try:
            import nextcloud_music_player
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"导入失败: {e}")
    
    def test_config_manager(self):
        """测试配置管理器"""
        try:
            from nextcloud_music_player.config_manager import ConfigManager
            config = ConfigManager()
            self.assertIsNotNone(config)
        except ImportError:
            self.skipTest("ConfigManager 不可用")
    
    def test_nextcloud_client(self):
        """测试 NextCloud 客户端"""
        try:
            from nextcloud_music_player.nextcloud_client import NextCloudClient
            # 不进行实际连接，只测试类的创建
            client = NextCloudClient("http://test.com", "user", "pass")
            self.assertIsNotNone(client)
        except ImportError:
            self.skipTest("NextCloudClient 不可用")

class TestMusicLibrary(unittest.TestCase):
    """音乐库测试用例"""
    
    def test_music_library_import(self):
        """测试音乐库导入"""
        try:
            from nextcloud_music_player.music_library import MusicLibrary
            library = MusicLibrary()
            self.assertIsNotNone(library)
        except ImportError:
            self.skipTest("MusicLibrary 不可用")

class TestServices(unittest.TestCase):
    """服务测试用例"""
    
    def test_services_import(self):
        """测试服务模块导入"""
        try:
            from nextcloud_music_player.services import playlist_manager
            from nextcloud_music_player.services import playback_service
            self.assertTrue(True)
        except ImportError:
            self.skipTest("Services 模块不可用")

if __name__ == '__main__':
    unittest.main()
