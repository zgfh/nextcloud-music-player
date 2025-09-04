# NextCloud Music Player MCP Plugin

This directory contains the Model Context Protocol (MCP) plugin for the NextCloud Music Player project.

## Overview

The MCP plugin provides automated development tools that can be called by MCP clients to perform common development tasks such as:

- Project scaffolding (creating views, services, components)
- Build automation (compilation, packaging, deployment)
- Test automation (running tests, generating coverage reports)
- Code quality checks (linting, formatting, type checking)
- Deployment automation (creating releases, tagging versions)
- Documentation generation (API docs, user guides, wikis)
- Configuration management (environment setup, validation)

## Usage

### Running the MCP Server

#### WebSocket Mode (Default)
```bash
python mcp_server.py --mode websocket --host localhost --port 8765
```

#### Stdio Mode (for direct integration)
```bash
python mcp_server.py --mode stdio
```

### Available Tools

1. **project_scaffolding** - Create new views, services, or components
2. **build_automation** - Build, package, and deploy the application
3. **test_automation** - Run tests and generate coverage reports
4. **code_quality** - Check code quality, format, and lint
5. **deployment** - Manage releases and deployments
6. **documentation** - Generate and update documentation
7. **configuration** - Manage project configuration

### Example Tool Calls

#### Create a New View
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "project_scaffolding",
    "arguments": {
      "action": "create_view",
      "name": "settings",
      "template": "default"
    }
  }
}
```

#### Build the Application
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "build_automation",
    "arguments": {
      "action": "build",
      "platform": "current",
      "mode": "debug"
    }
  }
}
```

#### Run Tests
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "test_automation",
    "arguments": {
      "action": "run_tests",
      "test_type": "all",
      "verbose": true
    }
  }
}
```

## Integration

The MCP server can be integrated with various development environments:

- **VS Code**: Use MCP extension to connect to the server
- **Command Line**: Use curl or custom scripts to call the API
- **CI/CD**: Integrate with build pipelines for automation
- **IDEs**: Connect via WebSocket or stdio protocols

## Development

To extend the MCP plugin:

1. Create new tools in the `tools/` directory
2. Inherit from `BaseTool` and implement required methods
3. Add the new tool to the server's `_initialize_tools` method
4. Test the tool using the MCP protocol

## Architecture

```
mcp/
├── __init__.py          # Package initialization
├── server.py            # MCP server implementation
└── tools/               # Automation tools
    ├── __init__.py      # Tools package
    ├── base.py          # Base tool class
    ├── project_scaffolding.py
    ├── build_automation.py
    ├── test_automation.py
    ├── code_quality.py
    ├── deployment.py
    ├── documentation.py
    └── configuration.py
```

## Requirements

- Python 3.8+
- asyncio for async operations
- websockets for WebSocket mode (optional)
- Project dependencies for tool functionality

## Error Handling

The MCP server provides comprehensive error handling:

- JSON-RPC 2.0 compliant error responses
- Detailed error logging
- Graceful degradation for missing dependencies
- Tool-specific error handling and recovery