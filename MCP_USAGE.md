# NextCloud Music Player - MCP Plugin Integration Examples

This document provides examples of how to integrate and use the MCP plugin with different tools and environments.

## Quick Start

### 1. Run the MCP Server

```bash
# WebSocket mode (default)
python mcp_server.py --mode websocket --host localhost --port 8765

# Stdio mode for direct integration
python mcp_server.py --mode stdio

# Custom project root
python mcp_server.py --project-root /path/to/your/project
```

### 2. Test the Server

```bash
# Run the demonstration script
python demo_mcp.py
```

## Integration Examples

### VS Code with MCP Extension

1. Install an MCP-compatible extension in VS Code
2. Configure connection to `ws://localhost:8765`
3. Available commands will appear in the command palette

### curl Commands

```bash
# List available tools
curl -X POST http://localhost:8765 \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'

# Create a new view
curl -X POST http://localhost:8765 \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "project_scaffolding",
      "arguments": {
        "action": "create_view",
        "name": "my_new_view"
      }
    }
  }'
```

### Python Client Example

```python
import asyncio
import json
import websockets

async def call_mcp_tool():
    uri = "ws://localhost:8765"
    
    async with websockets.connect(uri) as websocket:
        # List tools
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        await websocket.send(json.dumps(request))
        response = await websocket.recv()
        print("Available tools:", json.loads(response))
        
        # Call a tool
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "build_automation",
                "arguments": {
                    "action": "build",
                    "platform": "current"
                }
            }
        }
        
        await websocket.send(json.dumps(request))
        response = await websocket.recv()
        print("Build result:", json.loads(response))

# Run the client
asyncio.run(call_mcp_tool())
```

### CI/CD Integration

```yaml
# GitHub Actions example
name: MCP Automation
on: [push, pull_request]

jobs:
  automate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -e .
          
      - name: Run MCP automation
        run: |
          # Start MCP server in background
          python mcp_server.py --mode stdio &
          MCP_PID=$!
          
          # Run automated tasks
          echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"test_automation","arguments":{"action":"run_tests"}}}' | python mcp_server.py --mode stdio
          
          # Clean up
          kill $MCP_PID
```

## Tool Usage Examples

### Project Scaffolding

```bash
# Create a new view
python -c "
import asyncio, json, sys
sys.path.insert(0, 'src')
from nextcloud_music_player.mcp.server import MCPServer

async def create_view():
    server = MCPServer()
    request = {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {
            'name': 'project_scaffolding',
            'arguments': {'action': 'create_view', 'name': 'settings'}
        }
    }
    response = await server.handle_request(request)
    print(json.dumps(response, indent=2))

asyncio.run(create_view())
"
```

### Build Automation

```bash
# Build and package for multiple platforms
python -c "
import asyncio, json, sys
sys.path.insert(0, 'src')
from nextcloud_music_player.mcp.server import MCPServer

async def build_all():
    server = MCPServer()
    platforms = ['windows', 'macos', 'linux']
    
    for platform in platforms:
        request = {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {
                'name': 'build_automation',
                'arguments': {'action': 'package', 'platform': platform}
            }
        }
        response = await server.handle_request(request)
        print(f'Build {platform}: {response[\"result\"][\"content\"][0][\"text\"]}')

asyncio.run(build_all())
"
```

### Documentation Generation

```bash
# Generate comprehensive documentation
python -c "
import asyncio, json, sys
sys.path.insert(0, 'src')
from nextcloud_music_player.mcp.server import MCPServer

async def generate_docs():
    server = MCPServer()
    actions = ['generate_api_docs', 'update_readme', 'create_user_guide']
    
    for action in actions:
        request = {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {
                'name': 'documentation',
                'arguments': {'action': action, 'format': 'markdown'}
            }
        }
        response = await server.handle_request(request)
        print(f'{action}: completed')

asyncio.run(generate_docs())
"
```

## Advanced Usage

### Custom Tool Development

```python
# Create a custom tool
from nextcloud_music_player.mcp.tools.base import BaseTool

class CustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "custom_tool"
    
    @property
    def description(self) -> str:
        return "Custom automation tool"
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["custom_action"]}
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: dict):
        # Custom implementation
        return {"success": True, "message": "Custom action completed"}

# Register the tool with the server
server = MCPServer()
server.tools["custom_tool"] = CustomTool(server.project_root)
```

### Batch Operations

```python
# Run multiple operations in sequence
import asyncio
from nextcloud_music_player.mcp.server import MCPServer

async def batch_operations():
    server = MCPServer()
    
    operations = [
        ("test_automation", {"action": "run_tests"}),
        ("code_quality", {"action": "lint", "target": "src/"}),
        ("build_automation", {"action": "build"}),
        ("deployment", {"action": "create_release", "version": "1.0.0"})
    ]
    
    for tool_name, args in operations:
        request = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool_name, "arguments": args}
        }
        response = await server.handle_request(request)
        print(f"{tool_name}: {'✅' if 'success' in str(response) else '❌'}")

asyncio.run(batch_operations())
```

## Error Handling

All MCP responses follow JSON-RPC 2.0 error format:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Internal error: Tool execution failed"
  }
}
```

Common error codes:
- `-32700`: Parse error
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error

## Best Practices

1. **Always check responses** for success/error status
2. **Use appropriate timeouts** for long-running operations
3. **Handle network errors** gracefully in clients
4. **Validate input parameters** before sending requests
5. **Log operations** for debugging and auditing
6. **Use batch operations** for multiple related tasks
7. **Monitor server health** in production environments

## Support

For issues and questions:
- Check the MCP plugin documentation in `src/nextcloud_music_player/mcp/README.md`
- Run `python demo_mcp.py` to test functionality
- Review the source code in `src/nextcloud_music_player/mcp/`
- Open issues on the project GitHub repository