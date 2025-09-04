"""
Build automation tool.

This tool provides automated build and compilation functionality.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict
from .base import BaseTool


class BuildAutomationTool(BaseTool):
    """Tool for automating build tasks."""
    
    @property
    def name(self) -> str:
        return "build_automation"
    
    @property
    def description(self) -> str:
        return "Automate build tasks like compilation, packaging, and deployment preparation"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["build", "package", "clean", "rebuild", "dev", "update"],
                    "description": "The build action to perform"
                },
                "platform": {
                    "type": "string",
                    "enum": ["current", "windows", "macos", "linux", "ios", "android", "web"],
                    "description": "Target platform for build"
                },
                "mode": {
                    "type": "string",
                    "enum": ["debug", "release"],
                    "description": "Build mode"
                },
                "clean_first": {
                    "type": "boolean",
                    "description": "Whether to clean before building"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the build action."""
        if not self.validate_project_root():
            return {"error": "Invalid project root"}
        
        action = arguments.get("action")
        platform = arguments.get("platform", "current")
        mode = arguments.get("mode", "debug")
        clean_first = arguments.get("clean_first", False)
        
        try:
            if clean_first and action != "clean":
                await self._clean_build()
            
            if action == "build":
                return await self._build(platform, mode)
            elif action == "package":
                return await self._package(platform, mode)
            elif action == "clean":
                return await self._clean_build()
            elif action == "rebuild":
                return await self._rebuild(platform, mode)
            elif action == "dev":
                return await self._dev_build()
            elif action == "update":
                return await self._update_dependencies()
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            self.logger.error(f"Error in build automation: {e}")
            return {"error": str(e)}
    
    async def _build(self, platform: str, mode: str) -> Dict[str, Any]:
        """Build the application."""
        if platform == "current":
            command = "python -m briefcase build"
        else:
            command = f"python -m briefcase build {platform}"
        
        self.logger.info(f"Building for platform: {platform}")
        result = self.run_command(command)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Build completed for {platform}",
                "platform": platform,
                "mode": mode,
                "output": result["stdout"]
            }
        else:
            return {
                "success": False,
                "error": result["stderr"],
                "output": result["stdout"]
            }
    
    async def _package(self, platform: str, mode: str) -> Dict[str, Any]:
        """Package the application."""
        if platform == "current":
            command = "python -m briefcase package"
        else:
            command = f"python -m briefcase package {platform}"
        
        self.logger.info(f"Packaging for platform: {platform}")
        result = self.run_command(command)
        
        if result["success"]:
            # Find package files
            dist_dir = self.project_root / "dist"
            package_files = []
            
            if dist_dir.exists():
                for file in dist_dir.rglob("*"):
                    if file.is_file() and file.suffix in [".msi", ".dmg", ".deb", ".apk", ".ipa"]:
                        package_files.append(str(file))
            
            return {
                "success": True,
                "message": f"Package created for {platform}",
                "platform": platform,
                "mode": mode,
                "package_files": package_files,
                "output": result["stdout"]
            }
        else:
            return {
                "success": False,
                "error": result["stderr"],
                "output": result["stdout"]
            }
    
    async def _clean_build(self) -> Dict[str, Any]:
        """Clean build artifacts."""
        commands = [
            "find . -name '*.pyc' -delete",
            "find . -name '__pycache__' -type d -exec rm -rf {} +",
            "rm -rf build/",
            "rm -rf dist/",
            "rm -rf *.egg-info/"
        ]
        
        results = []
        for command in commands:
            result = self.run_command(command)
            results.append({
                "command": command,
                "success": result["success"],
                "output": result["stdout"] + result["stderr"]
            })
        
        return {
            "success": True,
            "message": "Clean completed",
            "results": results
        }
    
    async def _rebuild(self, platform: str, mode: str) -> Dict[str, Any]:
        """Clean and rebuild the application."""
        clean_result = await self._clean_build()
        if not clean_result["success"]:
            return clean_result
        
        build_result = await self._build(platform, mode)
        
        return {
            "success": build_result["success"],
            "message": f"Rebuild completed for {platform}",
            "clean_result": clean_result,
            "build_result": build_result
        }
    
    async def _dev_build(self) -> Dict[str, Any]:
        """Run development build."""
        command = "python -m briefcase dev"
        
        self.logger.info("Starting development build")
        result = self.run_command(command)
        
        return {
            "success": result["success"],
            "message": "Development build completed" if result["success"] else "Development build failed",
            "output": result["stdout"],
            "error": result["stderr"] if not result["success"] else None
        }
    
    async def _update_dependencies(self) -> Dict[str, Any]:
        """Update project dependencies."""
        commands = [
            "python -m briefcase update",
            "pip install --upgrade -e ."
        ]
        
        results = []
        overall_success = True
        
        for command in commands:
            result = self.run_command(command)
            results.append({
                "command": command,
                "success": result["success"],
                "output": result["stdout"],
                "error": result["stderr"]
            })
            
            if not result["success"]:
                overall_success = False
        
        return {
            "success": overall_success,
            "message": "Dependencies updated" if overall_success else "Dependency update failed",
            "results": results
        }