"""
Project scaffolding automation tool.

This tool provides automated project scaffolding and setup functionality.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict
from .base import BaseTool


class ProjectScaffoldingTool(BaseTool):
    """Tool for automating project scaffolding tasks."""
    
    @property
    def name(self) -> str:
        return "project_scaffolding"
    
    @property
    def description(self) -> str:
        return "Automate project scaffolding tasks like creating new components, views, or services"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_view", "create_service", "create_component", "setup_platform"],
                    "description": "The scaffolding action to perform"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the item to create"
                },
                "platform": {
                    "type": "string",
                    "enum": ["ios", "android", "web", "desktop"],
                    "description": "Target platform (for platform-specific scaffolding)"
                },
                "template": {
                    "type": "string",
                    "description": "Template to use for scaffolding"
                }
            },
            "required": ["action", "name"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the scaffolding action."""
        if not self.validate_project_root():
            return {"error": "Invalid project root"}
        
        action = arguments.get("action")
        name = arguments.get("name")
        platform = arguments.get("platform", "desktop")
        template = arguments.get("template", "default")
        
        try:
            if action == "create_view":
                return await self._create_view(name, template)
            elif action == "create_service":
                return await self._create_service(name, template)
            elif action == "create_component":
                return await self._create_component(name, template)
            elif action == "setup_platform":
                return await self._setup_platform(platform)
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            self.logger.error(f"Error in scaffolding: {e}")
            return {"error": str(e)}
    
    async def _create_view(self, name: str, template: str) -> Dict[str, Any]:
        """Create a new view."""
        view_name = f"{name.lower()}_view"
        class_name = f"{''.join(word.capitalize() for word in name.split('_'))}View"
        
        # Create view file
        view_content = f'''"""
{class_name} - {name.title()} view for NextCloud Music Player.

This view handles {name.lower()} functionality.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW


class {class_name}:
    """View for {name.lower()} functionality."""
    
    def __init__(self, app):
        """
        Initialize the {name.lower()} view.
        
        Args:
            app: The main application instance
        """
        self.app = app
        self.container = None
        self._create_ui()
    
    def _create_ui(self):
        """Create the user interface."""
        # Title
        title_label = toga.Label(
            "{name.title()}",
            style=Pack(
                padding=(10, 0),
                text_align="center",
                font_size=16,
                font_weight="bold"
            )
        )
        
        # Content area
        content_label = toga.Label(
            "This is the {name.lower()} view content.",
            style=Pack(padding=10)
        )
        
        # Action button
        action_button = toga.Button(
            "{name.title()} Action",
            on_press=self.on_action,
            style=Pack(padding=10)
        )
        
        # Create main container
        self.container = toga.Box(
            children=[
                title_label,
                content_label,
                action_button
            ],
            style=Pack(
                direction=COLUMN,
                padding=10
            )
        )
    
    async def on_action(self, widget):
        """Handle action button press."""
        await self.app.main_window.info_dialog(
            "{name.title()} Action",
            "Action button pressed!"
        )
    
    def get_container(self):
        """Get the view container."""
        return self.container
'''
        
        view_path = self.project_root / "src" / "nextcloud_music_player" / "views" / f"{view_name}.py"
        
        if not self.write_file(view_path, view_content):
            return {"error": f"Failed to create view file: {view_path}"}
        
        # Update __init__.py
        init_path = self.project_root / "src" / "nextcloud_music_player" / "views" / "__init__.py"
        try:
            init_content = self.read_file(init_path)
            if f"from .{view_name} import {class_name}" not in init_content:
                # Add import
                lines = init_content.splitlines()
                import_line = f"from .{view_name} import {class_name}"
                
                # Find where to insert the import
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.startswith("from ."):
                        insert_index = i + 1
                
                lines.insert(insert_index, import_line)
                
                # Update __all__ if it exists
                for i, line in enumerate(lines):
                    if line.strip().startswith("__all__"):
                        # Find the end of __all__
                        for j in range(i, len(lines)):
                            if "]" in lines[j]:
                                # Insert before the closing bracket
                                lines[j] = lines[j].replace("]", f', "{class_name}"]')
                                break
                        break
                
                new_content = "\\n".join(lines)
                self.write_file(init_path, new_content)
        
        except Exception as e:
            self.logger.warning(f"Could not update __init__.py: {e}")
        
        return {
            "success": True,
            "message": f"Created view: {class_name}",
            "files_created": [str(view_path)]
        }
    
    async def _create_service(self, name: str, template: str) -> Dict[str, Any]:
        """Create a new service."""
        service_name = f"{name.lower()}_service"
        class_name = f"{''.join(word.capitalize() for word in name.split('_'))}Service"
        
        service_content = f'''"""
{class_name} - {name.title()} service for NextCloud Music Player.

This service handles {name.lower()} business logic.
"""

import logging
from typing import Any, Dict, List, Optional


class {class_name}:
    """Service for {name.lower()} functionality."""
    
    def __init__(self, app):
        """
        Initialize the {name.lower()} service.
        
        Args:
            app: The main application instance
        """
        self.app = app
        self.logger = logging.getLogger(f"{{__name__}}.{{self.__class__.__name__}}")
        self._initialize()
    
    def _initialize(self):
        """Initialize the service."""
        self.logger.info("Initializing {name.lower()} service")
        # Add service initialization logic here
    
    async def process_{name.lower()}(self, data: Any) -> Dict[str, Any]:
        """
        Process {name.lower()} data.
        
        Args:
            data: Input data to process
            
        Returns:
            Processing result
        """
        try:
            self.logger.info(f"Processing {name.lower()} data: {{data}}")
            
            # Add processing logic here
            result = {{
                "success": True,
                "message": f"{name.title()} processed successfully",
                "data": data
            }}
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error processing {name.lower()}: {{e}}")
            return {{
                "success": False,
                "error": str(e)
            }}
    
    def get_{name.lower()}_info(self) -> Dict[str, Any]:
        """
        Get {name.lower()} information.
        
        Returns:
            Service information
        """
        return {{
            "service": "{name.lower()}",
            "status": "active",
            "version": "1.0.0"
        }}
'''
        
        service_path = self.project_root / "src" / "nextcloud_music_player" / "services" / f"{service_name}.py"
        
        if not self.write_file(service_path, service_content):
            return {"error": f"Failed to create service file: {service_path}"}
        
        return {
            "success": True,
            "message": f"Created service: {class_name}",
            "files_created": [str(service_path)]
        }
    
    async def _create_component(self, name: str, template: str) -> Dict[str, Any]:
        """Create a new component."""
        component_name = f"{name.lower()}_component"
        class_name = f"{''.join(word.capitalize() for word in name.split('_'))}Component"
        
        component_content = f'''"""
{class_name} - {name.title()} component for NextCloud Music Player.

This component provides reusable {name.lower()} UI functionality.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW


class {class_name}:
    """Reusable {name.lower()} component."""
    
    def __init__(self, app, **kwargs):
        """
        Initialize the {name.lower()} component.
        
        Args:
            app: The main application instance
            **kwargs: Additional component options
        """
        self.app = app
        self.options = kwargs
        self.container = None
        self._create_component()
    
    def _create_component(self):
        """Create the component UI."""
        # Component label
        label = toga.Label(
            f"{name.title()} Component",
            style=Pack(
                padding=5,
                font_weight="bold"
            )
        )
        
        # Component content
        content = toga.Label(
            "This is a reusable {name.lower()} component.",
            style=Pack(padding=5)
        )
        
        # Component button
        button = toga.Button(
            "Component Action",
            on_press=self.on_component_action,
            style=Pack(padding=5)
        )
        
        # Create container
        self.container = toga.Box(
            children=[label, content, button],
            style=Pack(
                direction=COLUMN,
                padding=5
            )
        )
    
    async def on_component_action(self, widget):
        """Handle component action."""
        await self.app.main_window.info_dialog(
            "{name.title()} Component",
            "Component action triggered!"
        )
    
    def get_widget(self):
        """Get the component widget."""
        return self.container
    
    def update_content(self, new_content: str):
        """Update component content."""
        # Implementation for updating component content
        pass
'''
        
        components_dir = self.project_root / "src" / "nextcloud_music_player" / "views" / "components"
        components_dir.mkdir(parents=True, exist_ok=True)
        
        component_path = components_dir / f"{component_name}.py"
        
        if not self.write_file(component_path, component_content):
            return {"error": f"Failed to create component file: {component_path}"}
        
        return {
            "success": True,
            "message": f"Created component: {class_name}",
            "files_created": [str(component_path)]
        }
    
    async def _setup_platform(self, platform: str) -> Dict[str, Any]:
        """Setup platform-specific configuration."""
        if platform == "ios":
            return await self._setup_ios()
        elif platform == "android":
            return await self._setup_android()
        elif platform == "web":
            return await self._setup_web()
        else:
            return {"error": f"Unsupported platform: {platform}"}
    
    async def _setup_ios(self) -> Dict[str, Any]:
        """Setup iOS-specific configuration."""
        # Create iOS-specific files and configurations
        result = self.run_command("python -m briefcase create iOS")
        
        if result["success"]:
            return {
                "success": True,
                "message": "iOS platform setup completed",
                "output": result["stdout"]
            }
        else:
            return {
                "success": False,
                "error": result["stderr"],
                "output": result["stdout"]
            }
    
    async def _setup_android(self) -> Dict[str, Any]:
        """Setup Android-specific configuration."""
        # Create Android-specific files and configurations
        result = self.run_command("python -m briefcase create android")
        
        if result["success"]:
            return {
                "success": True,
                "message": "Android platform setup completed",
                "output": result["stdout"]
            }
        else:
            return {
                "success": False,
                "error": result["stderr"],
                "output": result["stdout"]
            }
    
    async def _setup_web(self) -> Dict[str, Any]:
        """Setup Web-specific configuration."""
        # Create Web-specific files and configurations
        result = self.run_command("python -m briefcase create web")
        
        if result["success"]:
            return {
                "success": True,
                "message": "Web platform setup completed", 
                "output": result["stdout"]
            }
        else:
            return {
                "success": False,
                "error": result["stderr"],
                "output": result["stdout"]
            }