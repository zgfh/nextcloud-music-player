"""
Screenshot to UI Converter - Main Application

AI-powered tool for converting screenshots to optimized UI code using
Stable Diffusion, ControlNet, and code generation models.

Main responsibilities:
1. Application initialization and setup
2. AI model integration
3. Step-by-step processing pipeline with user interaction
4. Code generation and optimization

"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import os
from pathlib import Path
import tempfile
import logging
from typing import Optional

from .ai_processor import AIProcessor
from .ui_converter_views import ViewManager



class ScreenshotToUIConverter(toga.App):
    """Screenshot to UI Converter main application class"""

    def startup(self):
        """Application startup initialization"""
        # Set up logging system
        self.setup_logging()
        
        # Initialize AI processor
        self.ai_processor = None
        
        # Create main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        
        # Create view manager
        self.view_manager = ViewManager(self)
        
        # Set main window content
        self.main_window.content = self.view_manager.main_container
        self.main_window.show()
        
        self.logger.info("✅ Screenshot to UI Converter initialized successfully")

    def setup_logging(self):
        """Set up logging system"""
        try:
            # Create log directory
            log_dir = Path.home() / ".screenshot_to_ui" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / 'screenshot_to_ui.log'
            
            # Set up handlers
            handlers = [logging.StreamHandler()]  # Console output
            
            try:
                handlers.append(logging.FileHandler(str(log_file)))
            except (PermissionError, OSError) as e:
                logging.warning(f"⚠️ Cannot create log file {log_file}: {e}")
                logging.info("📝 Using console logging only")
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=handlers
            )
            self.logger = logging.getLogger(__name__)
            self.logger.info("✅ Logging system initialized")
            
        except Exception as e:
            # Fallback to basic console logging
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"❌ Failed to set up logging system: {e}")

    def get_ai_processor(self) -> AIProcessor:
        """Get or create AI processor instance"""
        if self.ai_processor is None:
            self.ai_processor = AIProcessor()
            self.logger.info("✅ AI processor initialized")
        return self.ai_processor

    def cleanup(self):
        """Clean up resources"""
        if self.ai_processor:
            self.ai_processor.cleanup()
            self.logger.info("✅ AI processor cleaned up")

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()



def main():
    return ScreenshotToUIConverter()
