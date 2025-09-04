"""
Documentation automation tool.

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
            lines = content.split('\\n')
            
            module_info = {
                "file": str(py_file),
                "docstring": "",
                "classes": [],
                "functions": []
            }
            
            current_item = None
            current_docstring = []
            in_docstring = False
            
            for line in lines:
                stripped = line.strip()
                
                # Look for module docstring at the top
                if stripped.startswith('"""') and not module_info["docstring"]:
                    if stripped.count('"""') == 2:
                        # Single line docstring
                        module_info["docstring"] = stripped.strip('"""').strip()
                    else:
                        in_docstring = True
                        current_docstring = [stripped.lstrip('"""')]
                elif in_docstring and '"""' in stripped:
                    current_docstring.append(stripped.rstrip('"""'))
                    module_info["docstring"] = '\\n'.join(current_docstring).strip()
                    in_docstring = False
                    current_docstring = []
                elif in_docstring:
                    current_docstring.append(stripped)
                
                # Look for class definitions
                elif stripped.startswith('class '):
                    class_name = stripped.split('(')[0].replace('class ', '').strip()
                    if include_private or not class_name.startswith('_'):
                        module_info["classes"].append({
                            "name": class_name,
                            "line": line,
                            "docstring": ""
                        })
                
                # Look for function definitions
                elif stripped.startswith('def '):
                    func_name = stripped.split('(')[0].replace('def ', '').strip()
                    if include_private or not func_name.startswith('_'):
                        module_info["functions"].append({
                            "name": func_name,
                            "line": line,
                            "docstring": ""
                        })
            
            return module_info
        
        except Exception as e:
            self.logger.error(f"Error extracting docs from {py_file}: {e}")
            return None
    
    def _format_as_markdown(self, doc_content: Dict[str, Any], module_name: str) -> str:
        """Format documentation content as markdown."""
        md_content = f"# {module_name}\\n\\n"
        
        if doc_content.get("docstring"):
            md_content += f"{doc_content['docstring']}\\n\\n"
        
        if doc_content.get("classes"):
            md_content += "## Classes\\n\\n"
            for cls in doc_content["classes"]:
                md_content += f"### {cls['name']}\\n\\n"
                md_content += f"```python\\n{cls['line']}\\n```\\n\\n"
                if cls.get("docstring"):
                    md_content += f"{cls['docstring']}\\n\\n"
        
        if doc_content.get("functions"):
            md_content += "## Functions\\n\\n"
            for func in doc_content["functions"]:
                md_content += f"### {func['name']}\\n\\n"
                md_content += f"```python\\n{func['line']}\\n```\\n\\n"
                if func.get("docstring"):
                    md_content += f"{func['docstring']}\\n\\n"
        
        return md_content
    
    def _create_api_index(self, generated_docs: list, format_type: str) -> str:
        """Create API documentation index."""
        if format_type == "markdown":
            content = "# API Documentation\\n\\n"
            content += "This directory contains auto-generated API documentation.\\n\\n"
            content += "## Modules\\n\\n"
            
            for doc_file in generated_docs:
                doc_path = Path(doc_file)
                module_name = doc_path.stem.replace("_", "/")
                content += f"- [{module_name}]({doc_path.name})\\n"
            
            return content
        
        return "API Documentation Index"
    
    async def _generate_readme_content(self) -> str:
        """Generate README content based on project structure."""
        # Read existing README for reference
        readme_path = self.project_root / "README.md"
        existing_content = ""
        
        if readme_path.exists():
            existing_content = self.read_file(readme_path)
        
        # Get project info from pyproject.toml
        try:
            pyproject_path = self.project_root / "pyproject.toml"
            if pyproject_path.exists():
                # Simple parsing without tomllib
                pyproject_content = self.read_file(pyproject_path)
                
                # Extract basic info
                name = "NextCloud Music Player"
                description = "A cross-platform music player with NextCloud integration"
                
                for line in pyproject_content.split('\\n'):
                    if line.strip().startswith('name = '):
                        name = line.split('=')[1].strip().strip('"')
                    elif line.strip().startswith('description = '):
                        description = line.split('=')[1].strip().strip('"')
        except:
            name = "NextCloud Music Player"
            description = "A cross-platform music player with NextCloud integration"
        
        # Generate new README
        readme_content = f"""# {name}

{description}

## Features

- Cross-platform music player built with BeeWare Toga
- NextCloud integration for cloud music storage
- Local caching for offline playback
- Modern UI with playlist management
- Multiple platform support (Windows, macOS, Linux, iOS, Android)

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/example/nextcloud-music-player.git
   cd nextcloud-music-player
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Run the application:
   ```bash
   python -m briefcase dev
   ```

## Usage

1. Launch the application
2. Configure your NextCloud server settings
3. Sync your music files
4. Enjoy your music!

## Development

### Requirements

- Python 3.8+
- BeeWare Briefcase
- NextCloud server

### Running Tests

```bash
python -m unittest discover tests/
```

### Building

```bash
python -m briefcase build
python -m briefcase package
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the BSD 3-Clause License - see the LICENSE file for details.

## Support

For support, please open an issue on GitHub.
"""
        
        return readme_content
    
    def _create_installation_guide(self) -> str:
        """Create installation guide content."""
        return """# Installation Guide

## System Requirements

- **Operating System**: Windows 10+, macOS 10.14+, Ubuntu 18.04+
- **Python**: 3.8 or higher (for development)
- **Memory**: 4GB RAM minimum
- **Storage**: 500MB free space
- **Network**: Internet connection for NextCloud sync

## Installation Methods

### Option 1: Pre-built Packages (Recommended)

Download the appropriate installer for your platform from the [Releases page](https://github.com/example/nextcloud-music-player/releases).

#### Windows
1. Download the `.msi` installer
2. Double-click to run the installer
3. Follow the installation wizard

#### macOS
1. Download the `.dmg` file
2. Open the disk image
3. Drag the app to Applications folder

#### Linux (Ubuntu/Debian)
1. Download the `.deb` package
2. Install using: `sudo dpkg -i nextcloud-music-player_*.deb`
3. If dependencies are missing: `sudo apt-get install -f`

### Option 2: From Source

See the [Development Setup Guide](Development-Setup.md) for building from source.

## First Run

1. Launch the application
2. Go to the "Connection" tab
3. Enter your NextCloud server details
4. Test the connection
5. Select your music folder
6. Sync your music files

## Troubleshooting

If you encounter issues, see the [Troubleshooting Guide](troubleshooting.md).
"""
    
    def _create_quick_start_guide(self) -> str:
        """Create quick start guide content."""
        return """# Quick Start Guide

Get up and running with NextCloud Music Player in just a few minutes!

## Step 1: Setup NextCloud Connection

1. Open the app and go to the **Connection** tab
2. Enter your NextCloud server URL (e.g., `https://your-nextcloud.com`)
3. Enter your username and password
4. Click **Test Connection** to verify

## Step 2: Configure Music Sync

1. In the **Sync Folder** field, enter your music folder path (e.g., `/Music`)
2. Click **Sync Music Files** to download your music
3. Wait for the sync to complete

## Step 3: Start Playing Music

1. Go to the **File List** tab to see your synced music
2. Double-click a song to start playing
3. Use the **Playback** tab for controls

## Key Features

### Playback Controls
- **▶️/⏸️**: Play/Pause
- **⏮️/⏭️**: Previous/Next track
- **🔁**: Repeat modes (off/single/all)
- **🔀**: Shuffle mode
- **Volume slider**: Adjust playback volume

### Playlist Management
- Add songs to playlist by selecting and clicking **Add to Playlist**
- Clear playlist with **Clear Playlist**
- Songs are automatically added when double-clicked

### Offline Mode
- Once synced, music plays offline
- Check cache status in the File List

## Tips

- Use **Test Connection** before syncing to avoid errors
- Larger music libraries take longer to sync initially
- The app remembers your settings between sessions
- Check the logs if you encounter issues

Ready to enjoy your music! 🎵
"""
    
    def _create_configuration_guide(self) -> str:
        """Create configuration guide content."""
        return """# Configuration Guide

## NextCloud Server Settings

### Server URL
- Format: `https://your-nextcloud-server.com`
- Include protocol (http:// or https://)
- No trailing slash

### Authentication
- **Username**: Your NextCloud username
- **Password**: Use App Password (recommended) or account password

### Creating App Password
1. Log into NextCloud web interface
2. Go to Settings → Security
3. Create new App Password
4. Use this password in the music player

## Music Sync Configuration

### Sync Folder
- Path to your music folder in NextCloud
- Examples: `/Music`, `/Media/Audio`, `/Shared/Music`
- Case-sensitive

### Cache Settings
- Local cache location: `~/.nextcloud-music-player/cache/`
- Cache is automatically managed
- Clear cache by deleting the cache folder

## Audio Settings

### Supported Formats
- MP3 (recommended)
- FLAC
- AAC
- WAV
- OGG

### Performance
- Larger files take longer to sync
- Local playback is always smooth once cached
- Network speed affects sync time

## Advanced Configuration

### Log Files
- Location: `~/.nextcloud-music-player/logs/`
- Useful for troubleshooting
- Automatically rotated

### Configuration File
- Location: `~/.nextcloud-music-player/config.json`
- Contains all settings
- Can be manually edited (advanced users)

### Custom SSL Certificates
For self-signed certificates, you may need to:
1. Add certificate to system trust store
2. Or use HTTP instead of HTTPS (not recommended)

## Troubleshooting Configuration

### Connection Issues
- Verify server URL is correct
- Check username/password
- Test network connectivity
- Check firewall settings

### Sync Issues  
- Verify folder path exists
- Check folder permissions
- Ensure sufficient storage space
- Check network stability

### Performance Issues
- Close other applications
- Check available memory
- Consider smaller sync folders
- Update to latest version
"""
    
    def _create_troubleshooting_guide(self) -> str:
        """Create troubleshooting guide content."""
        return """# Troubleshooting Guide

## Common Issues

### Connection Problems

#### "Cannot connect to server"
- **Check URL**: Ensure server URL is correct and accessible
- **Check credentials**: Verify username and password
- **Network**: Test internet connection
- **Firewall**: Check if firewall blocks the app

#### "SSL Certificate Error"
- Use App Password instead of regular password
- Check if server uses valid SSL certificate
- Try HTTP instead of HTTPS (temporary solution)

### Sync Issues

#### "No files found"
- Verify music folder path exists in NextCloud
- Check folder permissions
- Ensure folder contains supported audio files

#### "Sync fails partway through"
- Check network stability
- Ensure sufficient local storage space
- Try syncing smaller folder first

### Playback Issues

#### "No sound"
- Check system volume
- Check app volume slider
- Verify audio drivers are working
- Try different audio file

#### "Choppy playback"
- Check if file is fully cached
- Close other applications
- Check system performance
- Update audio drivers

## Log Files

### Accessing Logs
1. **Windows**: `%APPDATA%\\nextcloud-music-player\\logs\\`
2. **macOS**: `~/Library/Application Support/nextcloud-music-player/logs/`
3. **Linux**: `~/.nextcloud-music-player/logs/`

### Log Levels
- **ERROR**: Critical issues
- **WARNING**: Potential problems
- **INFO**: General information
- **DEBUG**: Detailed debugging info

## Reset Options

### Clear Cache
Delete the cache folder to force re-download:
- **Windows**: `%APPDATA%\\nextcloud-music-player\\cache\\`
- **macOS**: `~/Library/Application Support/nextcloud-music-player/cache/`
- **Linux**: `~/.nextcloud-music-player/cache/`

### Reset Settings
Delete configuration file to reset all settings:
- **Windows**: `%APPDATA%\\nextcloud-music-player\\config.json`
- **macOS**: `~/Library/Application Support/nextcloud-music-player/config.json`
- **Linux**: `~/.nextcloud-music-player/config.json`

## Getting Help

### Before Reporting Issues
1. Check this troubleshooting guide
2. Review log files for errors
3. Try resetting cache/settings
4. Update to latest version

### Reporting Bugs
Include the following information:
- Operating system and version
- App version
- NextCloud server version
- Error messages from logs
- Steps to reproduce the issue

### Support Channels
- **GitHub Issues**: [Project Issues Page](https://github.com/example/nextcloud-music-player/issues)
- **Documentation**: [Project Wiki](https://github.com/example/nextcloud-music-player/wiki)

## Performance Tips

- Use wired internet for initial sync
- Sync during off-peak hours
- Use MP3 format for better compatibility
- Keep music library organized in NextCloud
- Regular cache cleanup for heavy users
"""
    
    def _create_faq(self) -> str:
        """Create FAQ content."""
        return """# Frequently Asked Questions

## General Questions

### Q: What is NextCloud Music Player?
A: It's a cross-platform music player that syncs with your NextCloud server, allowing you to access your music collection anywhere.

### Q: What platforms are supported?
A: Windows, macOS, Linux, iOS, and Android (mobile platforms in development).

### Q: Is it free?
A: Yes, it's open source and completely free to use.

## Setup Questions

### Q: Do I need a NextCloud server?
A: Yes, you need access to a NextCloud server to sync your music. You can use a self-hosted server or a hosted service.

### Q: Can I use it without internet?
A: Yes, once your music is synced and cached locally, you can play it offline.

### Q: What audio formats are supported?
A: MP3, FLAC, AAC, WAV, and OGG formats are supported.

## Usage Questions

### Q: How do I add music to my library?
A: Upload music files to your NextCloud server, then sync them using the app.

### Q: Can I create playlists?
A: Yes, the app supports playlist creation and management.

### Q: How much storage does the app use?
A: The app caches music locally, so storage usage depends on your music library size.

## Technical Questions

### Q: Where are my settings stored?
A: Settings are stored in your user data directory, typically `~/.nextcloud-music-player/`

### Q: Can I sync multiple music folders?
A: Currently, only one sync folder is supported per configuration.

### Q: How do I update the app?
A: Download the latest version from the releases page, or use your system's package manager if available.

## Troubleshooting Questions

### Q: The app won't connect to my server. What should I do?
A: Check your server URL, credentials, and network connection. Use the "Test Connection" feature to diagnose issues.

### Q: My music isn't syncing. Why?
A: Verify the sync folder path exists in NextCloud and contains audio files. Check the logs for specific error messages.

### Q: The app is running slowly. How can I improve performance?
A: Close other applications, ensure sufficient system memory, and consider syncing smaller music collections.

## Security Questions

### Q: Is my music data secure?
A: Music is transferred using your NextCloud server's security protocols (typically HTTPS). Local cache is stored on your device.

### Q: Should I use my regular NextCloud password?
A: For better security, create an App Password in NextCloud settings and use that instead.

### Q: Can others access my cached music?
A: Cached music is stored in your user directory with standard file permissions. Ensure your device is properly secured.

## Development Questions

### Q: Is the source code available?
A: Yes, it's open source and available on GitHub.

### Q: Can I contribute to the project?
A: Absolutely! Check the contributing guidelines in the repository.

### Q: How do I report bugs or request features?
A: Use the GitHub Issues page to report bugs or request new features.

## Still Need Help?

If your question isn't answered here, please:
1. Check the full documentation
2. Search existing GitHub issues
3. Create a new issue with detailed information
"""
    
    def _create_user_guide_toc(self, sections: list, format_type: str) -> str:
        """Create table of contents for user guide."""
        if format_type == "markdown":
            content = "# User Guide\\n\\n"
            content += "Welcome to the NextCloud Music Player user guide!\\n\\n"
            content += "## Table of Contents\\n\\n"
            
            for section in sections:
                section_title = section.replace("_", " ").title()
                content += f"- [{section_title}]({section}.{format_type})\\n"
            
            return content
        
        return "User Guide Table of Contents"
    
    def _create_wiki_home(self) -> str:
        """Create wiki home page."""
        return """# NextCloud Music Player Wiki

Welcome to the NextCloud Music Player project wiki!

## Overview

NextCloud Music Player is a cross-platform music player application built with BeeWare Toga that integrates with NextCloud servers for cloud music storage and synchronization.

## Key Features

- **Cross-Platform**: Runs on Windows, macOS, Linux, iOS, and Android
- **Cloud Integration**: Seamless NextCloud server integration
- **Offline Playback**: Local caching for music files
- **Modern UI**: Clean, intuitive interface built with Toga
- **Playlist Management**: Create and manage playlists
- **Multiple Formats**: Support for MP3, FLAC, AAC, and more

## Quick Links

- [Architecture Overview](Architecture.md)
- [Development Setup](Development-Setup.md)
- [Contributing Guidelines](Contributing.md)
- [API Reference](API-Reference.md)

## Getting Started

For end users:
1. Download the latest release
2. Install on your platform
3. Configure NextCloud connection
4. Start enjoying your music!

For developers:
1. Clone the repository
2. Set up development environment
3. Read the contributing guidelines
4. Start coding!

## Project Structure

```
nextcloud-music-player/
├── src/nextcloud_music_player/    # Main application code
├── tests/                         # Test suite
├── docs/                          # Documentation
├── scripts/                       # Build and utility scripts
└── pyproject.toml                # Project configuration
```

## Community

- **Issues**: Report bugs and request features on GitHub
- **Discussions**: Join conversations about the project
- **Contributing**: Help improve the project

## License

This project is licensed under the BSD 3-Clause License.
"""
    
    def _create_architecture_docs(self) -> str:
        """Create architecture documentation."""
        return """# Architecture Overview

## System Architecture

NextCloud Music Player follows a modular architecture pattern with clear separation of concerns.

### Core Components

#### 1. Application Layer (`app.py`)
- Main application entry point
- Toga app initialization and lifecycle management
- UI coordination and event handling

#### 2. UI Layer (`views/`)
- **Connection View**: NextCloud server configuration
- **File List View**: Music library browsing
- **Playback View**: Music player controls
- **View Manager**: Coordinates view transitions

#### 3. Service Layer (`services/`)
- **Music Service**: Music file management and metadata
- **Playback Service**: Audio playback control
- **Playlist Manager**: Playlist creation and management

#### 4. Data Layer
- **NextCloud Client**: Server communication and file sync
- **Music Library**: Local music file organization
- **Config Manager**: Application settings persistence

#### 5. Platform Layer
- **Platform Audio**: Platform-specific audio handling
- **iOS Background Audio**: iOS-specific background playback

## Data Flow

### 1. Music Sync Flow
```
User Input → Connection View → NextCloud Client → File Download → Local Cache → Music Library → File List View
```

### 2. Playback Flow
```
User Selection → File List View → Playback Service → Platform Audio → Audio Output
```

### 3. Configuration Flow
```
User Settings → Connection View → Config Manager → Local Storage
```

## Key Design Patterns

### 1. Model-View-Controller (MVC)
- **Model**: Music Library, Config Manager
- **View**: UI views and components
- **Controller**: Services and application logic

### 2. Observer Pattern
- Event-driven communication between components
- UI updates based on service state changes

### 3. Strategy Pattern
- Platform-specific audio implementations
- Multiple authentication methods

## Technology Stack

### Core Framework
- **BeeWare Toga**: Cross-platform UI framework
- **Python 3.8+**: Core programming language

### Dependencies
- **requests/httpx**: HTTP client for NextCloud API
- **pygame**: Audio playback (desktop platforms)
- **platform-specific**: Native audio APIs (mobile)

### Development Tools
- **briefcase**: Application packaging and distribution
- **pytest**: Testing framework
- **black/flake8**: Code formatting and linting

## Platform Considerations

### Desktop (Windows, macOS, Linux)
- Full feature support
- File system access
- Native audio APIs

### Mobile (iOS, Android)
- Background playback support
- Optimized for touch interfaces
- Platform-specific permissions

### Web (Future)
- Browser-based playback
- Progressive Web App (PWA) features
- Limited file system access

## Security Architecture

### Data Protection
- HTTPS communication with NextCloud
- Local cache encryption (planned)
- Secure credential storage

### Authentication
- NextCloud username/password
- App-specific passwords (recommended)
- OAuth integration (planned)

## Performance Considerations

### Caching Strategy
- Intelligent prefetching
- LRU cache eviction
- Configurable cache limits

### Memory Management
- Streaming for large files
- Lazy loading of metadata
- Garbage collection optimization

### Network Optimization
- Delta sync for updates
- Compression for transfers
- Offline mode support

## Extension Points

### Plugin Architecture (Planned)
- Custom audio formats
- Additional cloud providers
- UI themes and customization

### API Integration
- Music metadata services
- Lyrics providers
- Social sharing features

## Testing Strategy

### Unit Tests
- Individual component testing
- Mock external dependencies
- High code coverage

### Integration Tests
- Component interaction testing
- NextCloud server integration
- Platform-specific testing

### End-to-End Tests
- Complete user workflows
- Multi-platform validation
- Performance testing
"""
    
    def _create_contributing_guide(self) -> str:
        """Create contributing guide."""
        return """# Contributing to NextCloud Music Player

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Git
- BeeWare Briefcase
- NextCloud server (for testing)

### Development Setup
1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/nextcloud-music-player.git
   cd nextcloud-music-player
   ```
3. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
   ```
4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Development Workflow

### 1. Create a Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes
- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes
```bash
# Run unit tests
python -m pytest tests/

# Run the application
python -m briefcase dev

# Test specific functionality
python -m tests.test_basic
```

### 4. Commit Changes
```bash
git add .
git commit -m "Add feature: description of what you added"
```

### 5. Push and Create PR
```bash
git push origin feature/your-feature-name
```
Then create a Pull Request on GitHub.

## Code Style Guidelines

### Python Code Style
- Follow PEP 8
- Use type hints where appropriate
- Maximum line length: 88 characters (Black default)
- Use meaningful variable and function names

### Code Formatting
We use automated tools for code formatting:
```bash
# Format code
black src/ tests/

# Check style
flake8 src/ tests/

# Sort imports
isort src/ tests/
```

### Documentation
- Add docstrings to all public functions and classes
- Update README for significant changes
- Create/update user guides for new features

## Testing Guidelines

### Writing Tests
- Write tests for all new functionality
- Maintain or improve test coverage
- Use descriptive test names
- Follow the existing test structure

### Test Categories
- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **Platform Tests**: Test platform-specific functionality

### Running Tests
```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m tests.test_basic

# With coverage
python -m pytest tests/ --cov=src/nextcloud_music_player
```

## Contribution Types

### Bug Fixes
- Check if issue already exists
- Create minimal reproduction case
- Write test that demonstrates the bug
- Fix the bug and ensure test passes

### New Features
- Discuss feature in GitHub Issues first
- Start with a design document for large features
- Implement incrementally
- Add comprehensive tests

### Documentation
- Improve existing documentation
- Add missing documentation
- Create tutorials and guides
- Fix typos and grammar

### Performance Improvements
- Profile before optimizing
- Include benchmarks in PR
- Consider impact on different platforms

## Platform-Specific Development

### Desktop Development
- Test on Windows, macOS, and Linux
- Consider platform UI guidelines
- Handle platform-specific file paths

### Mobile Development
- Test background behavior
- Consider touch interfaces
- Handle mobile-specific permissions

## Code Review Process

### Submitting PRs
- Fill out the PR template completely
- Link to related issues
- Include screenshots for UI changes
- Add tests and documentation

### Review Criteria
- Code quality and style
- Test coverage
- Documentation completeness
- Performance impact
- Cross-platform compatibility

## Release Process

### Version Numbering
We use Semantic Versioning (SemVer):
- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes

### Release Checklist
- [ ] Update version numbers
- [ ] Update CHANGELOG.md
- [ ] Create git tag
- [ ] Build all platform packages
- [ ] Upload to release page
- [ ] Update documentation

## Community Guidelines

### Code of Conduct
- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn
- Report inappropriate behavior

### Communication
- Use GitHub Issues for bugs and features
- Use Discussions for questions and ideas
- Be clear and specific in descriptions
- Search existing issues before creating new ones

## Getting Help

### Questions
- Check existing documentation
- Search GitHub Issues and Discussions
- Ask in project discussions
- Mention maintainers if urgent

### Development Issues
- Include error messages and logs
- Describe your environment
- Provide steps to reproduce
- Mention what you've already tried

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- GitHub contributors page
- Special thanks in major releases

Thank you for contributing to NextCloud Music Player! 🎵
"""
    
    def _create_dev_setup_guide(self) -> str:
        """Create development setup guide."""
        return """# Development Setup Guide

This guide will help you set up a complete development environment for NextCloud Music Player.

## System Requirements

### Minimum Requirements
- **OS**: Windows 10, macOS 10.14, or Ubuntu 18.04+
- **Python**: 3.8 or higher
- **Memory**: 4GB RAM
- **Storage**: 2GB free space
- **Network**: Internet connection for dependencies

### Recommended Requirements
- **Python**: 3.9 or 3.10
- **Memory**: 8GB RAM
- **Storage**: 5GB free space
- **Git**: Latest version

## Initial Setup

### 1. Install Python
Download and install Python from [python.org](https://python.org):
- Windows: Use the Windows installer
- macOS: Use Homebrew (`brew install python`) or official installer
- Linux: Use system package manager (`apt install python3`)

Verify installation:
```bash
python --version  # Should show 3.8+
```

### 2. Install Git
- Windows: Download from [git-scm.com](https://git-scm.com)
- macOS: Install with Xcode Command Line Tools or Homebrew
- Linux: Use package manager (`apt install git`)

### 3. Clone the Repository
```bash
git clone https://github.com/example/nextcloud-music-player.git
cd nextcloud-music-player
```

## Development Environment

### 1. Create Virtual Environment
```bash
python -m venv .venv
```

### 2. Activate Virtual Environment
```bash
# Windows
.venv\\Scripts\\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
# Install in development mode
pip install -e ".[dev]"

# Or install dependencies manually
pip install briefcase toga requests httpx pytest black flake8
```

## IDE Setup

### VS Code (Recommended)
1. Install VS Code
2. Install Python extension
3. Open project folder
4. Select Python interpreter from virtual environment
5. Install recommended extensions:
   - Python
   - Python Docstring Generator
   - Black Formatter
   - GitLens

### PyCharm
1. Open project in PyCharm
2. Configure Python interpreter to use virtual environment
3. Enable code style checking
4. Configure run configurations

## Running the Application

### Development Mode
```bash
# Using briefcase
python -m briefcase dev

# Direct execution
python run.py
```

### Building the Application
```bash
# Create build
python -m briefcase build

# Create package
python -m briefcase package
```

## Testing Setup

### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m tests.test_basic

# Run with coverage
python -m pytest tests/ --cov=src/nextcloud_music_player --cov-report=html
```

### Test Configuration
Tests require:
- No external dependencies by default
- Mock NextCloud server responses
- Isolated test environment

## Platform-Specific Setup

### Windows Development
Additional requirements:
- Visual Studio Build Tools (for some packages)
- Windows SDK (for native features)

### macOS Development
Additional requirements:
- Xcode Command Line Tools
- For iOS development: Full Xcode

### Linux Development
Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install python3-dev build-essential

# For Toga GTK backend
sudo apt-get install libgirepository1.0-dev libcairo2-dev libpango1.0-dev libwebkit2gtk-4.0-dev gir1.2-webkit2-4.0
```

## NextCloud Test Server

### Local NextCloud Setup
For development, set up a local NextCloud instance:

1. **Using Docker** (Recommended):
   ```bash
   docker run -d -p 8080:80 --name nextcloud nextcloud
   ```

2. **Manual Installation**:
   - Download NextCloud
   - Set up web server (Apache/Nginx)
   - Configure database
   - Complete web setup

### Test Data
Create test music files:
1. Upload MP3 files to NextCloud
2. Create folder structure: `/Music/Artist/Album/`
3. Add metadata to files
4. Create test playlists

## Code Quality Tools

### Automated Formatting
```bash
# Format Python code
black src/ tests/

# Sort imports
isort src/ tests/

# Check style
flake8 src/ tests/
```

### Type Checking
```bash
# Install mypy
pip install mypy

# Run type checking
mypy src/nextcloud_music_player/
```

### Pre-commit Hooks
Install pre-commit hooks to automate quality checks:
```bash
pip install pre-commit
pre-commit install
```

## Debugging

### VS Code Debugging
1. Set breakpoints in code
2. Use F5 to start debugging
3. Configure launch.json for different scenarios

### Console Debugging
Add debug prints:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Network Debugging
Use tools to monitor NextCloud communication:
- Browser developer tools
- Wireshark for network analysis
- NextCloud logs

## Performance Profiling

### Python Profiling
```bash
# Profile script execution
python -m cProfile -o profile.out run.py

# Analyze profile
python -c "import pstats; pstats.Stats('profile.out').sort_stats('cumulative').print_stats(10)"
```

### Memory Profiling
```bash
pip install memory-profiler
python -m memory_profiler run.py
```

## Continuous Integration

### Local CI Simulation
Before pushing, run the same checks as CI:
```bash
# Run tests
python -m pytest tests/

# Check code style
black --check src/ tests/
flake8 src/ tests/

# Build application
python -m briefcase build
```

## Common Issues

### Import Errors
- Ensure virtual environment is activated
- Check PYTHONPATH includes src directory
- Verify all dependencies are installed

### Build Failures
- Update briefcase to latest version
- Check platform-specific requirements
- Clear build cache and retry

### Test Failures
- Check if NextCloud server is available
- Verify test data exists
- Run tests individually to isolate issues

## Getting Help

### Documentation
- Read existing code comments
- Check project documentation
- Review similar projects

### Community Support
- GitHub Issues for bugs
- GitHub Discussions for questions
- Stack Overflow for general Python issues

### Code Review
- Submit small, focused PRs
- Include tests and documentation
- Respond to review feedback promptly

## Next Steps

Once your development environment is set up:
1. Run the test suite to verify everything works
2. Make a small change and test it
3. Read the contributing guidelines
4. Pick an issue to work on
5. Submit your first pull request!

Happy coding! 🎵
"""
    
    def _create_api_reference(self) -> str:
        """Create API reference."""
        return """# API Reference

This document provides a comprehensive reference for the NextCloud Music Player API.

## Core Classes

### NextCloudMusicPlayer
Main application class that coordinates all functionality.

```python
class NextCloudMusicPlayer(toga.App):
    def startup(self) -> None
    def setup_logging(self) -> None
    def on_exit(self, widget) -> bool
```

### NextCloudClient
Handles communication with NextCloud servers.

```python
class NextCloudClient:
    def __init__(self, server_url: str, username: str, password: str)
    async def test_connection(self) -> Dict[str, Any]
    async def list_files(self, path: str) -> List[Dict[str, Any]]
    async def download_file(self, remote_path: str, local_path: str) -> bool
```

### MusicLibrary
Manages local music file storage and metadata.

```python
class MusicLibrary:
    def __init__(self, cache_dir: Path)
    def get_cached_files(self) -> List[Dict[str, Any]]
    def add_file(self, file_info: Dict[str, Any]) -> None
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]
```

### ConfigManager
Handles application configuration persistence.

```python
class ConfigManager:
    def __init__(self, config_dir: Optional[Path] = None)
    def get(self, key: str, default: Any = None) -> Any
    def set(self, key: str, value: Any) -> None
    def save(self) -> None
    def load(self) -> None
```

## Service Classes

### MusicService
Business logic for music management.

```python
class MusicService:
    def __init__(self, app)
    async def sync_music(self) -> Dict[str, Any]
    def get_music_files(self) -> List[Dict[str, Any]]
    def search_music(self, query: str) -> List[Dict[str, Any]]
```

### PlaybackService
Audio playback control and management.

```python
class PlaybackService:
    def __init__(self, app)
    def play(self, file_path: str) -> bool
    def pause(self) -> None
    def stop(self) -> None
    def set_volume(self, volume: float) -> None
    def get_position(self) -> float
    def set_position(self, position: float) -> None
```

### PlaylistManager
Playlist creation and management.

```python
class PlaylistManager:
    def __init__(self)
    def add_song(self, song_info: Dict[str, Any]) -> None
    def remove_song(self, index: int) -> None
    def clear_playlist(self) -> None
    def get_current_song(self) -> Optional[Dict[str, Any]]
    def next_song(self) -> Optional[Dict[str, Any]]
    def previous_song(self) -> Optional[Dict[str, Any]]
```

## View Classes

### ConnectionView
NextCloud server configuration interface.

```python
class ConnectionView:
    def __init__(self, app)
    def get_container(self) -> toga.Box
    async def test_connection(self, widget) -> None
    def update_connection_status(self, connected: bool) -> None
```

### FileListView
Music library browsing interface.

```python
class FileListView:
    def __init__(self, app)
    def get_container(self) -> toga.Box
    def refresh_file_list(self) -> None
    def on_file_select(self, widget) -> None
    async def sync_files(self, widget) -> None
```

### PlaybackView
Music player control interface.

```python
class PlaybackView:
    def __init__(self, app)
    def get_container(self) -> toga.Box
    def update_now_playing(self, song_info: Dict[str, Any]) -> None
    def update_progress(self, position: float, duration: float) -> None
    async def toggle_play_pause(self, widget) -> None
```

## Utility Functions

### Audio Utilities
```python
def extract_metadata(file_path: str) -> Dict[str, Any]
def format_duration(seconds: float) -> str
def get_supported_formats() -> List[str]
```

### File Utilities
```python
def ensure_directory(path: Path) -> None
def get_file_size(file_path: Path) -> int
def calculate_cache_size(cache_dir: Path) -> int
```

### Network Utilities
```python
def validate_url(url: str) -> bool
def check_internet_connection() -> bool
def download_with_progress(url: str, local_path: str, progress_callback: Callable) -> bool
```

## Configuration Keys

### Server Configuration
- `server_url`: NextCloud server URL
- `username`: NextCloud username
- `password`: NextCloud password (encrypted)
- `sync_folder`: Remote music folder path

### Playback Configuration
- `volume`: Playback volume (0.0-1.0)
- `repeat_mode`: Repeat mode (off/single/all)
- `shuffle_enabled`: Shuffle mode enabled
- `crossfade_duration`: Crossfade duration in seconds

### Cache Configuration
- `cache_dir`: Local cache directory
- `max_cache_size`: Maximum cache size in bytes
- `auto_cleanup`: Enable automatic cache cleanup

### UI Configuration
- `window_width`: Main window width
- `window_height`: Main window height
- `theme`: UI theme (light/dark)

## Events

### Application Events
- `app.startup`: Application startup complete
- `app.shutdown`: Application shutdown initiated

### Connection Events
- `connection.established`: NextCloud connection established
- `connection.lost`: NextCloud connection lost
- `connection.error`: Connection error occurred

### Sync Events
- `sync.started`: Music sync started
- `sync.progress`: Sync progress update
- `sync.completed`: Music sync completed
- `sync.error`: Sync error occurred

### Playback Events
- `playback.started`: Playback started
- `playback.paused`: Playback paused
- `playback.stopped`: Playback stopped
- `playback.position_changed`: Playback position changed
- `playback.song_changed`: Current song changed

## Error Handling

### Exception Classes
```python
class NextCloudError(Exception): pass
class ConnectionError(NextCloudError): pass
class AuthenticationError(NextCloudError): pass
class SyncError(NextCloudError): pass
class PlaybackError(Exception): pass
class ConfigurationError(Exception): pass
```

### Error Codes
- `1001`: Server connection failed
- `1002`: Authentication failed
- `1003`: File not found
- `2001`: Playback initialization failed
- `2002`: Audio format not supported
- `3001`: Configuration file corrupt

## Platform Differences

### Desktop Platforms
All features fully supported.

### iOS Platform
- Background playback supported
- File system access limited
- Network permissions required

### Android Platform
- Background playback supported
- Storage permissions required
- Network permissions required

### Web Platform (Future)
- Limited file system access
- No background processing
- Browser audio API only

## Integration Examples

### Basic Usage
```python
# Initialize application
app = NextCloudMusicPlayer()

# Configure NextCloud connection
config = app.config_manager
config.set('server_url', 'https://my-nextcloud.com')
config.set('username', 'myuser')
config.set('password', 'mypassword')

# Test connection
client = NextCloudClient(config.get('server_url'), config.get('username'), config.get('password'))
result = await client.test_connection()

# Sync music
music_service = MusicService(app)
await music_service.sync_music()

# Start playback
playback_service = PlaybackService(app)
playback_service.play('/path/to/song.mp3')
```

### Custom Integration
```python
# Extend functionality with custom service
class CustomMusicService(MusicService):
    def custom_feature(self):
        # Implementation here
        pass

# Register custom service
app.music_service = CustomMusicService(app)
```

## Testing

### Unit Test Utilities
```python
from tests.utils import MockNextCloudClient, create_test_app

def test_custom_functionality():
    app = create_test_app()
    client = MockNextCloudClient()
    # Test implementation
```

### Integration Test Setup
```python
def setup_test_environment():
    # Create temporary directories
    # Initialize test configuration
    # Setup mock services
    pass
```

For more detailed information, see the source code and inline documentation.
"""