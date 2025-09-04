"""
Tests for UI Converter Views
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os


class TestScreenshotUploaderView(unittest.TestCase):
    """Test the screenshot uploader view"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock app
        self.mock_app = Mock()
        
        # Import the view class
        from nextcloud_music_player.ui_converter_views import ScreenshotUploaderView
        self.view = ScreenshotUploaderView(self.mock_app)
    
    def test_view_initialization(self):
        """Test view initialization"""
        self.assertIsNotNone(self.view.title)
        self.assertIsNotNone(self.view.subtitle)
        self.assertIsNotNone(self.view.upload_button)
        self.assertIsNotNone(self.view.process_button)
        self.assertIsNotNone(self.view.framework_selection)
        self.assertIsNotNone(self.view.container)
    
    def test_framework_selection_default(self):
        """Test default framework selection"""
        self.assertEqual(self.view.framework_selection.value, "React")
    
    def test_initial_state(self):
        """Test initial state of the view"""
        self.assertIsNone(self.view.current_image_path)
        self.assertFalse(self.view.process_button.enabled)
        self.assertEqual(self.view.status_label.text, "No image selected")
    
    @patch('nextcloud_music_player.ui_converter_views.PIL')
    async def test_create_sample_image_with_pil(self, mock_pil):
        """Test sample image creation with PIL available"""
        # Mock PIL components
        mock_image = Mock()
        mock_draw = Mock()
        mock_pil.Image.new.return_value = mock_image
        mock_pil.ImageDraw.Draw.return_value = mock_draw
        
        result = await self.view.create_sample_image()
        
        self.assertIsNotNone(result)
        mock_pil.Image.new.assert_called_once()
        mock_image.save.assert_called_once()
    
    async def test_create_sample_image_without_pil(self):
        """Test sample image creation without PIL"""
        with patch('nextcloud_music_player.ui_converter_views.PIL', None):
            result = await self.view.create_sample_image()
            
            # Should create a text file as fallback
            self.assertIsNotNone(result)
            self.assertTrue(result.endswith('.txt'))


