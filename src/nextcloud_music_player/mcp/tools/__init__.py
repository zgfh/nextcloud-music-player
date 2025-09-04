"""
MCP Tools for NextCloud Music Player automation.

This module contains various automation tools that can be called
via the MCP protocol to perform development tasks.
"""

from .base import BaseTool
from .project_scaffolding import ProjectScaffoldingTool
from .build_automation import BuildAutomationTool
from .test_automation import TestAutomationTool
from .code_quality import CodeQualityTool
from .deployment import DeploymentTool
from .documentation import DocumentationTool
from .configuration import ConfigurationTool

__all__ = [
    "BaseTool",
    "ProjectScaffoldingTool",
    "BuildAutomationTool", 
    "TestAutomationTool",
    "CodeQualityTool",
    "DeploymentTool",
    "DocumentationTool",
    "ConfigurationTool"
]