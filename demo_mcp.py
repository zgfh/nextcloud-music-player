#!/usr/bin/env python3
"""
MCP Server Demonstration Script

This script demonstrates the functionality of the NextCloud Music Player MCP plugin
by calling various automation tools and showing their capabilities.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from nextcloud_music_player.mcp.server import MCPServer


async def demo_tools_list(server):
    """Demonstrate listing available tools."""
    print("=" * 60)
    print("MCP TOOLS DEMONSTRATION")
    print("=" * 60)
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = await server.handle_request(request)
    tools = response.get("result", {}).get("tools", [])
    
    print(f"\\nAvailable Tools ({len(tools)}):")
    print("-" * 40)
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool['name']}")
        print(f"   {tool['description']}")
        print()


async def demo_project_scaffolding(server):
    """Demonstrate project scaffolding tool."""
    print("🏗️  PROJECT SCAFFOLDING DEMO")
    print("-" * 40)
    
    # Create a test service
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "project_scaffolding",
            "arguments": {
                "action": "create_service",
                "name": "demo_service"
            }
        }
    }
    
    response = await server.handle_request(request)
    result_text = response["result"]["content"][0]["text"]
    result = eval(result_text)  # Safe here since we control the data
    
    if result["success"]:
        print(f"✅ {result['message']}")
        print(f"   Files created: {result['files_created']}")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    print()


async def demo_test_automation(server):
    """Demonstrate test automation tool."""
    print("🧪 TEST AUTOMATION DEMO")
    print("-" * 40)
    
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "test_automation",
            "arguments": {
                "action": "run_tests",
                "test_type": "unit",
                "verbose": False
            }
        }
    }
    
    response = await server.handle_request(request)
    result_text = response["result"]["content"][0]["text"]
    result = eval(result_text)
    
    print(f"Test execution {'✅ completed' if result['success'] else '❌ failed'}")
    print(f"Test type: {result['test_type']}")
    
    if 'test_results' in result:
        test_results = result['test_results']
        print(f"Tests run: {test_results.get('tests_run', 0)}")
        print(f"Failures: {test_results.get('failures', 0)}")
        print(f"Errors: {test_results.get('errors', 0)}")
    
    print()


async def demo_code_quality(server):
    """Demonstrate code quality tool."""
    print("📊 CODE QUALITY DEMO")
    print("-" * 40)
    
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "code_quality",
            "arguments": {
                "action": "lint",
                "target": "src/",
                "auto_fix": False
            }
        }
    }
    
    response = await server.handle_request(request)
    result_text = response["result"]["content"][0]["text"]
    result = eval(result_text)
    
    print(f"Code linting {'✅ completed' if result['success'] else '❌ failed'}")
    print(f"Target: {result['target']}")
    print(f"Issues found: {len(result.get('issues_found', []))}")
    
    print()


async def demo_configuration(server):
    """Demonstrate configuration tool."""
    print("⚙️  CONFIGURATION DEMO")
    print("-" * 40)
    
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "configuration",
            "arguments": {
                "action": "setup_environment",
                "environment": "development"
            }
        }
    }
    
    response = await server.handle_request(request)
    result_text = response["result"]["content"][0]["text"]
    result = eval(result_text)
    
    if result["success"]:
        print(f"✅ {result['message']}")
        print(f"Environment: {result['environment']}")
        print(f"Config file: {result['config_file']}")
        if 'directories_created' in result:
            print(f"Directories created: {len(result['directories_created'])}")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    print()


async def demo_documentation(server):
    """Demonstrate documentation tool."""
    print("📚 DOCUMENTATION DEMO")
    print("-" * 40)
    
    request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "documentation",
            "arguments": {
                "action": "generate_api_docs",
                "format": "markdown",
                "include_private": False,
                "output_dir": "docs"
            }
        }
    }
    
    response = await server.handle_request(request)
    result_text = response["result"]["content"][0]["text"]
    result = eval(result_text)
    
    if result["success"]:
        print(f"✅ {result['message']}")
        print(f"Format: {result['format']}")
        print(f"Output directory: {result['output_dir']}")
        print(f"Files generated: {len(result['files_generated'])}")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    print()


async def main():
    """Main demonstration function."""
    print("NextCloud Music Player - MCP Plugin Demonstration")
    print("=" * 60)
    
    # Initialize MCP server
    try:
        server = MCPServer()
        print(f"🚀 MCP Server initialized with {len(server.tools)} tools")
    except Exception as e:
        print(f"❌ Failed to initialize MCP server: {e}")
        return
    
    # Run demonstrations
    demos = [
        demo_tools_list,
        demo_project_scaffolding,
        demo_test_automation,
        demo_code_quality,
        demo_configuration,
        demo_documentation
    ]
    
    for demo in demos:
        try:
            await demo(server)
            await asyncio.sleep(0.5)  # Small delay between demos
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            print()
    
    print("=" * 60)
    print("🎉 MCP Plugin demonstration completed!")
    print()
    print("To use the MCP server:")
    print("1. WebSocket mode: python mcp_server.py --mode websocket")
    print("2. Stdio mode: python mcp_server.py --mode stdio")
    print("3. Custom project: python mcp_server.py --project-root /path/to/project")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 Demonstration interrupted by user")
    except Exception as e:
        print(f"\\n❌ Demonstration failed: {e}")
        sys.exit(1)