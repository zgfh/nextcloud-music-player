
# NextCloud Music Player 🎵

免责: 大模型生成的项目,开发学习使用,不保证质量

<div align="center">

![License](https://img.shields.io/badge/license-BSD%203--Clause-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows%20%7C%20iOS%20%7C%20Android-lightgrey.svg)
![Status](https://img.shields.io/badge/status-Alpha-orange.svg)
![Build](https://github.com/zgfh/nextcloud-music-player/actions/workflows/build.yml/badge.svg)
![Release](https://github.com/zgfh/nextcloud-music-player/actions/workflows/release.yml/badge.svg)

**一个基于 BeeWare 的跨平台音乐播放器，支持 NextCloud 云端音乐同步**

[功能特性](#-功能特性) • [安装说明](#-安装说明) • [使用指南](#-使用指南) • [开发指南](#-开发指南) • [自动化构建](#-自动化构建与发布) • [贡献](#-贡献) • [许可证](#-许可证)

</div>

## 📖 项目简介

NextCloud Music Player 是一款现代化的跨平台音乐播放器，专为喜欢使用 NextCloud 云存储服务的用户设计。它能够无缝连接到您的 NextCloud 服务器，同步音乐文件到本地缓存，并提供流畅的音乐播放体验。

### 🎯 设计理念

- **云端同步**：与 NextCloud 无缝集成，自动同步音乐库
- **跨平台**：基于 BeeWare Toga 框架，支持 macOS、Linux、Windows、iOS 和 Android
- **智能缓存**：本地缓存管理，支持离线播放
- **用户友好**：直观的界面设计，简单易用

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
- **标签式界面**：连接设置、文件列表、播放控制分离
- **进度显示**：实时显示播放进度和时间
- **响应式设计**：适配不同屏幕尺寸
- **表情符号按钮**：直观的播放控制按钮

### 🔧 高级功能
- **离线播放**：缓存的音乐可离线播放
- **播放历史**：记录播放次数和最后播放时间
- **收藏功能**：支持标记喜爱的歌曲
- **日志系统**：完善的日志记录，便于问题诊断

## 🚀 安装说明

### 📦 预构建版本（推荐）

访问 [Releases 页面](https://github.com/zgfh/nextcloud-music-player/releases) 下载适合您操作系统的预构建安装包：

#### 桌面平台
- **Windows**: 下载 `.msi` 文件，双击安装
- **macOS**: 下载 `.dmg` 文件，拖拽到应用程序文件夹
- **Linux**: 下载 `.deb` 文件，使用包管理器安装

#### 移动平台
- **iOS**: 下载 iOS 项目文件，需要 Xcode 编译和签名
- **Android**: 下载 `.apk` 文件（开发版本，未签名）

📱 **移动平台详细安装和构建指南**: [移动平台构建指南](docs/MOBILE_BUILD_GUIDE.md)

```bash
# Ubuntu/Debian 系统安装示例
sudo dpkg -i nextcloud-music-player_*.deb
sudo apt-get install -f  # 如果有依赖问题
```

#### 移动平台安装说明

**iOS 安装:**
1. 下载 iOS 构建文件并解压
2. 使用 Xcode 打开 `.xcodeproj` 文件
3. 配置开发者证书和描述文件
4. 连接 iOS 设备并编译安装

**Android 安装:**
1. 在 Android 设备上启用"开发者选项"和"USB调试"
2. 在"安全"设置中允许"未知来源"安装
3. 下载并安装 `.apk` 文件
4. 注意：开发版本未经过签名，仅用于测试

### 系统要求

- **Python**: 3.8 或更高版本
- **操作系统**: macOS 10.14+、Ubuntu 18.04+、Windows 10+
- **NextCloud**: 兼容 NextCloud 20+ 版本

### 从源码安装

1. **克隆仓库**
   ```bash
   git clone https://github.com/yourusername/nextcloud-music-player.git
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
   ```

4. **运行应用**
   ```bash
   python -m briefcase dev
   ```

### 构建发布版本

```bash
# 构建本平台应用
python -m briefcase build

# 打包为可分发格式
python -m briefcase package
```

### 移动平台构建

#### iOS 平台
```bash
# 系统要求：macOS + Xcode
# 初始化 iOS 项目
python -m briefcase create iOS
python -m briefcase build iOS

# 在 Xcode 中打开项目进行进一步配置
python -m briefcase open iOS

# 后续更新
python -m briefcase update iOS
```

**iOS 构建要求:**
- macOS 系统
- Xcode 14.0 或更高版本
- Apple Developer 账户（用于设备安装）
- iOS 12.0 或更高版本的目标设备

#### Android 平台
```bash
# 系统要求：安装 Android SDK 和 JDK
# 初始化 Android 项目
python -m briefcase create android
python -m briefcase build android

# 打包 APK
python -m briefcase package android

# 后续更新
python -m briefcase update android
```

**Android 构建要求:**
- JDK 11 或更高版本
- Android SDK (API Level 21+)
- Android Build Tools
- 至少 4GB 可用内存

#### 移动平台注意事项
- 移动平台构建需要额外的系统配置
- iOS 需要 Apple Developer 证书进行签名
- Android APK 默认为调试版本，生产环境需要签名
- 某些音频功能在移动平台上可能有限制
python -m briefcase create android
python -m briefcase build android
```

## 📱 使用指南

### 首次设置

1. **启动应用**：运行应用后，首先进入"连接设置"标签页
2. **配置服务器**：
   - 输入您的 NextCloud 服务器地址（如：`https://cloud.example.com`）
   - 输入用户名和密码（推荐使用应用专用密码）
3. **测试连接**：点击"测试连接"按钮验证设置
4. **选择文件夹**：在"同步文件夹"中输入音乐文件夹路径（如：`/Music`）

### 音乐同步

1. **点击同步**：在"文件列表"标签页点击"同步音乐文件"
2. **查看文件**：同步完成后，音乐文件将显示在列表中
3. **下载状态**：绿色图标表示已下载，红色表示仅在云端

### 音乐播放

1. **添加到播放列表**：
   - 选择音乐文件，点击"添加到播放列表"
   - 或者双击文件直接播放
2. **播放控制**：
   - 使用 ▶️ ⏸️ 按钮控制播放/暂停
   - 使用 ⏮️ ⏭️ 按钮切换歌曲
   - 拖动进度条调整播放位置
3. **播放模式**：点击播放模式按钮切换：
   - 🔁 列表循环
   - 🔂 单曲循环
   - 🔀 随机播放

## 🛠 开发指南

### 项目结构

```
nextcloud-music-player/
├── src/nextcloud_music_player/
│   ├── app.py                  # 主应用类
│   ├── nextcloud_client.py     # NextCloud API 客户端
│   ├── music_library.py        # 音乐库管理
│   ├── config_manager.py       # 配置管理
│   ├── services/               # 业务逻辑服务
│   │   ├── music_service.py    # 音乐服务
│   │   └── playback_service.py # 播放服务
│   └── views/                  # UI 视图组件
│       ├── connection_view.py  # 连接设置视图
│       ├── file_list_view.py   # 文件列表视图
│       ├── playback_view.py    # 播放控制视图
│       └── view_manager.py     # 视图管理器
├── tests/                      # 单元测试
├── docs/                       # 文档
└── pyproject.toml             # 项目配置
```

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

### 技术栈

- **UI 框架**: [BeeWare Toga](https://toga.readthedocs.io/) - 跨平台原生 UI
- **音频播放**: [Pygame](https://www.pygame.org/) - 跨平台音频处理
- **网络请求**: [httpx](https://www.python-httpx.org/) - 现代 HTTP 客户端
- **配置管理**: JSON 格式配置文件
- **日志系统**: Python 标准 logging 模块

### 架构设计

应用采用 MVC 架构模式：

- **Model**: `music_library.py`、`config_manager.py` - 数据模型和配置
- **View**: `views/` 目录下的各个视图组件 - 用户界面
- **Controller**: `services/` 目录下的服务类 - 业务逻辑

## 🧪 测试

### 运行单元测试
```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_nextcloud_client.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=src/nextcloud_music_player --cov-report=html
```

### 手动测试

项目包含以下 VS Code 任务，可通过命令面板执行：

- **运行 NextCloud 音乐播放器**: 启动开发版本
- **运行单元测试**: 执行完整测试套件
- **构建应用**: 构建发布版本
- **NextCloud 连接测试**: 测试服务器连接

## � 自动化构建与发布

本项目配置了完整的 CI/CD 流水线，支持自动构建、测试和发布。

### 🔄 持续集成

每次推送代码或创建 Pull Request 时，会自动执行：
- 单元测试
- 代码质量检查（flake8, black, isort）
- 安全漏洞扫描（bandit, safety）
- 多平台构建测试

### 📦 自动发布

#### 开发版本
每次推送到 `main` 分支时，自动创建开发版本：
- 构建所有平台的应用包（Windows .msi、macOS .dmg、Linux .deb）
- 创建预发布版本，标签格式：`dev-{commit-sha}`
- 上传构建产物到 GitHub Releases

#### 正式版本
创建新的版本标签时，自动发布正式版本：

```bash
# 使用发布脚本（推荐）
./scripts/release.sh 1.0.0

# 或手动创建标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

发布流程会：
- 自动生成更改日志
- 创建详细的 Release 说明
- 上传所有平台的安装包
- 发送发布通知

### 📊 构建状态

- **构建状态**: ![Build](https://github.com/zgfh/nextcloud-music-player/actions/workflows/build.yml/badge.svg)
- **发布状态**: ![Release](https://github.com/zgfh/nextcloud-music-player/actions/workflows/release.yml/badge.svg)
- **代码质量**: ![Quality](https://github.com/zgfh/nextcloud-music-player/actions/workflows/quality.yml/badge.svg)

查看详细构建信息：
- [Actions 页面](https://github.com/zgfh/nextcloud-music-player/actions)
- [Releases 页面](https://github.com/zgfh/nextcloud-music-player/releases)

更多信息请参考 [工作流说明文档](.github/workflows/README.md)。

## �📄 许可证

本项目采用 BSD 3-Clause 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎贡献代码！请按照以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 贡献指南

- 请确保代码通过所有测试
- 遵循现有的代码风格
- 为新功能添加相应的测试
- 更新相关文档

## 📞 支持与反馈

- **问题报告**: [GitHub Issues](https://github.com/yourusername/nextcloud-music-player/issues)
- **功能请求**: [GitHub Discussions](https://github.com/yourusername/nextcloud-music-player/discussions)
- **文档**: [项目 Wiki](https://github.com/yourusername/nextcloud-music-player/wiki)

## 🙏 致谢

- [BeeWare Project](https://beeware.org/) - 提供优秀的跨平台 Python 框架
- [NextCloud](https://nextcloud.com/) - 开源云存储解决方案
- [Pygame](https://www.pygame.org/) - 跨平台游戏和多媒体库

---

<div align="center">

**如果这个项目对您有帮助，请给它一个 ⭐ Star！**

Made with ❤️ by the NextCloud Music Player Team

</div>