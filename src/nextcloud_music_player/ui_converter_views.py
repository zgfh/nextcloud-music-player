"""
Screenshot to UI Converter Views

UI components for the screenshot to UI converter application
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER
import asyncio
import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScreenshotUploaderView:
    """View for uploading or capturing screenshots"""
    
    def __init__(self, app):
        self.app = app
        self.current_image_path = None
        self.create_ui()
    
    def create_ui(self):
        """Create the screenshot uploader interface"""
        
        # Title
        self.title = toga.Label(
            "📸 Screenshot to UI Converter",
            style=Pack(
                font_size=24,
                font_weight="bold",
                text_align="center",
                padding=(20, 10)
            )
        )
        
        # Subtitle
        self.subtitle = toga.Label(
            "Upload a screenshot to generate optimized UI code using AI",
            style=Pack(
                font_size=14,
                text_align="center",
                padding=(0, 10, 20, 10),
                color="#666666"
            )
        )
        
        # Image preview
        self.image_preview = toga.ImageView(
            style=Pack(
                width=300,
                height=200,
                padding=10,
                background_color="#f0f0f0"
            )
        )
        
        # Upload button
        self.upload_button = toga.Button(
            "📁 Select Screenshot",
            on_press=self.select_screenshot,
            style=Pack(
                padding=10,
                background_color="#2196F3",
                color="#FFFFFF",
                font_size=16
            )
        )
        
        # Status label
        self.status_label = toga.Label(
            "No image selected",
            style=Pack(
                padding=10,
                text_align="center",
                color="#666666"
            )
        )
        
        # Framework selection
        self.framework_label = toga.Label(
            "Target Framework:",
            style=Pack(padding=(20, 10, 5, 10), font_weight="bold")
        )
        
        self.framework_selection = toga.Selection(
            items=["React", "Vue.js", "HTML/CSS", "Flutter", "Swift UI"],
            style=Pack(padding=(0, 10, 10, 10), width=200)
        )
        self.framework_selection.value = "React"
        
        # Process button
        self.process_button = toga.Button(
            "🚀 Generate UI Code",
            on_press=self.start_processing,
            enabled=False,
            style=Pack(
                padding=20,
                background_color="#4CAF50",
                color="#FFFFFF",
                font_size=18,
                font_weight="bold"
            )
        )
        
        # Container
        self.container = toga.ScrollContainer(
            content=toga.Box(
                children=[
                    self.title,
                    self.subtitle,
                    self.image_preview,
                    self.upload_button,
                    self.status_label,
                    self.framework_label,
                    self.framework_selection,
                    self.process_button,
                ],
                style=Pack(
                    direction=COLUMN,
                    alignment=CENTER,
                    padding=20
                )
            )
        )
    
    async def select_screenshot(self, widget):
        """Handle screenshot selection"""
        try:
            # In a real implementation, this would open a file dialog
            # For now, we'll create a sample image path
            sample_image_path = await self.create_sample_image()
            
            if sample_image_path:
                self.current_image_path = sample_image_path
                self.status_label.text = f"✅ Image loaded: {os.path.basename(sample_image_path)}"
                self.process_button.enabled = True
                
                # Try to load the image preview
                try:
                    self.image_preview.image = toga.Image(sample_image_path)
                except Exception as e:
                    logger.warning(f"Could not load image preview: {e}")
                
        except Exception as e:
            self.status_label.text = f"❌ Error loading image: {e}"
            logger.error(f"Error selecting screenshot: {e}")
    
    async def create_sample_image(self):
        """Create a sample image for demonstration"""
        try:
            # Create a sample image using PIL if available
            try:
                from PIL import Image, ImageDraw, ImageFont
                PIL_AVAILABLE = True
            except ImportError:
                PIL_AVAILABLE = False
            
            if PIL_AVAILABLE:
                # Create a sample UI screenshot
                img = Image.new('RGB', (400, 300), color='white')
                draw = ImageDraw.Draw(img)
                
                # Draw a simple UI mockup
                # Header
                draw.rectangle([0, 0, 400, 60], fill='#2196F3')
                draw.text((20, 20), "Sample App Header", fill='white')
                
                # Button
                draw.rectangle([20, 80, 140, 120], fill='#4CAF50')
                draw.text((50, 95), "Button", fill='white')
                
                # Text
                draw.text((20, 140), "This is sample text content", fill='black')
                
                # Input field
                draw.rectangle([20, 170, 220, 200], outline='#cccccc', width=2)
                draw.text((25, 180), "Input field...", fill='#999999')
                
                # Save to temp file
                temp_path = os.path.join(tempfile.gettempdir(), "sample_ui_screenshot.png")
                img.save(temp_path)
                return temp_path
            else:
                # If PIL is not available, create a text file as placeholder
                temp_path = os.path.join(tempfile.gettempdir(), "sample_screenshot.txt")
                with open(temp_path, 'w') as f:
                    f.write("Sample screenshot placeholder - PIL not available")
                return temp_path
                
        except Exception as e:
            logger.error(f"Error creating sample image: {e}")
            return None
    
    async def start_processing(self, widget):
        """Start the AI processing pipeline"""
        if not self.current_image_path:
            self.status_label.text = "❌ No image selected"
            return
        
        try:
            # Get selected framework
            framework_map = {
                "React": "react",
                "Vue.js": "vue", 
                "HTML/CSS": "html",
                "Flutter": "flutter",
                "Swift UI": "swift"
            }
            
            selected_framework = framework_map.get(self.framework_selection.value, "react")
            
            # Switch to processing view
            if hasattr(self.app, 'view_manager'):
                await self.app.view_manager.start_processing(
                    self.current_image_path, 
                    selected_framework
                )
            
        except Exception as e:
            self.status_label.text = f"❌ Error starting processing: {e}"
            logger.error(f"Error starting processing: {e}")


class ProcessingView:
    """View for showing AI processing progress"""
    
    def __init__(self, app):
        self.app = app
        self.current_stage = ""
        self.current_progress = 0.0
        self.user_selections = {}
        self.create_ui()
    
    def create_ui(self):
        """Create the processing interface"""
        
        # Title
        self.title = toga.Label(
            "🤖 AI Processing Pipeline",
            style=Pack(
                font_size=20,
                font_weight="bold",
                text_align="center",
                padding=(20, 10)
            )
        )
        
        # Current stage
        self.stage_label = toga.Label(
            "Initializing...",
            style=Pack(
                font_size=16,
                text_align="center",
                padding=10,
                font_weight="bold"
            )
        )
        
        # Progress bar (simulated with label for now)
        self.progress_label = toga.Label(
            "Progress: 0%",
            style=Pack(
                text_align="center",
                padding=10,
                background_color="#f0f0f0"
            )
        )
        
        # Progress details
        self.details_label = toga.Label(
            "",
            style=Pack(
                text_align="center",
                padding=10,
                color="#666666"
            )
        )
        
        # User selection area
        self.selection_label = toga.Label(
            "",
            style=Pack(
                padding=10,
                font_weight="bold"
            )
        )
        
        self.selection_box = toga.Box(
            style=Pack(direction=COLUMN, padding=10)
        )
        
        # Action buttons
        self.action_buttons = toga.Box(
            style=Pack(direction=ROW, padding=10)
        )
        
        # Log area
        self.log_area = toga.MultilineTextInput(
            readonly=True,
            style=Pack(
                height=200,
                padding=10
            )
        )
        
        # Container
        self.container = toga.ScrollContainer(
            content=toga.Box(
                children=[
                    self.title,
                    self.stage_label,
                    self.progress_label,
                    self.details_label,
                    self.selection_label,
                    self.selection_box,
                    self.action_buttons,
                    toga.Label("Processing Log:", style=Pack(padding=(20, 10, 5, 10), font_weight="bold")),
                    self.log_area,
                ],
                style=Pack(
                    direction=COLUMN,
                    padding=20
                )
            )
        )
    
    def update_progress(self, stage: str, progress: float, message: str, user_options: Optional[Dict] = None):
        """Update the processing progress"""
        self.current_stage = stage
        self.current_progress = progress
        
        # Update UI elements
        stage_names = {
            "image_analysis": "🔍 Analyzing Image",
            "component_detection": "🎯 Detecting Components", 
            "layout_analysis": "📐 Analyzing Layout",
            "style_extraction": "🎨 Extracting Styles",
            "code_generation": "💻 Generating Code",
            "finalization": "✅ Finalizing",
            "error": "❌ Error"
        }
        
        self.stage_label.text = stage_names.get(stage, f"Processing: {stage}")
        self.progress_label.text = f"Progress: {progress:.1%}"
        self.details_label.text = message
        
        # Add to log
        log_entry = f"[{stage.upper()}] {progress:.1%}: {message}\n"
        self.log_area.value += log_entry
        
        # Handle user selection options
        if user_options:
            self.show_user_options(user_options)
        else:
            self.clear_user_options()
    
    def show_user_options(self, options: Dict):
        """Show user selection options"""
        self.selection_label.text = options.get("message", "Please select an option:")
        
        # Clear existing options
        self.selection_box.clear()
        self.action_buttons.clear()
        
        option_values = options.get("options", [])
        default_value = options.get("default", option_values[0] if option_values else None)
        
        # Create selection widget
        if len(option_values) > 1:
            selection = toga.Selection(
                items=option_values,
                style=Pack(padding=5, width=200)
            )
            selection.value = default_value
            self.selection_box.add(selection)
            
            # Add continue button
            continue_button = toga.Button(
                "Continue",
                on_press=lambda w: self.handle_user_selection(selection.value),
                style=Pack(padding=5, background_color="#4CAF50", color="#FFFFFF")
            )
            self.action_buttons.add(continue_button)
        
        # Add auto-continue button
        auto_button = toga.Button(
            f"Auto ({default_value})",
            on_press=lambda w: self.handle_user_selection(default_value),
            style=Pack(padding=5, background_color="#2196F3", color="#FFFFFF")
        )
        self.action_buttons.add(auto_button)
    
    def clear_user_options(self):
        """Clear user selection options"""
        self.selection_label.text = ""
        self.selection_box.clear()
        self.action_buttons.clear()
    
    def handle_user_selection(self, selection: str):
        """Handle user selection and continue processing"""
        self.user_selections[self.current_stage] = selection
        self.clear_user_options()
        
        # Log the selection
        log_entry = f"User selected: {selection}\n"
        self.log_area.value += log_entry
        
        # Continue processing (this would normally trigger the next AI processing step)
        # For now, we'll just log it
        logger.info(f"User selected {selection} for stage {self.current_stage}")


class CodeOutputView:
    """View for displaying generated code"""
    
    def __init__(self, app):
        self.app = app
        self.generated_code = ""
        self.result_data = {}
        self.create_ui()
    
    def create_ui(self):
        """Create the code output interface"""
        
        # Title
        self.title = toga.Label(
            "📄 Generated UI Code",
            style=Pack(
                font_size=20,
                font_weight="bold",
                text_align="center",
                padding=(20, 10)
            )
        )
        
        # Framework info
        self.framework_label = toga.Label(
            "",
            style=Pack(
                text_align="center",
                padding=10,
                color="#666666"
            )
        )
        
        # Code area
        self.code_area = toga.MultilineTextInput(
            readonly=True,
            style=Pack(
                height=400,
                padding=10,
                font_family="monospace"
            )
        )
        
        # Copy button
        self.copy_button = toga.Button(
            "📋 Copy to Clipboard",
            on_press=self.copy_code,
            style=Pack(
                padding=10,
                background_color="#2196F3",
                color="#FFFFFF"
            )
        )
        
        # Save button
        self.save_button = toga.Button(
            "💾 Save to File",
            on_press=self.save_code,
            style=Pack(
                padding=10,
                background_color="#4CAF50",
                color="#FFFFFF"
            )
        )
        
        # New conversion button
        self.new_button = toga.Button(
            "🔄 New Conversion",
            on_press=self.start_new_conversion,
            style=Pack(
                padding=10,
                background_color="#FF9800",
                color="#FFFFFF"
            )
        )
        
        # Button box
        button_box = toga.Box(
            children=[self.copy_button, self.save_button, self.new_button],
            style=Pack(direction=ROW, padding=10)
        )
        
        # Metadata section
        self.metadata_label = toga.Label(
            "Generation Details:",
            style=Pack(
                padding=(20, 10, 5, 10),
                font_weight="bold"
            )
        )
        
        self.metadata_area = toga.MultilineTextInput(
            readonly=True,
            style=Pack(
                height=100,
                padding=10
            )
        )
        
        # Container
        self.container = toga.ScrollContainer(
            content=toga.Box(
                children=[
                    self.title,
                    self.framework_label,
                    self.code_area,
                    button_box,
                    self.metadata_label,
                    self.metadata_area,
                ],
                style=Pack(
                    direction=COLUMN,
                    padding=20
                )
            )
        )
    
    def set_result(self, result_data: Dict[str, Any]):
        """Set the generated code result"""
        self.result_data = result_data
        self.generated_code = result_data.get("code", "")
        
        # Update UI
        framework = result_data.get("framework", "unknown")
        self.framework_label.text = f"Framework: {framework.upper()}"
        self.code_area.value = self.generated_code
        
        # Update metadata
        metadata = result_data.get("metadata", {})
        components = result_data.get("components", [])
        
        metadata_text = f"""Components detected: {len(components)}
