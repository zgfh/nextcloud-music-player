"""
Tests for Screenshot to UI Converter functionality
"""

import unittest
import tempfile
import os
from pathlib import Path
import json

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class TestAIProcessor(unittest.TestCase):
    """Test the AI processor functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        from nextcloud_music_player.ai_processor import AIProcessor, ProgressCallback
        self.processor = AIProcessor()
        self.test_image_path = None
        
        # Create a test image if PIL is available
        if PIL_AVAILABLE:
            self.test_image_path = self.create_test_image()
    
    def tearDown(self):
        """Clean up test fixtures"""
        if self.processor:
            self.processor.cleanup()
        
        # Clean up test image
        if self.test_image_path and os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)
    
    def create_test_image(self):
        """Create a test image for processing"""
        if not PIL_AVAILABLE:
            return None
            
        # Create a simple test UI
        img = Image.new('RGB', (400, 300), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw test UI elements
        draw.rectangle([0, 0, 400, 50], fill='#2196F3')  # Header
        draw.rectangle([20, 70, 120, 100], fill='#4CAF50')  # Button
        draw.text((20, 120), "Test text", fill='black')  # Text
        
        # Save to temp file
        temp_path = tempfile.mktemp(suffix='.png')
        img.save(temp_path)
        return temp_path
    
    def test_processor_initialization(self):
        """Test AI processor initialization"""
        self.assertIsNotNone(self.processor)
        self.assertIsNotNone(self.processor.supported_frameworks)
        self.assertIn('react', self.processor.supported_frameworks)
        self.assertIn('vue', self.processor.supported_frameworks)
        self.assertIn('html', self.processor.supported_frameworks)
    
    def test_image_analysis(self):
        """Test image analysis functionality"""
        if not self.test_image_path:
            self.skipTest("Test image not available")
        
        analysis = self.processor._analyze_image(self.test_image_path)
        
        self.assertIsInstance(analysis, dict)
        self.assertIn('dimensions', analysis)
        self.assertIn('mode', analysis)
        self.assertEqual(analysis['dimensions'], (400, 300))
    
    def test_component_detection(self):
        """Test UI component detection"""
        if not self.test_image_path:
            self.skipTest("Test image not available")
        
        image_analysis = {'dimensions': (400, 300), 'mode': 'RGB'}
        components = self.processor._detect_ui_components(self.test_image_path, image_analysis)
        
        self.assertIsInstance(components, list)
        self.assertGreater(len(components), 0)
        
        # Check component structure
        for component in components:
            self.assertIn('type', component)
            self.assertIn('bounds', component)
            self.assertIn('confidence', component)
    
    def test_layout_analysis(self):
        """Test layout analysis"""
        mock_components = [
            {'type': 'header', 'bounds': {'x': 0, 'y': 0, 'width': 400, 'height': 50}},
            {'type': 'button', 'bounds': {'x': 20, 'y': 70, 'width': 100, 'height': 30}}
        ]
        
        layout = self.processor._analyze_layout(mock_components)
        
        self.assertIsInstance(layout, dict)
        self.assertIn('type', layout)
        self.assertIn('direction', layout)
    
    def test_style_extraction(self):
        """Test style extraction"""
        if not self.test_image_path:
            self.skipTest("Test image not available")
        
        mock_components = []
        styles = self.processor._extract_styles(self.test_image_path, mock_components)
        
        self.assertIsInstance(styles, dict)
        self.assertIn('theme', styles)
        self.assertIn('typography', styles)
        self.assertIn('spacing', styles)
    
    def test_code_generation_react(self):
        """Test React code generation"""
        mock_components = [
            {
                'type': 'header',
                'text': 'Test Header',
                'bounds': {'x': 0, 'y': 0, 'width': 400, 'height': 50}
            }
        ]
        mock_layout = {'type': 'flexbox', 'direction': 'column'}
        mock_styles = {
            'theme': {'primary_color': '#2196F3'},
            'typography': {'font_family': 'Arial', 'font_sizes': {'medium': '14px'}}
        }
        
        code = self.processor._generate_react_code(mock_components, mock_layout, mock_styles)
        
        self.assertIsInstance(code, str)
        self.assertIn('import React', code)
        self.assertIn('export default', code)
        self.assertIn('Test Header', code)
    
    def test_code_generation_vue(self):
        """Test Vue.js code generation"""
        mock_components = [
            {
                'type': 'button',
                'text': 'Test Button',
                'bounds': {'x': 20, 'y': 70, 'width': 100, 'height': 30}
            }
        ]
        mock_layout = {'type': 'flexbox', 'direction': 'column'}
        mock_styles = {
            'theme': {'secondary_color': '#4CAF50'},
            'typography': {'font_family': 'Arial', 'font_sizes': {'medium': '14px'}}
        }
        
        code = self.processor._generate_vue_code(mock_components, mock_layout, mock_styles)
        
        self.assertIsInstance(code, str)
        self.assertIn('<template>', code)
        self.assertIn('export default', code)
        self.assertIn('Test Button', code)
    
    def test_code_generation_html(self):
        """Test HTML/CSS code generation"""
        mock_components = [
            {
                'type': 'text',
                'text': 'Test Text',
                'bounds': {'x': 20, 'y': 120, 'width': 200, 'height': 20}
            }
        ]
        mock_layout = {'type': 'flexbox', 'direction': 'column'}
        mock_styles = {
            'theme': {'text_color': '#333333'},
            'typography': {'font_family': 'Arial', 'font_sizes': {'medium': '14px'}}
        }
        
        code = self.processor._generate_html_code(mock_components, mock_layout, mock_styles)
        
        self.assertIsInstance(code, str)
        self.assertIn('<!DOCTYPE html>', code)
        self.assertIn('<style>', code)
        self.assertIn('Test Text', code)
    
    def test_full_processing_pipeline(self):
        """Test the complete processing pipeline"""
        if not self.test_image_path:
            self.skipTest("Test image not available")
        
        # Track progress updates
        progress_updates = []
        
        def progress_callback(stage, progress, message, user_options=None):
            progress_updates.append({
                'stage': stage,
                'progress': progress,
                'message': message,
                'user_options': user_options
            })
        
        from nextcloud_music_player.ai_processor import ProgressCallback
        callback = ProgressCallback(progress_callback)
        
        result = self.processor.process_screenshot(
            self.test_image_path,
            'react',
            callback
        )
        
        # Check result structure
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('code', result)
        self.assertIn('framework', result)
        self.assertIn('components', result)
        self.assertIn('steps', result)
        
        # Check progress updates
        self.assertGreater(len(progress_updates), 0)
        self.assertTrue(any(update['stage'] == 'image_analysis' for update in progress_updates))
        self.assertTrue(any(update['stage'] == 'code_generation' for update in progress_updates))
    
    def test_unsupported_framework(self):
        """Test handling of unsupported framework"""
        if not self.test_image_path:
            self.skipTest("Test image not available")
        
        result = self.processor.process_screenshot(
            self.test_image_path,
            'unsupported_framework'
        )
        
        self.assertIsInstance(result, dict)
        # Should still process but with basic code generation


class TestProgressCallback(unittest.TestCase):
    """Test the progress callback functionality"""
    
    def test_callback_initialization(self):
        """Test callback initialization"""
        from nextcloud_music_player.ai_processor import ProgressCallback
        
        # Test with callback function
        def dummy_callback(stage, progress, message, user_options=None):
            pass
        
        callback = ProgressCallback(dummy_callback)
        self.assertEqual(callback.callback_func, dummy_callback)
        
        # Test without callback function
        callback_none = ProgressCallback()
        self.assertIsNone(callback_none.callback_func)
    
    def test_callback_update(self):
        """Test callback update functionality"""
        from nextcloud_music_player.ai_processor import ProgressCallback
        
        updates = []
        
        def test_callback(stage, progress, message, user_options=None):
            updates.append({
                'stage': stage,
                'progress': progress,
                'message': message,
                'user_options': user_options
            })
        
        callback = ProgressCallback(test_callback)
        callback.update('test_stage', 0.5, 'Test message', {'option': 'value'})
        
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]['stage'], 'test_stage')
        self.assertEqual(updates[0]['progress'], 0.5)
        self.assertEqual(updates[0]['message'], 'Test message')
        self.assertEqual(updates[0]['user_options'], {'option': 'value'})


class TestSupportedFrameworks(unittest.TestCase):
    """Test supported framework configurations"""
    
    def setUp(self):
        """Set up test fixtures"""
        from nextcloud_music_player.ai_processor import AIProcessor
        self.processor = AIProcessor()
    
    def test_framework_definitions(self):
        """Test that all frameworks are properly defined"""
        frameworks = self.processor.supported_frameworks
        
        expected_frameworks = ['react', 'vue', 'html', 'flutter', 'swift']
        
        for framework in expected_frameworks:
            self.assertIn(framework, frameworks)
            self.assertIn('name', frameworks[framework])
            self.assertIn('extension', frameworks[framework])
    
    def test_framework_extensions(self):
        """Test framework file extensions"""
        frameworks = self.processor.supported_frameworks
        
        expected_extensions = {
            'react': '.jsx',
            'vue': '.vue',
            'html': '.html',
            'flutter': '.dart',
            'swift': '.swift'
        }
        
        for framework, expected_ext in expected_extensions.items():
            self.assertEqual(
                frameworks[framework]['extension'],
                expected_ext
            )


class TestErrorHandling(unittest.TestCase):
    """Test error handling in the AI processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        from nextcloud_music_player.ai_processor import AIProcessor
        self.processor = AIProcessor()
    
    def test_invalid_image_path(self):
        """Test handling of invalid image path"""
        result = self.processor.process_screenshot(
            '/nonexistent/path/image.png',
            'react'
        )
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get('success', True))
        self.assertIn('error', result)
    
    def test_image_analysis_error_handling(self):
        """Test error handling in image analysis"""
        analysis = self.processor._analyze_image('/nonexistent/path/image.png')
        
        self.assertIsInstance(analysis, dict)
        self.assertIn('error', analysis)


if __name__ == '__main__':
    unittest.main()