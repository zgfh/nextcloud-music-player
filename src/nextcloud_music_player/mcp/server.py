"""
MCP Server implementation for NextCloud Music Player automation.

This module implements a Model Context Protocol server that provides
automated development tools for the NextCloud Music Player project.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Sequence
import sys
import os
from pathlib import Path

# Add the project root to the path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from .tools import (
    ProjectScaffoldingTool,
    BuildAutomationTool,
    TestAutomationTool,
    CodeQualityTool,
    DeploymentTool,
    DocumentationTool,
    ConfigurationTool
)

logger = logging.getLogger(__name__)


class MCPServer:
    """
    Model Context Protocol server for NextCloud Music Player automation.
    
    This server provides automated development tools that can be called
    by MCP clients to perform common development tasks.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the MCP server.
        
        Args:
            project_root: Path to the project root directory
        """
        if project_root is None:
            # Auto-detect project root by looking for pyproject.toml
            current_dir = Path(__file__).parent
            while current_dir != current_dir.parent:
                if (current_dir / "pyproject.toml").exists():
                    project_root = current_dir
                    break
                current_dir = current_dir.parent
            else:
                project_root = Path.cwd()
        
        self.project_root = project_root
        self.tools = {}
        self._setup_logging()
        self._initialize_tools()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _initialize_tools(self):
        """Initialize all available tools."""
        tool_classes = [
            ProjectScaffoldingTool,
            BuildAutomationTool,
            TestAutomationTool,
            CodeQualityTool,
            DeploymentTool,
            DocumentationTool,
            ConfigurationTool
        ]
        
        for tool_class in tool_classes:
            tool = tool_class(self.project_root)
            self.tools[tool.name] = tool
            logger.info(f"Initialized tool: {tool.name}")
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an MCP request.
        
        Args:
            request: The MCP request object
            
        Returns:
            The response object
        """
        try:
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            if method == "tools/list":
                return await self._handle_list_tools(request_id)
            elif method == "tools/call":
                return await self._handle_tool_call(request_id, params)
            elif method == "initialize":
                return await self._handle_initialize(request_id, params)
            else:
                return self._error_response(request_id, -32601, f"Method not found: {method}")
        
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return self._error_response(request.get("id"), -32603, f"Internal error: {str(e)}")
    
    async def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialization request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "nextcloud-music-player-mcp",
                    "version": "0.1.0"
                }
            }
        }
    
    async def _handle_list_tools(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools_list = []
        for tool in self.tools.values():
            tools_list.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            })
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools_list
            }
        }
    
    async def _handle_tool_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            return self._error_response(request_id, -32602, f"Tool not found: {tool_name}")
        
        try:
            tool = self.tools[tool_name]
            result = await tool.execute(arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result)
                        }
                    ]
                }
            }
        
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return self._error_response(request_id, -32603, f"Tool execution error: {str(e)}")
    
    def _error_response(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
    
    async def run_server(self, host: str = "localhost", port: int = 8765):
        """
        Run the MCP server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        try:
            import websockets
        except ImportError:
            logger.error("websockets library not installed. Run: pip install websockets")
            return
        
        async def handle_websocket(websocket, path):
            """Handle WebSocket connections."""
            logger.info(f"Client connected from {websocket.remote_address}")
            try:
                async for message in websocket:
                    try:
                        request = json.loads(message)
                        response = await self.handle_request(request)
                        await websocket.send(json.dumps(response))
                    except json.JSONDecodeError:
                        error_response = self._error_response(None, -32700, "Parse error")
                        await websocket.send(json.dumps(error_response))
            except websockets.exceptions.ConnectionClosed:
                logger.info("Client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
        
        logger.info(f"Starting MCP server on {host}:{port}")
        async with websockets.serve(handle_websocket, host, port):
            await asyncio.Future()  # Run forever
    
    def run_stdio(self):
        """Run the MCP server over stdio (for direct integration)."""
        logger.info("Starting MCP server over stdio")
        
        try:
            while True:
                try:
                    line = input()
                    if not line.strip():
                        continue
                    
                    request = json.loads(line)
                    response = asyncio.run(self.handle_request(request))
                    print(json.dumps(response))
                    sys.stdout.flush()
                
                except EOFError:
                    break
                except json.JSONDecodeError:
                    error_response = self._error_response(None, -32700, "Parse error")
                    print(json.dumps(error_response))
                    sys.stdout.flush()
                except Exception as e:
                    logger.error(f"Stdio error: {e}")
                    error_response = self._error_response(None, -32603, f"Internal error: {str(e)}")
                    print(json.dumps(error_response))
                    sys.stdout.flush()
        
        except KeyboardInterrupt:
            logger.info("Server stopped by user")


def main():
    """Main entry point for the MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NextCloud Music Player MCP Server")
    parser.add_argument("--mode", choices=["websocket", "stdio"], default="websocket",
                       help="Server mode (default: websocket)")
    parser.add_argument("--host", default="localhost", help="Host to bind to (websocket mode)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to (websocket mode)")
    parser.add_argument("--project-root", type=Path, help="Project root directory")
    
    args = parser.parse_args()
    
    server = MCPServer(project_root=args.project_root)
    
    if args.mode == "websocket":
        asyncio.run(server.run_server(args.host, args.port))
    else:
        server.run_stdio()


if __name__ == "__main__":
    main()