Framework: {framework}
Image dimensions: {metadata.get('image_dimensions', 'Unknown')}
Processing steps: {len(result_data.get('steps', []))}
Success: {result_data.get('success', False)}"""
        
        self.metadata_area.value = metadata_text
    
    async def copy_code(self, widget):
        """Copy code to clipboard"""
        try:
            # In a real implementation, this would copy to system clipboard
            # For now, we'll just show a message
            self.framework_label.text = "✅ Code copied to clipboard!"
            
            # Reset message after delay
            await asyncio.sleep(2)
            framework = self.result_data.get("framework", "unknown")
            self.framework_label.text = f"Framework: {framework.upper()}"
            
        except Exception as e:
            logger.error(f"Error copying code: {e}")
    
    async def save_code(self, widget):
        """Save code to file"""
        try:
            # Create a temporary file with the generated code
            framework = self.result_data.get("framework", "unknown")
            extension_map = {
                "react": ".jsx",
                "vue": ".vue",
                "html": ".html",
                "flutter": ".dart",
                "swift": ".swift"
            }
            
            extension = extension_map.get(framework, ".txt")
            filename = f"generated_ui_{framework}{extension}"
            filepath = os.path.join(tempfile.gettempdir(), filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.generated_code)
            
            self.framework_label.text = f"✅ Code saved to: {filepath}"
            
            # Reset message after delay
            await asyncio.sleep(3)
            self.framework_label.text = f"Framework: {framework.upper()}"
            
        except Exception as e:
            self.framework_label.text = f"❌ Error saving file: {e}"
            logger.error(f"Error saving code: {e}")
    
    async def start_new_conversion(self, widget):
        """Start a new conversion"""
        if hasattr(self.app, 'view_manager'):
            await self.app.view_manager.switch_to_upload()


class ViewManager:
    """Manages different views in the application"""
    
    def __init__(self, app):
        self.app = app
        self.uploader_view = ScreenshotUploaderView(app)
        self.processing_view = ProcessingView(app)
        self.output_view = CodeOutputView(app)
        
        # Create main container with tab navigation
        self.main_container = toga.OptionContainer(
            content=[
                ("📸 Upload", self.uploader_view.container),
                ("🤖 Processing", self.processing_view.container),
                ("📄 Output", self.output_view.container),
            ],
            style=Pack(flex=1)
        )
        
        # Start with upload view
        self.main_container.current_tab = 0
    
    async def start_processing(self, image_path: str, framework: str):
        """Start the AI processing pipeline"""
        # Switch to processing view
        self.main_container.current_tab = 1
        
        # Initialize AI processor
        from .ai_processor import AIProcessor, ProgressCallback
        
        ai_processor = AIProcessor()
        
        # Create progress callback
        progress_callback = ProgressCallback(self.processing_view.update_progress)
        
        try:
            # Start processing
            result = ai_processor.process_screenshot(
                image_path, 
                framework, 
                progress_callback
            )
            
            # Show results
            if result.get("success"):
                self.output_view.set_result(result)
                self.main_container.current_tab = 2
            else:
                error_msg = result.get("error", "Unknown error occurred")
                self.processing_view.update_progress("error", 0.0, f"Processing failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error in processing pipeline: {e}")
            self.processing_view.update_progress("error", 0.0, f"Processing error: {e}")
        
        finally:
            # Cleanup
            ai_processor.cleanup()
    
    async def switch_to_upload(self):
        """Switch to upload view"""
        self.main_container.current_tab = 0