"""
最小化测试：只测试基本的Python功能 - Screenshot to UI Converter
"""
import unittest
import sys
import os

class TestEnvironment(unittest.TestCase):
    """测试环境兼容性"""
    
    def test_python_version(self):
        """测试Python版本兼容性"""
        self.assertGreaterEqual(sys.version_info.major, 3)
        self.assertGreaterEqual(sys.version_info.minor, 8)
    
    def test_core_libraries(self):
        """测试核心库导入"""
        import json
        import os
        import sys
        import tempfile
        import logging
        from pathlib import Path
        self.assertTrue(True)
    
    def test_image_libraries(self):
        """测试图像处理库"""
        try:
            from PIL import Image, ImageDraw
            # 测试基本图像创建
            img = Image.new('RGB', (100, 100), color='white')
            self.assertEqual(img.size, (100, 100))
        except ImportError:
            self.skipTest("PIL/Pillow 不可用，将使用基础功能")
    
    def test_http_dependencies(self):
        """测试HTTP相关依赖"""
        try:
            import requests
            import httpx
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"HTTP依赖导入失败: {e}")
    
    def test_project_structure(self):
        """测试项目结构"""
        project_root = os.path.dirname(os.path.dirname(__file__))
        src_path = os.path.join(project_root, 'src', 'nextcloud_music_player')
        self.assertTrue(os.path.exists(src_path), "源代码目录应该存在")
        
        # 测试新的核心文件
        required_files = [
            '__init__.py',
            'app.py',
            'ai_processor.py',
            'ui_converter_views.py'
        ]
        
        for file in required_files:
            file_path = os.path.join(src_path, file)
            self.assertTrue(os.path.exists(file_path), f"核心文件 {file} 应该存在")

    def test_ai_processor_basic(self):
        """测试AI处理器基础功能"""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
            from nextcloud_music_player.ai_processor import AIProcessor
            
            processor = AIProcessor()
            self.assertIsNotNone(processor.supported_frameworks)
            self.assertIn('react', processor.supported_frameworks)
            
            # 清理
            processor.cleanup()
        except ImportError:
            self.skipTest("AI处理器模块不可用")

if __name__ == '__main__':
    unittest.main()