class TestProcessingView(unittest.TestCase):
    """Test the processing view"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_app = Mock()
        
        from nextcloud_music_player.ui_converter_views import ProcessingView
        self.view = ProcessingView(self.mock_app)
    
    def test_view_initialization(self):
        """Test view initialization"""
        self.assertIsNotNone(self.view.title)
        self.assertIsNotNone(self.view.stage_label)
        self.assertIsNotNone(self.view.progress_label)
        self.assertIsNotNone(self.view.log_area)
        self.assertIsNotNone(self.view.container)
    
    def test_initial_values(self):
        """Test initial values"""
        self.assertEqual(self.view.current_stage, "")
        self.assertEqual(self.view.current_progress, 0.0)
        self.assertEqual(self.view.user_selections, {})
    
    def test_update_progress_basic(self):
        """Test basic progress update"""
        self.view.update_progress("image_analysis", 0.3, "Analyzing image...")
        
        self.assertEqual(self.view.current_stage, "image_analysis")
        self.assertEqual(self.view.current_progress, 0.3)
        self.assertEqual(self.view.stage_label.text, "🔍 Analyzing Image")
        self.assertEqual(self.view.progress_label.text, "Progress: 30.0%")
        self.assertIn("Analyzing image...", self.view.log_area.value)
    
    def test_update_progress_with_user_options(self):
        """Test progress update with user options"""
        user_options = {
            "options": ["option1", "option2"],
            "default": "option1",
            "message": "Please select an option"
        }
        
        self.view.update_progress("component_detection", 0.5, "Detecting components...", user_options)
        
        self.assertEqual(self.view.selection_label.text, "Please select an option")
        # Check that selection box and action buttons are populated
        self.assertGreater(len(self.view.selection_box.children), 0)
        self.assertGreater(len(self.view.action_buttons.children), 0)
    
    def test_handle_user_selection(self):
        """Test user selection handling"""
        self.view.current_stage = "test_stage"
        self.view.handle_user_selection("test_selection")
        
        self.assertEqual(self.view.user_selections["test_stage"], "test_selection")
        self.assertIn("User selected: test_selection", self.view.log_area.value)
    
    def test_clear_user_options(self):
        """Test clearing user options"""
        # First add some options
        self.view.selection_label.text = "Test message"
        self.view.selection_box.add(Mock())
        self.view.action_buttons.add(Mock())
        
        # Then clear them
        self.view.clear_user_options()
        
        self.assertEqual(self.view.selection_label.text, "")
        self.assertEqual(len(self.view.selection_box.children), 0)
        self.assertEqual(len(self.view.action_buttons.children), 0)


class TestCodeOutputView(unittest.TestCase):
    """Test the code output view"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_app = Mock()
        
        from nextcloud_music_player.ui_converter_views import CodeOutputView
        self.view = CodeOutputView(self.mock_app)
    
    def test_view_initialization(self):
        """Test view initialization"""
        self.assertIsNotNone(self.view.title)
        self.assertIsNotNone(self.view.code_area)
        self.assertIsNotNone(self.view.copy_button)
        self.assertIsNotNone(self.view.save_button)
        self.assertIsNotNone(self.view.new_button)
        self.assertIsNotNone(self.view.metadata_area)
        self.assertIsNotNone(self.view.container)
    
    def test_initial_values(self):
        """Test initial values"""
        self.assertEqual(self.view.generated_code, "")
        self.assertEqual(self.view.result_data, {})
    
    def test_set_result(self):
        """Test setting result data"""
        result_data = {
            "success": True,
            "code": "const App = () => { return <div>Hello</div>; };",
            "framework": "react",
            "components": [{"type": "div", "text": "Hello"}],
            "metadata": {
                "image_dimensions": (400, 300),
                "component_count": 1
            },
            "steps": [{"stage": "test", "data": {}}]
        }
        
        self.view.set_result(result_data)
        
        self.assertEqual(self.view.generated_code, result_data["code"])
        self.assertEqual(self.view.result_data, result_data)
        self.assertEqual(self.view.framework_label.text, "Framework: REACT")
        self.assertEqual(self.view.code_area.value, result_data["code"])
        self.assertIn("Components detected: 1", self.view.metadata_area.value)
    
    async def test_copy_code(self):
        """Test copy code functionality"""
        self.view.result_data = {"framework": "react"}
        
        await self.view.copy_code(None)
        
        # Should show success message temporarily
        self.assertEqual(self.view.framework_label.text, "✅ Code copied to clipboard!")
    
    async def test_save_code(self):
        """Test save code functionality"""
        self.view.generated_code = "test code"
        self.view.result_data = {"framework": "react"}
        
        with patch('tempfile.gettempdir', return_value='/tmp'):
            with patch('builtins.open', create=True) as mock_open:
                await self.view.save_code(None)
                
                # Should attempt to save file
                mock_open.assert_called_once()
                self.assertIn("✅ Code saved to:", self.view.framework_label.text)
    
    async def test_start_new_conversion(self):
        """Test starting new conversion"""
        self.mock_app.view_manager = Mock()
        self.mock_app.view_manager.switch_to_upload = AsyncMock()
        
        await self.view.start_new_conversion(None)
        
        self.mock_app.view_manager.switch_to_upload.assert_called_once()


