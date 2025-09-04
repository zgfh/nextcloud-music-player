# documentation.py\n\nDocumentation automation tool.

This tool provides automated documentation generation and management.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict
from .base import BaseTool


class DocumentationTool(BaseTool):
    """Tool for automating documentation tasks."""
    
    @property
    def name(self) -> str:
        return "documentation"
    
    @property
    def description(self) -> str:
        return "Automate documentation tasks like generating API docs, updating README, and creating user guides"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["generate_api_docs", "update_readme", "create_user_guide", "generate_changelog", "create_wiki"],
                    "description": "The documentation action to perform"
                },
                "format": {
                    "type": "string",
                    "enum": ["markdown", "html", "pdf", "rst"],
                    "description": "Output format for documentation"
                },
                "include_private": {
                    "type": "boolean",
                    "description": "Include private methods/classes in API docs"
                },
                "output_dir": {
                    "type": "string",
                    "description": "Output directory for generated docs"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the documentation action."""
        if not self.validate_project_root():
            return {"error": "Invalid project root"}
        
        action = arguments.get("action")
        format_type = arguments.get("format", "markdown")
        include_private = arguments.get("include_private", False)
        output_dir = arguments.get("output_dir", "docs")
        
        try:
            if action == "generate_api_docs":
                return await self._generate_api_docs(format_type, include_private, output_dir)
            elif action == "update_readme":
                return await self._update_readme()
            elif action == "create_user_guide":
                return await self._create_user_guide(format_type, output_dir)
            elif action == "generate_changelog":
                return await self._generate_changelog()
            elif action == "create_wiki":
                return await self._create_wiki(output_dir)
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            self.logger.error(f"Error in documentation: {e}")
            return {"error": str(e)}
    
    async def _generate_api_docs(self, format_type: str, include_private: bool, output_dir: str) -> Dict[str, Any]:
        """Generate API documentation."""
        docs_dir = self.project_root / output_dir / "api"
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all Python modules
        src_dir = self.project_root / "src" / "nextcloud_music_player"
        python_files = self.list_files(src_dir, "**/*.py")
        
        generated_docs = []
        
        for py_file in python_files:
            if py_file.name == "__init__.py":
                continue
            
            # Generate documentation for this module
            doc_content = await self._extract_module_docs(py_file, include_private)
            
            if doc_content:
                # Create doc file
                relative_path = py_file.relative_to(src_dir)
                doc_filename = str(relative_path).replace("/", "_").replace(".py", f".{format_type}")
                doc_path = docs_dir / doc_filename
                
                if format_type == "markdown":
                    formatted_content = self._format_as_markdown(doc_content, py_file.name)
                else:
                    formatted_content = str(doc_content)
                
                self.write_file(doc_path, formatted_content)
                generated_docs.append(str(doc_path))
        
        # Create index file
        index_content = self._create_api_index(generated_docs, format_type)
        index_path = docs_dir / f"index.{format_type}"
        self.write_file(index_path, index_content)
        
        return {
            "success": True,
            "message": "API documentation generated",
            "format": format_type,
            "output_dir": str(docs_dir),
            "files_generated": generated_docs + [str(index_path)],
            "include_private": include_private
        }
    
    async def _update_readme(self) -> Dict[str, Any]:
        """Update README.md with current project information."""
        readme_path = self.project_root / "README.md"
        
        # Generate updated README content
        readme_content = await self._generate_readme_content()
        
        # Backup existing README
        if readme_path.exists():
            backup_path = self.project_root / "README.md.backup"
            backup_content = self.read_file(readme_path)
            self.write_file(backup_path, backup_content)
        
        # Write new README
        self.write_file(readme_path, readme_content)
        
        return {
            "success": True,
            "message": "README.md updated",
            "readme_path": str(readme_path),
            "backup_created": readme_path.exists()
        }
    
    async def _create_user_guide(self, format_type: str, output_dir: str) -> Dict[str, Any]:
        """Create user guide documentation."""
        guide_dir = self.project_root / output_dir / "user_guide"
        guide_dir.mkdir(parents=True, exist_ok=True)
        
        # Create different sections of the user guide
        sections = {
            "installation": self._create_installation_guide(),
            "quick_start": self._create_quick_start_guide(),
            "configuration": self._create_configuration_guide(),
            "troubleshooting": self._create_troubleshooting_guide(),
            "faq": self._create_faq()
        }
        
        generated_files = []
        
        for section_name, content in sections.items():
            section_file = guide_dir / f"{section_name}.{format_type}"
            
            if format_type == "markdown":
                formatted_content = content
            else:
                formatted_content = content  # For now, just use markdown
            
            self.write_file(section_file, formatted_content)
            generated_files.append(str(section_file))
        
        # Create table of contents
        toc_content = self._create_user_guide_toc(sections.keys(), format_type)
        toc_file = guide_dir / f"index.{format_type}"
        self.write_file(toc_file, toc_content)
        generated_files.append(str(toc_file))
        
        return {
            "success": True,
            "message": "User guide created",
            "format": format_type,
            "output_dir": str(guide_dir),
            "files_generated": generated_files
        }
    
    async def _generate_changelog(self) -> Dict[str, Any]:
        """Generate changelog from git history."""
        changelog_path = self.project_root / "CHANGELOG.md"
        
        # Get git log
        git_log_result = self.run_command("git log --oneline --decorate --all -50")
        
        if git_log_result["success"]:
            commits = git_log_result["stdout"].strip().split('\\n')
            
            changelog_content = "# Changelog\\n\\n"
            changelog_content += "All notable changes to this project will be documented in this file.\\n\\n"
            
            # Group commits by date or tag
            current_date = None
            for commit in commits:
                if commit.strip():
                    changelog_content += f"- {commit.strip()}\\n"
        else:
            changelog_content = "# Changelog\\n\\nNo git history available.\\n"
        
        self.write_file(changelog_path, changelog_content)
        
        return {
            "success": True,
            "message": "Changelog generated",
            "changelog_path": str(changelog_path)
        }
    
    async def _create_wiki(self, output_dir: str) -> Dict[str, Any]:
        """Create wiki-style documentation."""
        wiki_dir = self.project_root / output_dir / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        
        # Create wiki pages
        wiki_pages = {
            "Home": self._create_wiki_home(),
            "Architecture": self._create_architecture_docs(),
            "Contributing": self._create_contributing_guide(),
            "Development-Setup": self._create_dev_setup_guide(),
            "API-Reference": self._create_api_reference()
        }
        
        generated_files = []
        
        for page_name, content in wiki_pages.items():
            page_file = wiki_dir / f"{page_name}.md"
            self.write_file(page_file, content)
            generated_files.append(str(page_file))
        
        return {
            "success": True,
            "message": "Wiki documentation created",
            "output_dir": str(wiki_dir),
            "files_generated": generated_files
        }
    
    async def _extract_module_docs(self, py_file: Path, include_private: bool) -> Dict[str, Any]:
        """Extract documentation from a Python module."""
        try:
            content = self.read_file(py_file)
            
            # Parse docstrings and function/class definitions
            lines = content.split('\\n\n