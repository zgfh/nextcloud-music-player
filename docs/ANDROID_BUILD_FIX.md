# Android 构建修复说明

## 问题描述

在 Android 构建过程中，出现了 pycairo 依赖编译失败的问题：

```
error: subprocess-exited-with-error
× Preparing metadata (pyproject.toml) did not run successfully.
│ exit code: 1
╰─> [465 lines of output]
      ERROR: Dependency "cairo" not found, tried pkgconfig and cmake
```

## 问题原因

1. **缺少系统级 Cairo 库**：pycairo 需要系统安装 Cairo 图形库及其开发文件
2. **缺少构建工具**：编译 pycairo 需要 pkg-config 和编译器工具链
3. **CI 环境配置不完整**：GitHub Actions 环境中没有预装所需的图形库

## 修复方案

### 1. 更新 GitHub Actions 工作流

#### `.github/workflows/mobile.yml`
在 Android 构建任务中添加了系统依赖安装步骤：

```yaml
- name: Install system dependencies for pycairo
  run: |
    sudo apt-get update
    sudo apt-get install -y \
      pkg-config \
      build-essential \
      libcairo2-dev \
      libpango1.0-dev \
      libglib2.0-dev \
      libgdk-pixbuf2.0-dev \
      libffi-dev \
      libgirepository1.0-dev \
      libcairo-gobject2 \
      libgirepository-1.0-1 \
      libgtk-3-0 \
      libpango-1.0-0
```

#### `.github/workflows/test-linux-fix.yml`
增强了 Linux 构建的系统依赖：

```yaml
libcairo2 \
libcairo-gobject2 \
cairo-5c \
libglib2.0-dev \
libgdk-pixbuf2.0-dev \
libffi-dev
```

### 2. 更新项目配置

#### `pyproject.toml`
为 Android 平台添加了专门的配置：

```toml
[tool.briefcase.app.nextcloud-music-player.android]
requires = [
    "toga-android~=0.4.0",
    "requests>=2.25.0",
    "httpx>=0.24.0",
]
gradle_dependencies = [
    "androidx.media:media:1.6.0",
    "androidx.lifecycle:lifecycle-service:2.6.1",
]
permission.INTERNET = "This app needs internet access to connect to your NextCloud server."
permission.WAKE_LOCK = "This app needs wake lock permission for background music playback."
permission.FOREGROUND_SERVICE = "This app needs foreground service permission for music playback."
```

### 3. 创建测试工具

#### `scripts/test_android_deps.sh`
创建了一个测试脚本来验证依赖安装：

```bash
#!/bin/bash
# 安装所有必需的系统依赖
sudo apt-get install -y pkg-config build-essential libcairo2-dev ...
# 测试 pycairo 安装
python3 -m pip install pycairo --verbose
# 验证导入
python3 -c "import cairo; print(f'pycairo version: {cairo.version}')"
```

#### `.github/workflows/test-android-fix.yml`
创建了专门的测试工作流来验证修复：

- 检查系统包可用性
- 安装系统依赖
- 测试 pycairo 编译和安装
- 验证 briefcase create android 命令

## 依赖包说明

| 包名 | 用途 |
|------|------|
| `pkg-config` | 查找和使用库文件的工具 |
| `build-essential` | 基本编译工具（gcc, make等） |
| `libcairo2-dev` | Cairo 图形库开发文件 |
| `libpango1.0-dev` | Pango 文本渲染库开发文件 |
| `libglib2.0-dev` | GLib 基础库开发文件 |
| `libgdk-pixbuf2.0-dev` | GdkPixbuf 图像库开发文件 |
| `libffi-dev` | Foreign Function Interface 库 |
| `libgirepository1.0-dev` | GObject Introspection 开发文件 |

## 测试验证

### 本地测试
```bash
# 使用测试脚本
./scripts/test_android_deps.sh

# 手动测试
python -m briefcase create android
```

### CI 测试
- 推送代码触发 `test-android-fix.yml` 工作流
- 手动触发 `mobile.yml` 工作流进行完整构建

## 注意事项

1. **平台差异**：这些修复主要针对 Ubuntu/Debian 系统的 CI 环境
2. **本地开发**：本地 macOS/Windows 开发不受影响
3. **构建时间**：安装系统依赖会增加 CI 构建时间（约 30-60 秒）
4. **缓存优化**：可以考虑使用 GitHub Actions 缓存来加速后续构建

## 相关链接

- [pycairo 文档](https://pycairo.readthedocs.io/)
- [BeeWare Briefcase 文档](https://briefcase.readthedocs.io/)
- [GitHub Actions setup-android](https://github.com/android-actions/setup-android)
