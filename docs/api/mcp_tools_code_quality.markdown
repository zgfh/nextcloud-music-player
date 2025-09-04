# code_quality.py\n\nCode quality automation tool.

This tool provides automated code quality checks and improvements.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict
from .base import BaseTool


class CodeQualityTool(BaseTool):
    """Tool for automating code quality tasks."""
    
    @property
    def name(self) -> str:
        return "code_quality"
    
    @property
    def description(self) -> str:
        return "Automate code quality tasks like linting, formatting, type checking, and security scanning"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["lint", "format", "type_check", "security_scan", "all_checks", "fix_issues"],
                    "description": "The code quality action to perform"
                },
                "target": {
                    "type": "string",
                    "description": "Target directory or file to check (default: src/)"
                },
                "auto_fix": {
                    "type": "boolean",
                    "description": "Automatically fix issues where possible"
                },
                "strict": {
                    "type": "boolean",
                    "description": "Use strict checking mode"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the code quality action."""
        if not self.validate_project_root():
            return {"error": "Invalid project root"}
        
        action = arguments.get("action")
        target = arguments.get("target", "src/")
        auto_fix = arguments.get("auto_fix", False)
        strict = arguments.get("strict", False)
        
        try:
            if action == "lint":
                return await self._lint_code(target, auto_fix)
            elif action == "format":
                return await self._format_code(target)
            elif action == "type_check":
                return await self._type_check(target, strict)
            elif action == "security_scan":
                return await self._security_scan(target)
            elif action == "all_checks":
                return await self._run_all_checks(target, auto_fix, strict)
            elif action == "fix_issues":
                return await self._fix_common_issues(target)
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            self.logger.error(f"Error in code quality: {e}")
            return {"error": str(e)}
    
    async def _lint_code(self, target: str, auto_fix: bool) -> Dict[str, Any]:
        """Run code linting."""
        commands = []
        
        # Try flake8 first (basic linting)
        commands.append("python -m flake8 src/ tests/ --statistics")
        
        # Try pylint as backup
        commands.append("python -c \"import sys; sys.exit(0)\" && python -m pylint src/nextcloud_music_player/ --reports=n")
        
        results = []
        for command in commands:
            result = self.run_command(command)
            tool_name = "flake8" if "flake8" in command else "pylint"
            
            results.append({
                "tool": tool_name,
                "command": command,
                "success": result["success"],
                "output": result["stdout"],
                "error": result["stderr"]
            })
            
            # If first tool works, break
            if result["success"] or "flake8" in command:
                break
        
        # Parse linting results
        issues = self._parse_lint_output(results)
        
        return {
            "success": len([r for r in results if r["success"]]) > 0,
            "message": f"Linting completed for {target}",
            "target": target,
            "results": results,
            "issues_found": issues,
            "auto_fix_applied": auto_fix
        }
    
    async def _format_code(self, target: str) -> Dict[str, Any]:
        """Format code using black and isort."""
        commands = [
            f"python -c \"import black; black.format_file_in_place('{target}')\" 2>/dev/null || echo 'Black not available'",
            f"python -c \"import isort; isort.file('{target}')\" 2>/dev/null || echo 'isort not available'"
        ]
        
        # Manual formatting for Python files if tools not available
        manual_format_result = await self._manual_format(target)
        
        results = []
        for command in commands:
            result = self.run_command(command)
            tool_name = "black" if "black" in command else "isort"
            
            results.append({
                "tool": tool_name,
                "success": "not available" not in result["stdout"].lower(),
                "output": result["stdout"],
                "error": result["stderr"]
            })
        
        return {
            "success": True,
            "message": f"Code formatting completed for {target}",
            "target": target,
            "results": results,
            "manual_formatting": manual_format_result
        }
    
    async def _type_check(self, target: str, strict: bool) -> Dict[str, Any]:
        """Run type checking."""
        # Basic type checking without mypy
        type_issues = await self._basic_type_check(target)
        
        command = f"python -c \"import mypy; mypy.api.run(['{target}'])\" 2>/dev/null"
        result = self.run_command(command)
        
        if "mypy" in result["stderr"] or not result["success"]:
            # Mypy not available, use basic checks
            return {
                "success": True,
                "message": f"Basic type checking completed for {target}",
                "target": target,
                "mypy_available": False,
                "basic_type_issues": type_issues
            }
        else:
            return {
                "success": result["success"],
                "message": f"Type checking completed for {target}",
                "target": target,
                "mypy_available": True,
                "output": result["stdout"],
                "error": result["stderr"] if not result["success"] else None
            }
    
    async def _security_scan(self, target: str) -> Dict[str, Any]:
        """Run security scanning."""
        # Basic security checks
        security_issues = []
        
        # Check for common security issues in Python files
        python_files = self.list_files(Path(target), "**/*.py")
        
        for file_path in python_files:
            try:
                content = self.read_file(file_path)
                issues = self._check_security_patterns(content, str(file_path))
                security_issues.extend(issues)
            except Exception as e:
                self.logger.error(f"Error scanning {file_path}: {e}")
        
        return {
            "success": True,
            "message": f"Security scan completed for {target}",
            "target": target,
            "security_issues": security_issues,
            "files_scanned": len(python_files)
        }
    
    async def _run_all_checks(self, target: str, auto_fix: bool, strict: bool) -> Dict[str, Any]:
        """Run all code quality checks."""
        lint_result = await self._lint_code(target, auto_fix)
        format_result = await self._format_code(target)
        type_result = await self._type_check(target, strict)
        security_result = await self._security_scan(target)
        
        overall_success = all([
            lint_result.get("success", False),
            format_result.get("success", False),
            type_result.get("success", False),
            security_result.get("success", False)
        ])
        
        return {
            "success": overall_success,
            "message": f"All code quality checks completed for {target}",
            "target": target,
            "results": {
                "linting": lint_result,
                "formatting": format_result,
                "type_checking": type_result,
                "security": security_result
            }
        }
    
    async def _fix_common_issues(self, target: str) -> Dict[str, Any]:
        """Fix common code issues."""
        fixes_applied = []
        
        # Find Python files
        python_files = self.list_files(Path(target), "**/*.py")
        
        for file_path in python_files:
            try:
                content = self.read_file(file_path)
                original_content = content
                
                # Apply common fixes
                content = self._fix_whitespace_issues(content)
                content = self._fix_import_issues(content)
                content = self._fix_common_patterns(content)
                
                if content != original_content:
                    self.write_file(file_path, content)
                    fixes_applied.append(str(file_path))
            
            except Exception as e:
                self.logger.error(f"Error fixing {file_path}: {e}")
        
        return {
            "success": True,
            "message": f"Common issues fixed in {target}",
            "target": target,
            "files_fixed": fixes_applied,
            "fixes_count": len(fixes_applied)
        }
    
    async def _manual_format(self, target: str) -> Dict[str, Any]:
        """Manually format Python files."""
        formatted_files = []
        
        python_files = self.list_files(Path(target), "**/*.py")
        
        for file_path in python_files:
            try:
                content = self.read_file(file_path)
                formatted_content = self._basic_format_python(content)
                
                if formatted_content != content:
                    self.write_file(file_path, formatted_content)
                    formatted_files.append(str(file_path))
            
            except Exception as e:
                self.logger.error(f"Error formatting {file_path}: {e}")
        
        return {
            "files_formatted": formatted_files,
            "count": len(formatted_files)
        }
    
    async def _basic_type_check(self, target: str) -> list:
        """Perform basic type checking."""
        issues = []
        
        python_files = self.list_files(Path(target), "**/*.py")
        
        for file_path in python_files:
            try:
                content = self.read_file(file_path)
                file_issues = self._check_type_patterns(content, str(file_path))
                issues.extend(file_issues)
            except Exception as e:
                self.logger.error(f"Error type checking {file_path}: {e}")
        
        return issues
    
    def _parse_lint_output(self, results: list) -> list:
        """Parse linting output to extract issues."""
        issues = []
        
        for result in results:
            if result["success"] and result["output"]:
                lines = result["output"].split('\\n')
                for line in lines:
                    if ":" in line and any(char.isdigit() for char in line):
                        issues.append({
                            "tool": result["tool"],
                            "line": line.strip(),
                            "severity": "warning"  # Default severity
                        })
        
        return issues
    
    def _check_security_patterns(self, content: str, file_path: str) -> list:
        """Check for security patterns in code."""
        issues = []
        lines = content.split('\\n\n