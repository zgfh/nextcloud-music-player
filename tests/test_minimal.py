"""
最小化测试：只测试基本的Python功能，无GUI依赖
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
        self.assertTrue(True)
    
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
        
        init_file = os.path.join(src_path, '__init__.py')
        self.assertTrue(os.path.exists(init_file), "__init__.py 文件应该存在")

if __name__ == '__main__':
    unittest.main()
