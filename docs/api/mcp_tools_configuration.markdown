# configuration.py\n\nConfiguration automation tool.

This tool provides automated configuration management functionality.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict
from .base import BaseTool


class ConfigurationTool(BaseTool):
    """Tool for automating configuration management tasks."""
    
    @property
    def name(self) -> str:
        return "configuration"
    
    @property
    def description(self) -> str:
        return "Automate configuration management tasks like setting up environments, managing secrets, and validating configs"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["setup_environment", "validate_config", "backup_config", "restore_config", "reset_config"],
                    "description": "The configuration action to perform"
                },
                "environment": {
                    "type": "string",
                    "enum": ["development", "staging", "production"],
                    "description": "Target environment"
                },
                "config_file": {
                    "type": "string",
                    "description": "Specific configuration file to work with"
                },
                "backup_name": {
                    "type": "string",
                    "description": "Name for configuration backup"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the configuration action."""
        if not self.validate_project_root():
            return {"error": "Invalid project root"}
        
        action = arguments.get("action")
        environment = arguments.get("environment", "development")
        config_file = arguments.get("config_file")
        backup_name = arguments.get("backup_name")
        
        try:
            if action == "setup_environment":
                return await self._setup_environment(environment)
            elif action == "validate_config":
                return await self._validate_config(config_file)
            elif action == "backup_config":
                return await self._backup_config(backup_name)
            elif action == "restore_config":
                return await self._restore_config(backup_name)
            elif action == "reset_config":
                return await self._reset_config()
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            self.logger.error(f"Error in configuration: {e}")
            return {"error": str(e)}
    
    async def _setup_environment(self, environment: str) -> Dict[str, Any]:
        """Setup environment-specific configuration."""
        config_templates = {
            "development": {
                "debug": True,
                "log_level": "DEBUG",
                "cache_size": "1GB",
                "sync_interval": 300,
                "server_url": "http://localhost:8080",
                "auto_sync": True
            },
            "staging": {
                "debug": False,
                "log_level": "INFO",
                "cache_size": "2GB",
                "sync_interval": 600,
                "server_url": "https://staging-nextcloud.example.com",
                "auto_sync": True
            },
            "production": {
                "debug": False,
                "log_level": "WARNING",
                "cache_size": "5GB",
                "sync_interval": 1800,
                "server_url": "",  # Must be configured by user
                "auto_sync": False
            }
        }
        
        if environment not in config_templates:
            return {"error": f"Unknown environment: {environment}"}
        
        # Create environment-specific config
        config_dir = self.project_root / "config"
        config_dir.mkdir(exist_ok=True)
        
        env_config = config_templates[environment]
        config_file = config_dir / f"{environment}.json"
        
        self.write_file(config_file, json.dumps(env_config, indent=2))
        
        # Create environment file
        env_file = self.project_root / ".env"
        env_content = f"ENVIRONMENT={environment}\\n"
        env_content += f"CONFIG_FILE=config/{environment}.json\\n"
        
        self.write_file(env_file, env_content)
        
        # Setup logging configuration
        await self._setup_logging_config(environment)
        
        # Setup directories
        directories = [
            "logs",
            "cache",
            "backups",
            "temp"
        ]
        
        created_dirs = []
        for dir_name in directories:
            dir_path = self.project_root / dir_name
            dir_path.mkdir(exist_ok=True)
            created_dirs.append(str(dir_path))
        
        return {
            "success": True,
            "message": f"Environment {environment} setup completed",
            "environment": environment,
            "config_file": str(config_file),
            "env_file": str(env_file),
            "directories_created": created_dirs,
            "next_steps": [
                "Configure server_url in the config file" if environment == "production" else None,
                "Set up NextCloud credentials",
                "Test the configuration"
            ]
        }
    
    async def _validate_config(self, config_file: str = None) -> Dict[str, Any]:
        """Validate configuration files."""
        validation_results = []
        
        if config_file:
            # Validate specific file
            config_path = self.project_root / config_file
            if not config_path.exists():
                return {"error": f"Configuration file not found: {config_file}"}
            
            result = await self._validate_single_config(config_path)
            validation_results.append(result)
        else:
            # Validate all config files
            config_files = [
                "pyproject.toml",
                "config/development.json",
                "config/staging.json", 
                "config/production.json",
                ".env"
            ]
            
            for file_path in config_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    result = await self._validate_single_config(full_path)
                    validation_results.append(result)
        
        # Summary
        total_files = len(validation_results)
        valid_files = len([r for r in validation_results if r["valid"]])
        invalid_files = total_files - valid_files
        
        return {
            "success": invalid_files == 0,
            "message": f"Validation completed: {valid_files}/{total_files} files valid",
            "total_files": total_files,
            "valid_files": valid_files,
            "invalid_files": invalid_files,
            "results": validation_results
        }
    
    async def _backup_config(self, backup_name: str = None) -> Dict[str, Any]:
        """Backup configuration files."""
        import datetime
        
        if not backup_name:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"config_backup_{timestamp}"
        
        backup_dir = self.project_root / "backups" / backup_name
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Files to backup
        config_files = [
            "pyproject.toml",
            ".env",
            "config/",
            "src/nextcloud_music_player/config_manager.py"
        ]
        
        backed_up_files = []
        
        for file_path in config_files:
            source_path = self.project_root / file_path
            
            if source_path.exists():
                if source_path.is_file():
                    # Backup single file
                    dest_path = backup_dir / source_path.name
                    content = self.read_file(source_path)
                    self.write_file(dest_path, content)
                    backed_up_files.append(str(source_path))
                elif source_path.is_dir():
                    # Backup directory
                    for sub_file in source_path.rglob("*"):
                        if sub_file.is_file():
                            relative_path = sub_file.relative_to(source_path)
                            dest_path = backup_dir / source_path.name / relative_path
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            content = self.read_file(sub_file)
                            self.write_file(dest_path, content)
                            backed_up_files.append(str(sub_file))
        
        # Create backup manifest
        manifest = {
            "backup_name": backup_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "files": backed_up_files,
            "project_root": str(self.project_root)
        }
        
        manifest_path = backup_dir / "manifest.json"
        self.write_file(manifest_path, json.dumps(manifest, indent=2))
        
        return {
            "success": True,
            "message": f"Configuration backup created: {backup_name}",
            "backup_name": backup_name,
            "backup_dir": str(backup_dir),
            "files_backed_up": len(backed_up_files),
            "backed_up_files": backed_up_files
        }
    
    async def _restore_config(self, backup_name: str) -> Dict[str, Any]:
        """Restore configuration from backup."""
        if not backup_name:
            return {"error": "Backup name is required"}
        
        backup_dir = self.project_root / "backups" / backup_name
        
        if not backup_dir.exists():
            return {"error": f"Backup not found: {backup_name}"}
        
        # Read backup manifest
        manifest_path = backup_dir / "manifest.json"
        if not manifest_path.exists():
            return {"error": "Backup manifest not found"}
        
        try:
            manifest_content = self.read_file(manifest_path)
            manifest = json.loads(manifest_content)
        except Exception as e:
            return {"error": f"Invalid backup manifest: {e}"}
        
        # Restore files
        restored_files = []
        failed_files = []
        
        for original_file in manifest["files"]:
            try:
                original_path = Path(original_file)
                
                # Find backup file
                if original_path.is_absolute():
                    relative_path = original_path.relative_to(manifest["project_root"])
                else:
                    relative_path = original_path
                
                backup_file_path = None
                
                # Search for the file in backup directory
                for backup_file in backup_dir.rglob("*"):
                    if backup_file.is_file() and backup_file.name == original_path.name:
                        backup_file_path = backup_file
                        break
                
                if backup_file_path:
                    # Restore file
                    content = self.read_file(backup_file_path)
                    target_path = self.project_root / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    self.write_file(target_path, content)
                    restored_files.append(str(target_path))
                else:
                    failed_files.append(original_file)
            
            except Exception as e:
                self.logger.error(f"Error restoring {original_file}: {e}")
                failed_files.append(original_file)
        
        return {
            "success": len(failed_files) == 0,
            "message": f"Configuration restored from backup: {backup_name}",
            "backup_name": backup_name,
            "restored_files": len(restored_files),
            "failed_files": len(failed_files),
            "restored_file_list": restored_files,
            "failed_file_list": failed_files
        }
    
    async def _reset_config(self) -> Dict[str, Any]:
        """Reset configuration to defaults."""
        # Backup current config first
        backup_result = await self._backup_config("pre_reset_backup")
        
        if not backup_result["success"]:
            return {"error": "Failed to backup current configuration"}
        
        # Reset configuration files
        reset_files = []
        
        # Reset pyproject.toml to template
        pyproject_template = """[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "nextcloud-music-player"
version = "0.1.0"
description = "A cross-platform music player with NextCloud integration"
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    "toga>=0.4.0",
    "requests>=2.25.0",
    "httpx>=0.24.0",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
    "black",
    "flake8",
    "briefcase",
]

[tool.briefcase]
project_name = "NextCloud Music Player"
bundle = "com.example"
version = "0.1.0"
"""
        
        pyproject_path = self.project_root / "pyproject.toml"
        self.write_file(pyproject_path, pyproject_template)
        reset_files.append(str(pyproject_path))
        
        # Remove environment-specific configs
        config_dir = self.project_root / "config"
        if config_dir.exists():
            for config_file in config_dir.glob("*.json"):
                config_file.unlink()
                reset_files.append(str(config_file))
        
        # Reset .env file
        env_path = self.project_root / ".env"
        if env_path.exists():
            env_path.unlink()
            reset_files.append(str(env_path))
        
        # Setup default development environment
        setup_result = await self._setup_environment("development")
        
        return {
            "success": True,
            "message": "Configuration reset to defaults",
            "backup_created": backup_result["backup_name"],
            "reset_files": reset_files,
            "setup_result": setup_result
        }
    
    async def _validate_single_config(self, config_path: Path) -> Dict[str, Any]:
        """Validate a single configuration file."""
        result = {
            "file": str(config_path),
            "valid": False,
            "errors": [],
            "warnings": []
        }
        
        try:
            if config_path.suffix == ".json":
                # Validate JSON
                content = self.read_file(config_path)
                json.loads(content)  # Will raise exception if invalid
                
                # Additional validation for specific files
                if "development.json" in config_path.name or "staging.json" in config_path.name or "production.json" in config_path.name:
                    config_data = json.loads(content)
                    await self._validate_app_config(config_data, result)
            
            elif config_path.suffix == ".toml":
                # Basic TOML validation
                content = self.read_file(config_path)
                
                # Check for required sections in pyproject.toml
                if "pyproject.toml" in config_path.name:
                    await self._validate_pyproject_toml(content, result)
            
            elif config_path.name == ".env":
                # Validate environment file
                content = self.read_file(config_path)
                await self._validate_env_file(content, result)
            
            # If no errors found, mark as valid
            if not result["errors"]:
                result["valid"] = True
        
        except json.JSONDecodeError as e:
            result["errors"].append(f"Invalid JSON: {e}")
        except Exception as e:
            result["errors"].append(f"Validation error: {e}")
        
        return result
    
    async def _validate_app_config(self, config_data: dict, result: dict) -> None:
        """Validate application configuration data."""
        required_keys = ["debug", "log_level", "cache_size", "sync_interval"]
        
        for key in required_keys:
            if key not in config_data:
                result["errors"].append(f"Missing required key: {key}")
        
        # Validate specific values
        if "log_level" in config_data:
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
            if config_data["log_level"] not in valid_levels:
                result["errors"].append(f"Invalid log_level: {config_data['log_level']}")
        
        if "sync_interval" in config_data:
            if not isinstance(config_data["sync_interval"], int) or config_data["sync_interval"] < 60:
                result["warnings"].append("sync_interval should be at least 60 seconds")
        
        if "server_url" in config_data and config_data["server_url"]:
            url = config_data["server_url"]
            if not url.startswith(("http://", "https://")):
                result["errors"].append("server_url must start with http:// or https://")
    
    async def _validate_pyproject_toml(self, content: str, result: dict) -> None:
        """Validate pyproject.toml content."""
        required_sections = ["build-system", "project", "tool.briefcase"]
        
        for section in required_sections:
            if f"[{section}]" not in content:
                result["errors"].append(f"Missing required section: [{section}]")
        
        # Check for required project fields
        required_project_fields = ["name", "version", "description"]
        for field in required_project_fields:
            if f"{field} =" not in content:
                result["errors"].append(f"Missing required project field: {field}")
    
    async def _validate_env_file(self, content: str, result: dict) -> None:
        """Validate .env file content."""
        lines = content.strip().split('\\n\n