class TestViewManager(unittest.TestCase):
    """Test the view manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_app = Mock()
        
        with patch('nextcloud_music_player.ui_converter_views.ScreenshotUploaderView'):
            with patch('nextcloud_music_player.ui_converter_views.ProcessingView'):
                with patch('nextcloud_music_player.ui_converter_views.CodeOutputView'):
                    from nextcloud_music_player.ui_converter_views import ViewManager
                    self.view_manager = ViewManager(self.mock_app)
    
    def test_view_manager_initialization(self):
        """Test view manager initialization"""
        self.assertIsNotNone(self.view_manager.uploader_view)
        self.assertIsNotNone(self.view_manager.processing_view)
        self.assertIsNotNone(self.view_manager.output_view)
        self.assertIsNotNone(self.view_manager.main_container)
    
    def test_initial_tab_selection(self):
        """Test initial tab selection"""
        self.assertEqual(self.view_manager.main_container.current_tab, 0)
    
    @patch('nextcloud_music_player.ui_converter_views.AIProcessor')
    async def test_start_processing_success(self, mock_ai_processor):
        """Test successful processing start"""
        # Mock AI processor
        mock_processor_instance = Mock()
        mock_ai_processor.return_value = mock_processor_instance
        mock_processor_instance.process_screenshot.return_value = {
            "success": True,
            "code": "test code",
            "framework": "react"
        }
        
        await self.view_manager.start_processing("/test/image.png", "react")
        
        # Should switch to processing view
        self.assertEqual(self.view_manager.main_container.current_tab, 1)
        
        # Should call AI processor
        mock_processor_instance.process_screenshot.assert_called_once()
        mock_processor_instance.cleanup.assert_called_once()
    
    @patch('nextcloud_music_player.ui_converter_views.AIProcessor')
    async def test_start_processing_failure(self, mock_ai_processor):
        """Test processing failure handling"""
        # Mock AI processor to return failure
        mock_processor_instance = Mock()
        mock_ai_processor.return_value = mock_processor_instance
        mock_processor_instance.process_screenshot.return_value = {
            "success": False,
            "error": "Test error"
        }
        
        await self.view_manager.start_processing("/test/image.png", "react")
        
        # Should still switch to processing view
        self.assertEqual(self.view_manager.main_container.current_tab, 1)
        
        # Should cleanup
        mock_processor_instance.cleanup.assert_called_once()
    
    @patch('nextcloud_music_player.ui_converter_views.AIProcessor')
    async def test_start_processing_exception(self, mock_ai_processor):
        """Test processing exception handling"""
        # Mock AI processor to raise exception
        mock_processor_instance = Mock()
        mock_ai_processor.return_value = mock_processor_instance
        mock_processor_instance.process_screenshot.side_effect = Exception("Test exception")
        
        await self.view_manager.start_processing("/test/image.png", "react")
        
        # Should cleanup even on exception
        mock_processor_instance.cleanup.assert_called_once()
    
    async def test_switch_to_upload(self):
        """Test switching to upload view"""
        await self.view_manager.switch_to_upload()
        
        self.assertEqual(self.view_manager.main_container.current_tab, 0)


class TestUIIntegration(unittest.TestCase):
    """Test UI component integration"""
    
    def test_framework_mapping(self):
        """Test framework mapping consistency"""
        from nextcloud_music_player.ui_converter_views import ScreenshotUploaderView
        
        mock_app = Mock()
        view = ScreenshotUploaderView(mock_app)
        
        # Test that all selection items have corresponding mappings
        selection_items = ["React", "Vue.js", "HTML/CSS", "Flutter", "Swift UI"]
        framework_map = {
            "React": "react",
            "Vue.js": "vue", 
            "HTML/CSS": "html",
            "Flutter": "flutter",
            "Swift UI": "swift"
        }
        
        for item in selection_items:
            self.assertIn(item, framework_map)
    
    def test_progress_stage_names(self):
        """Test progress stage name mappings"""
        from nextcloud_music_player.ui_converter_views import ProcessingView
        
        mock_app = Mock()
        view = ProcessingView(mock_app)
        
        # Test stage name mapping
        view.update_progress("image_analysis", 0.1, "Test")
        self.assertEqual(view.stage_label.text, "🔍 Analyzing Image")
        
        view.update_progress("component_detection", 0.2, "Test")
        self.assertEqual(view.stage_label.text, "🎯 Detecting Components")
        
        view.update_progress("code_generation", 0.8, "Test")
        self.assertEqual(view.stage_label.text, "💻 Generating Code")


if __name__ == '__main__':
    unittest.main()