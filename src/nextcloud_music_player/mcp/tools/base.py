"""
Base class for MCP tools.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Base class for all MCP tools.
    
    This class provides common functionality for all automation tools.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize the tool.
        
        Args:
            project_root: Path to the project root directory
        """
        self.project_root = Path(project_root)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the tool."""
        pass
    
    @property
    @abstractmethod  
    def description(self) -> str:
        """A description of what the tool does."""
        pass
    
    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema for the tool's input parameters."""
        pass
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """
        Execute the tool with the given arguments.
        
        Args:
            arguments: The input arguments for the tool
            
        Returns:
            The result of the tool execution
        """
        pass
    
    def validate_project_root(self) -> bool:
        """
        Validate that the project root is valid.
        
        Returns:
            True if valid, False otherwise
        """
        return (
            self.project_root.exists() and
            self.project_root.is_dir() and
            (self.project_root / "pyproject.toml").exists()
        )
    
    def run_command(self, command: str, cwd: Path = None) -> Dict[str, Any]:
        """
        Run a shell command and return the result.
        
        Args:
            command: The command to run
            cwd: Working directory for the command
            
        Returns:
            Dictionary with 'returncode', 'stdout', and 'stderr'
        """
        import subprocess
        
        if cwd is None:
            cwd = self.project_root
        
        self.logger.info(f"Running command: {command} in {cwd}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
        
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out after 5 minutes",
                "success": False
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def read_file(self, file_path: Path) -> str:
        """
        Read a file and return its contents.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            File contents as string
        """
        try:
            if not file_path.is_absolute():
                file_path = self.project_root / file_path
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def write_file(self, file_path: Path, content: str) -> bool:
        """
        Write content to a file.
        
        Args:
            file_path: Path to the file to write
            content: Content to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not file_path.is_absolute():
                file_path = self.project_root / file_path
            
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            self.logger.error(f"Error writing file {file_path}: {e}")
            return False
    
    def list_files(self, directory: Path, pattern: str = "*") -> list:
        """
        List files in a directory matching a pattern.
        
        Args:
            directory: Directory to search in
            pattern: Glob pattern to match
            
        Returns:
            List of matching file paths
        """
        try:
            if not directory.is_absolute():
                directory = self.project_root / directory
            
            if not directory.exists():
                return []
            
            return list(directory.glob(pattern))
        except Exception as e:
            self.logger.error(f"Error listing files in {directory}: {e}")
            return []