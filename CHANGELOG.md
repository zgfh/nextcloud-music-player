# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **前端框架迁移：Toga (BeeWare) → Flet (Flutter) 0.86.5**
  - 所有视图重写为 Flet：`views/`、`views/components/`
  - 服务层 `services/` 保持框架无关，未改动
  - 导航改为底部 NavigationBar，播放列表/歌词改为 TabBar + TabBarView
  - Python 最低版本要求提升至 3.10（Flet 0.86 要求）
- 构建体系从 Briefcase 切换为 `flet build`（iOS/Android）

### Added
- iOS 一键部署脚本 `scripts/deploy_iso.sh`（自动设备检测、增量构建、自动签名、7 天续签提醒）
- **批量下载整批提交**：选中的歌曲一次性全部提交给原生后台会话（此前逐首提交，切后台后链式提交可能中断，表现为后台不再继续）；此后挂起、锁屏、应用被杀，整个队列都由系统继续执行。`DownloadProgressTracker` 重构为按文件维护的下载列表，设置页下载页逐文件显示状态/进度，菜单副标题显示聚合摘要；顺带修复歌词下载失败会覆盖歌曲下载成功状态的旧问题
- **设置页改为菜单式二级导航**：首页为功能菜单列表（下载进度 / 缓存管理 / 应用日志 / 应用信息），点击进入对应子页面，子页头部返回菜单；下载状态在菜单副标题实时跟随，日志页包含级别切换与实时输出，从其它标签页切回设置时停留在离开前的页面
- **iOS 原生后台下载**（`ios_background_download.py`）：经 rubicon-objc 创建 Background NSURLSession，音乐下载在切后台、锁屏甚至应用被杀后由系统继续执行；应用重启时重建同名会话，遗留任务自动落库；传输中断用 resumeData 自动续传一次；非 2xx 的 HTTP 响应（如 404 错误页）拦截为失败；SMB 来源与非 iOS 平台自动回退 requests 路径
- macOS 冒烟脚本 `scripts/test_ios_background_download_macos.py`：在桌面端真实创建后台会话，验证正常下载、404 拦截、进程强杀后恢复三个场景

### Fixed
- 播放视图中间区域空白：Flet 0.86 中 `SafeArea` 无 `bottom` 参数，无效属性导致渲染补丁失败
- 播放/暂停按钮红错：`FilledButton` icon-only 需显式 `content=""`
- **iOS 原生后台下载被 ATS 拦截（NSURLErrorDomain -1022）**：`[tool.flet.ios.info]` 里的 ATS 例外此前以 TOML 字符串写入 Info.plist，iOS 解析不到合法字典即按默认策略拦截明文 HTTP（家庭服务器 `http://` 地址全部下载失败）；改为 TOML 嵌套表生成真正的 plist 字典。另加运行时保险：检测到 -1022 自动禁用原生路径并回退 requests，plist 配置失效时不再整批失败

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
