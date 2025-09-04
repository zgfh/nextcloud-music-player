"""
Deployment automation tool.

This tool provides automated deployment functionality.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict
from .base import BaseTool


class DeploymentTool(BaseTool):
    """Tool for automating deployment tasks."""
    
    @property
    def name(self) -> str:
        return "deployment"
    
    @property
    def description(self) -> str:
        return "Automate deployment tasks like creating releases, uploading artifacts, and managing versions"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_release", "build_artifacts", "upload_artifacts", "tag_version", "prepare_deploy"],
                    "description": "The deployment action to perform"
                },
                "version": {
                    "type": "string",
                    "description": "Version number for release"
                },
                "platform": {
                    "type": "string",
                    "enum": ["all", "windows", "macos", "linux", "ios", "android"],
                    "description": "Target platform for deployment"
                },
                "environment": {
                    "type": "string",
                    "enum": ["development", "staging", "production"],
                    "description": "Deployment environment"
                },
                "changelog": {
                    "type": "string",
                    "description": "Changelog for the release"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the deployment action."""
        if not self.validate_project_root():
            return {"error": "Invalid project root"}
        
        action = arguments.get("action")
        version = arguments.get("version")
        platform = arguments.get("platform", "all")
        environment = arguments.get("environment", "development")
        changelog = arguments.get("changelog", "")
        
        try:
            if action == "create_release":
                return await self._create_release(version, changelog)
            elif action == "build_artifacts":
                return await self._build_artifacts(platform)
            elif action == "upload_artifacts":
                return await self._upload_artifacts(platform)
            elif action == "tag_version":
                return await self._tag_version(version)
            elif action == "prepare_deploy":
                return await self._prepare_deployment(environment, version)
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            self.logger.error(f"Error in deployment: {e}")
            return {"error": str(e)}
    
    async def _create_release(self, version: str, changelog: str) -> Dict[str, Any]:
        """Create a new release."""
        if not version:
            return {"error": "Version is required for release creation"}
        
        # Update version in pyproject.toml
        version_update_result = await self._update_version(version)
        if not version_update_result["success"]:
            return version_update_result
        
        # Create git tag
        tag_result = await self._tag_version(version)
        if not tag_result["success"]:
            return tag_result
        
        # Generate changelog if not provided
        if not changelog:
            changelog = await self._generate_changelog(version)
        
        # Create release notes
        release_notes = await self._create_release_notes(version, changelog)
        
        return {
            "success": True,
            "message": f"Release {version} created successfully",
            "version": version,
            "changelog": changelog,
            "release_notes": release_notes,
            "tag_result": tag_result
        }
    
    async def _build_artifacts(self, platform: str) -> Dict[str, Any]:
        """Build deployment artifacts."""
        artifacts = []
        build_results = []
        
        if platform == "all":
            platforms = ["windows", "macos", "linux"]
        else:
            platforms = [platform]
        
        for target_platform in platforms:
            self.logger.info(f"Building artifacts for {target_platform}")
            
            if target_platform == "windows":
                command = "python -m briefcase package windows"
            elif target_platform == "macos":
                command = "python -m briefcase package macOS"
            elif target_platform == "linux":
                command = "python -m briefcase package linux"
            else:
                continue
            
            result = self.run_command(command)
            build_results.append({
                "platform": target_platform,
                "success": result["success"],
                "output": result["stdout"],
                "error": result["stderr"]
            })
            
            if result["success"]:
                # Find created artifacts
                dist_dir = self.project_root / "dist"
                if dist_dir.exists():
                    for artifact in dist_dir.rglob("*"):
                        if artifact.is_file() and self._is_deployment_artifact(artifact):
                            artifacts.append({
                                "platform": target_platform,
                                "file": str(artifact),
                                "size": artifact.stat().st_size
                            })
        
        return {
            "success": len([r for r in build_results if r["success"]]) > 0,
            "message": f"Artifact building completed for {platform}",
            "platform": platform,
            "artifacts": artifacts,
            "build_results": build_results
        }
    
    async def _upload_artifacts(self, platform: str) -> Dict[str, Any]:
        """Upload deployment artifacts."""
        # This is a placeholder - in real scenarios, this would upload to
        # artifact repositories, app stores, or deployment servers
        
        dist_dir = self.project_root / "dist"
        artifacts = []
        
        if dist_dir.exists():
            for artifact in dist_dir.rglob("*"):
                if artifact.is_file() and self._is_deployment_artifact(artifact):
                    artifacts.append({
                        "file": str(artifact),
                        "size": artifact.stat().st_size,
                        "uploaded": False,  # Placeholder
                        "upload_url": f"https://example.com/artifacts/{artifact.name}"
                    })
        
        return {
            "success": True,
            "message": f"Artifact upload prepared for {platform}",
            "platform": platform,
            "artifacts": artifacts,
            "note": "This is a placeholder - configure actual upload destinations"
        }
    
    async def _tag_version(self, version: str) -> Dict[str, Any]:
        """Create a git tag for the version."""
        if not version:
            return {"error": "Version is required for tagging"}
        
        # Check if tag already exists
        check_result = self.run_command(f"git tag -l v{version}")
        if check_result["stdout"].strip():
            return {"error": f"Tag v{version} already exists"}
        
        # Create the tag
        tag_result = self.run_command(f"git tag -a v{version} -m 'Release version {version}'")
        
        if tag_result["success"]:
            # Push the tag
            push_result = self.run_command(f"git push origin v{version}")
            
            return {
                "success": push_result["success"],
                "message": f"Version {version} tagged and pushed" if push_result["success"] else f"Version {version} tagged locally",
                "version": version,
                "tag": f"v{version}",
                "pushed": push_result["success"],
                "push_error": push_result["stderr"] if not push_result["success"] else None
            }
        else:
            return {
                "success": False,
                "error": tag_result["stderr"],
                "message": f"Failed to create tag for version {version}"
            }
    
    async def _prepare_deployment(self, environment: str, version: str = None) -> Dict[str, Any]:
        """Prepare deployment for specified environment."""
        preparation_steps = []
        
        # Step 1: Validate project state
        validation_result = await self._validate_deployment_readiness()
        preparation_steps.append({
            "step": "validation",
            "success": validation_result["success"],
            "details": validation_result
        })
        
        # Step 2: Run tests
        test_result = self.run_command("python -m tests.test_basic")
        preparation_steps.append({
            "step": "testing",
            "success": test_result["success"],
            "output": test_result["stdout"]
        })
        
        # Step 3: Build artifacts
        if test_result["success"]:
            build_result = await self._build_artifacts("all")
            preparation_steps.append({
                "step": "build",
                "success": build_result["success"],
                "details": build_result
            })
        else:
            preparation_steps.append({
                "step": "build",
                "success": False,
                "error": "Skipped due to test failures"
            })
        
        # Step 4: Create deployment manifest
        manifest = await self._create_deployment_manifest(environment, version)
        preparation_steps.append({
            "step": "manifest",
            "success": True,
            "details": manifest
        })
        
        overall_success = all(step["success"] for step in preparation_steps)
        
        return {
            "success": overall_success,
            "message": f"Deployment preparation completed for {environment}",
            "environment": environment,
            "version": version,
            "steps": preparation_steps,
            "ready_for_deployment": overall_success
        }
    
    async def _update_version(self, version: str) -> Dict[str, Any]:
        """Update version in project files."""
        try:
            # Update pyproject.toml
            pyproject_path = self.project_root / "pyproject.toml"
            if pyproject_path.exists():
                content = self.read_file(pyproject_path)
                
                # Replace version line
                lines = content.split('\\n')
                for i, line in enumerate(lines):
                    if line.strip().startswith('version = '):
                        lines[i] = f'version = "{version}"'
                        break
                
                new_content = '\\n'.join(lines)
                self.write_file(pyproject_path, new_content)
            
            # Update __init__.py files if they contain version
            init_files = self.list_files(self.project_root / "src", "**/__init__.py")
            for init_file in init_files:
                content = self.read_file(init_file)
                if "__version__" in content:
                    lines = content.split('\\n')
                    for i, line in enumerate(lines):
                        if "__version__" in line:
                            lines[i] = f'__version__ = "{version}"'
                            break
                    
                    new_content = '\\n'.join(lines)
                    self.write_file(init_file, new_content)
            
            return {
                "success": True,
                "message": f"Version updated to {version}",
                "version": version
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_changelog(self, version: str) -> str:
        """Generate changelog from git commits."""
        # Get commits since last tag
        last_tag_result = self.run_command("git describe --tags --abbrev=0")
        
        if last_tag_result["success"]:
            last_tag = last_tag_result["stdout"].strip()
            log_result = self.run_command(f"git log {last_tag}..HEAD --oneline")
        else:
            log_result = self.run_command("git log --oneline -10")
        
        if log_result["success"]:
            commits = log_result["stdout"].strip().split('\\n')
            changelog = f"## Version {version}\\n\\n"
            
            for commit in commits:
                if commit.strip():
                    changelog += f"- {commit.strip()}\\n"
            
            return changelog
        else:
            return f"## Version {version}\\n\\n- Release version {version}\\n"
    
    async def _create_release_notes(self, version: str, changelog: str) -> str:
        """Create release notes."""
        release_notes = f"""# Release {version}

{changelog}

## Installation

Download the appropriate installer for your platform:

- **Windows**: Download the `.msi` installer
- **macOS**: Download the `.dmg` file
- **Linux**: Download the `.deb` package

## Requirements

- Python 3.8 or higher
- NextCloud server (version 20 or higher)

## Known Issues

Please check the [GitHub Issues](https://github.com/example/nextcloud-music-player/issues) page for known issues.

## Support

For support, please open an issue on GitHub or check our documentation.
"""
        
        # Save release notes to file
        release_notes_path = self.project_root / f"RELEASE_NOTES_{version}.md"
        self.write_file(release_notes_path, release_notes)
        
        return release_notes
    
    async def _validate_deployment_readiness(self) -> Dict[str, Any]:
        """Validate that the project is ready for deployment."""
        issues = []
        
        # Check required files exist
        required_files = [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "src/nextcloud_music_player/__init__.py"
        ]
        
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                issues.append(f"Missing required file: {file_path}")
        
        # Check git status
        git_status = self.run_command("git status --porcelain")
        if git_status["success"] and git_status["stdout"].strip():
            issues.append("Uncommitted changes in git repository")
        
        # Check if tests pass
        test_result = self.run_command("python -m tests.test_minimal")
        if not test_result["success"]:
            issues.append("Tests are failing")
        
        return {
            "success": len(issues) == 0,
            "issues": issues,
            "ready_for_deployment": len(issues) == 0
        }
    
    async def _create_deployment_manifest(self, environment: str, version: str = None) -> Dict[str, Any]:
        """Create deployment manifest."""
        import datetime
        
        manifest = {
            "deployment": {
                "environment": environment,
                "version": version or "latest",
                "timestamp": datetime.datetime.now().isoformat(),
                "platform": "multi-platform",
                "artifacts": []
            },
            "requirements": {
                "python": ">=3.8",
                "platforms": ["Windows", "macOS", "Linux", "iOS", "Android"]
            },
            "configuration": {
                "database": "local_sqlite",
                "cache": "local_filesystem",
                "logging": "file_and_console"
            }
        }
        
        # Save manifest
        manifest_path = self.project_root / f"deployment_manifest_{environment}.json"
        self.write_file(manifest_path, json.dumps(manifest, indent=2))
        
        return manifest
    
    def _is_deployment_artifact(self, file_path: Path) -> bool:
        """Check if file is a deployment artifact."""
        deployment_extensions = [".msi", ".dmg", ".deb", ".apk", ".ipa", ".exe", ".tar.gz", ".zip"]
        return file_path.suffix.lower() in deployment_extensions