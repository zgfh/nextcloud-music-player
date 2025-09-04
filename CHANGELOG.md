# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-09-04

### Added
- Initial release of NextCloud Music Player
- NextCloud server integration for music synchronization
- Cross-platform music playback using Toga and pygame
- Playlist management with shuffle, repeat, and loop modes
- Volume control and progress bar
- Song metadata display (artist, album, title)
- Offline music caching with smart sync
- Mobile-optimized interface with emoji-based controls
- Background audio playback support for iOS
- Comprehensive unit test suite
- Logging system with file and console output

### Features
- **Audio Playback**: Full-featured music player with play/pause/stop/skip controls
- **NextCloud Integration**: 
  - Automatic synchronization with NextCloud music folders
  - Incremental sync (only downloads new files)
  - Folder selection for targeted synchronization
  - Offline cache management with size tracking
- **Playlist Management**:
  - Multiple playback modes (normal, shuffle, repeat, loop)
  - Previous/next song navigation
  - Song queue management
- **User Interface**:
  - Tabbed interface design (Connection, Files, Playback)
  - Play progress bar with time display
  - Volume control slider (0-100%)
  - Beautiful emoji-based control buttons
  - Responsive design for mobile adaptation
- **Cross-Platform Support**:
  - Windows, macOS, Linux desktop support
  - iOS and Android mobile support
  - Platform-specific audio optimizations
- **Technical Features**:
  - Smart metadata extraction from audio files
  - Cache persistence and validation
  - Enhanced error handling with user-friendly messages
  - Background processing for file operations

### Supported Platforms
- Windows (10+)
- macOS (10.14+)
- Linux (Ubuntu 20.04+)
- iOS (13+)
- Android (API 21+)
- Web browsers (experimental)

### Dependencies
- Toga (cross-platform GUI framework)
- pygame (audio playback)
- httpx (HTTP client for NextCloud API)
- mutagen (audio metadata)
- pathlib (file system operations)

### Installation
See README.md for detailed installation and setup instructions.

### Known Issues
- iOS background playback requires specific entitlements
- Android audio focus handling needs testing
- Web platform has limited audio codec support

### Future Plans
- Lyrics display support
- Audio visualization
- Equalizer controls
- Cloud storage provider integration beyond NextCloud
- Last.fm scrobbling support
