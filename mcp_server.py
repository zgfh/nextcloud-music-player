#!/usr/bin/env python3
"""
MCP Server CLI entry point for NextCloud Music Player automation.

This script provides a command-line interface to run the MCP server
for automating development tasks.
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.nextcloud_music_player.mcp.server import main

if __name__ == "__main__":
    main()