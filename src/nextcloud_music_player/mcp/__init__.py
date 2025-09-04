"""
NextCloud Music Player MCP Plugin

This module provides a Model Context Protocol (MCP) server plugin
that automates common development tasks for the NextCloud Music Player project.
"""

from .server import MCPServer
from .tools import *

__version__ = "0.1.0"
__all__ = ["MCPServer"]