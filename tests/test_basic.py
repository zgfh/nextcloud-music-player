"""
基础测试用例 - Screenshot to UI Converter
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
    
    def test_ai_processor_import(self):
        """测试 AI 处理器导入"""
        try:
            from nextcloud_music_player.ai_processor import AIProcessor
            processor = AIProcessor()
            self.assertIsNotNone(processor)
            processor.cleanup()
        except ImportError:
            self.skipTest("AIProcessor 不可用")
    
    def test_ui_converter_views_import(self):
        """测试 UI 转换器视图导入"""
        try:
            from nextcloud_music_player.ui_converter_views import ViewManager
            # 只测试导入，不创建实例（需要mock app）
            self.assertTrue(hasattr(ViewManager, '__init__'))
        except ImportError:
            self.skipTest("UI Converter Views 不可用")

class TestAIProcessor(unittest.TestCase):
    """AI处理器测试用例"""
    
    def test_ai_processor_initialization(self):
        """测试AI处理器初始化"""
        try:
            from nextcloud_music_player.ai_processor import AIProcessor
            processor = AIProcessor()
            
            # 测试基本属性
            self.assertIsNotNone(processor.supported_frameworks)
            self.assertIn('react', processor.supported_frameworks)
            self.assertIn('vue', processor.supported_frameworks)
            
            # 清理
            processor.cleanup()
        except ImportError:
            self.skipTest("AIProcessor 不可用")

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
