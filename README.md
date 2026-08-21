
# NextCloud Music Player

免责: 大模型生成的项目,开发学习使用,不保证质量

<div align="center">

![License](https://img.shields.io/badge/license-BSD%203--Clause-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows%20%7C%20iOS%20%7C%20Android-lightgrey.svg)
![Framework](https://img.shields.io/badge/framework-Flet%200.86-blue.svg)
![Status](https://img.shields.io/badge/status-Alpha-orange.svg)

**一个基于 Flet (Flutter) 的跨平台音乐播放器，支持 NextCloud 云端音乐同步**

[功能特性](#-功能特性) • [截图预览](#-截图预览) • [安装说明](#-安装说明) • [使用指南](#-使用指南) • [开发指南](#-开发指南) • [自动化构建](#-自动化构建与发布) • [许可证](#-许可证)

</div>

## 📖 项目简介

NextCloud Music Player 是一款现代化的跨平台音乐播放器，专为喜欢使用 NextCloud 云存储服务的用户设计。它能够无缝连接到您的 NextCloud 服务器，同步音乐文件到本地缓存，并提供流畅的音乐播放体验。

项目使用 [Flet](https://flet.dev/) 框架（基于 Flutter 引擎），实现了原生级别的 UI 渲染和流畅的跨平台体验。

### 🎯 设计理念

- **云端同步**：与 NextCloud 无缝集成，自动同步音乐库
- **跨平台**：基于 Flet (Flutter) 框架，支持 macOS、Linux、Windows、iOS 和 Android
- **智能缓存**：本地缓存管理，支持离线播放
- **用户友好**：现代化的 Material Design 界面，简单易用

## ✨ 功能特性

### 🎵 音乐播放功能
- **多格式支持**：支持 MP3、FLAC、AAC 等常见音频格式
- **智能播放列表**：支持创建、管理和保存播放列表
- **播放模式**：顺序播放、随机播放、单曲循环、列表循环
- **播放控制**：播放/暂停、上一曲/下一曲、进度控制、音量调节
- **歌曲信息**：显示歌曲标题、艺术家、专辑等元数据信息

### ☁️ NextCloud 集成
- **服务器连接**：支持自定义 NextCloud 服务器地址
- **安全认证**：支持用户名/密码和应用专用密码认证
- **增量同步**：只下载新文件，避免重复传输
- **文件夹选择**：可选择特定文件夹进行同步
- **缓存管理**：智能本地缓存，支持缓存大小限制

### 📱 用户界面
- **底部导航**：连接设置、文件列表、播放控制三个主要视图
- **Tab 切换**：播放列表与歌词即时切换
- **进度显示**：实时显示播放进度和时间
- **响应式设计**：适配不同屏幕尺寸，支持 iOS SafeArea
- **歌词同步**：支持 LRC 格式歌词，自动高亮当前行并滚动

### 🔧 高级功能
- **离线播放**：缓存的音乐可离线播放
- **播放历史**：记录播放次数和最后播放时间
- **收藏功能**：支持标记喜爱的歌曲
- **日志系统**：完善的日志记录，便于问题诊断

## 📸 截图预览

<div align="center">

### 播放视图
![播放视图](docs/screenshots/playback_view.png)

### 连接设置视图
![连接设置视图](docs/screenshots/connection_view.png)

### 文件列表视图
![文件列表视图](docs/screenshots/files_view.png)

### 歌词视图
![歌词视图](docs/screenshots/lyrics_view.png)

</div>

## 🚀 安装说明

### 📦 从源码运行（推荐）

1. **克隆仓库**
   ```bash
   git clone https://github.com/zgfh/nextcloud-music-player.git
   cd nextcloud-music-player
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # 或
   .venv\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -e .
   pip install flet  # 安装 Flet CLI
   ```

4. **运行应用**
   ```bash
   python -m nextcloud_music_player
   ```

### 桌面平台

直接运行即可：
```bash
python -m nextcloud_music_player
```

### iOS 平台

```bash
# 需要 macOS + Xcode
# 构建 iOS 应用
flet build ipa

# 安装到设备
xcrun devicectl list devices  # 找到设备 ID
xcrun devicectl device install app --device <DEVICE_ID> build/ios/NextCloudMusicPlayer.ipa
```

或使用部署脚本：
```bash
bash scripts/deploy_iso.sh
```

### Android 平台

```bash
flet build apk
```

### 系统要求

- **Python**: 3.8 或更高版本
- **Flet**: 0.86.5+
- **操作系统**: macOS 10.14+、Ubuntu 18.04+、Windows 10+
- **iOS 构建**: macOS + Xcode 14+
- **NextCloud**: 兼容 NextCloud 20+ 版本

## 📱 使用指南

### 首次设置

1. **启动应用**：运行应用后，点击底部导航栏的"连接"标签
2. **配置服务器**：
   - 输入您的 NextCloud 服务器地址（如：`https://cloud.example.com`）
   - 输入用户名和密码（推荐使用应用专用密码）
3. **测试连接**：点击"测试连接"按钮验证设置
4. **选择文件夹**：点击"选择文件夹"按钮选择音乐文件夹路径（如：`/Music`）

### 音乐同步

1. **点击同步**：在"文件"标签页点击"同步音乐文件"
2. **查看文件**：同步完成后，音乐文件将显示在列表中
3. **下载状态**：绿色图标表示已下载，红色表示仅在云端

### 音乐播放

1. **添加到播放列表**：
   - 在文件列表中选择音乐文件，点击"添加到播放列表"
   - 或直接点击文件进行播放
2. **播放控制**：
   - 使用 ▶ ⏸ 按钮控制播放/暂停
   - 使用 ⏮ ⏭ 按钮切换歌曲
   - 拖动进度条调整播放位置
3. **播放模式**：点击播放模式按钮切换：
   - 顺序播放
   - 单曲循环
   - 全部循环
   - 随机播放
4. **歌词**：切换到"歌词"标签查看当前歌曲歌词，支持自动滚动和高亮

## 🛠 开发指南

### 项目结构

```
nextcloud-music-player/
├── src/nextcloud_music_player/
│   ├── __main__.py              # 入口 (ft.run)
│   ├── app.py                   # Flet 主入口
│   ├── nextcloud_client.py      # NextCloud API 客户端
│   ├── music_library.py         # 音乐库管理
│   ├── config_manager.py        # 配置管理
│   ├── platform_audio.py        # 平台音频抽象
│   ├── services/                # 业务逻辑服务（与框架无关）
│   │   ├── music_service.py     # 音乐服务
│   │   ├── playback_service.py  # 播放服务
│   │   ├── playback_controller.py # 播放控制器
│   │   ├── playlist_manager.py  # 播放列表管理
│   │   └── lyrics_service.py    # 歌词服务
│   ├── views/                   # Flet UI 视图
│   │   ├── view_manager.py      # 视图管理器 (NavigationBar)
│   │   ├── connection_view.py   # 连接设置视图
│   │   ├── file_list_view.py    # 文件列表视图
│   │   ├── playback_view.py     # 播放控制视图
│   │   ├── folder_selector.py   # 文件夹选择器
│   │   └── components/          # 可复用组件
│   │       ├── playback_control_component.py
│   │       ├── playlist_component.py
│   │       └── lyrics_component.py
│   └── utils/                   # 工具类
│       ├── theme.py             # 主题配色
│       └── platform_ui.py       # 平台 UI 适配
├── docs/screenshots/            # 应用截图
├── scripts/                     # 部署脚本
│   └── deploy_iso.sh            # iOS 部署脚本
└── pyproject.toml               # 项目配置
```

### 技术栈

- **UI 框架**: [Flet](https://flet.dev/) 0.86.5 - 基于 Flutter 的跨平台 UI 框架
- **音频播放**: [Pygame](https://www.pygame.org/) - 跨平台音频处理（桌面）
- **网络请求**: [httpx](https://www.python-httpx.org/) - 现代 HTTP 客户端
- **配置管理**: JSON 格式配置文件
- **日志系统**: Python 标准 logging 模块

### 架构设计

应用采用分层 MVC 架构：

- **Model**: `music_library.py`、`config_manager.py` - 数据模型和配置
- **View**: `views/` 目录下的 Flet 视图组件 - 用户界面
- **Controller**: `services/` 目录下的服务类 - 业务逻辑（完全与 UI 框架解耦）

服务层设计为框架无关，可复用于任何 UI 框架。

### 开发环境设置

1. **安装开发依赖**
   ```bash
   pip install -e ".[dev]"
   ```

2. **运行测试**
   ```bash
   python -m pytest tests/ -v
   ```

3. **代码格式化**
   ```bash
   black src/ tests/
   flake8 src/ tests/
   ```

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 生成覆盖率报告
python -m pytest tests/ --cov=src/nextcloud_music_player --cov-report=html
```

## 📦 构建与发布

### 桌面平台

```bash
# 直接运行
python -m nextcloud_music_player

# 或使用 Flet 构建
flet build macos  # macOS
flet build linux  # Linux
flet build windows  # Windows
```

### iOS

```bash
flet build ipa
bash scripts/deploy_iso.sh  # 自动构建并安装到连接的设备
```

### Android

```bash
flet build apk
```

## 📄 许可证

本项目采用 BSD 3-Clause 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎贡献代码！请按照以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 🙏 致谢

- [Flet](https://flet.dev/) - 基于 Flutter 的跨平台 Python UI 框架
- [NextCloud](https://nextcloud.com/) - 开源云存储解决方案
- [Pygame](https://www.pygame.org/) - 跨平台游戏和多媒体库

---

<div align="center">

**如果这个项目对您有帮助，请给它一个 ⭐ Star！**

Made with ❤️ by the NextCloud Music Player Team

</div>
