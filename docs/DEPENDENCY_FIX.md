# GObject Introspection 依赖问题解决方案

## 问题描述

在 GitHub Actions 的 Ubuntu 环境中构建项目时，经常遇到以下错误：

```
../meson.build:31:9: ERROR: Dependency 'girepository-2.0' is required but not found.
```

## 问题根源

根据 [Toga Issue #3143](https://github.com/beeware/toga/issues/3143)，这个问题的根源是：

1. **PyGObject >= 3.51.0 需要 `girepository-2.0`**
2. **不同 Ubuntu 版本提供不同的包**：
   - **Ubuntu 24.04+**: 使用 `libgirepository-2.0-dev`
   - **Ubuntu 22.04 及更早版本**: 使用 `libgirepository1.0-dev`
3. **官方推荐的包名在不同版本间不兼容**

## 解决方案

### 1. 根据 Ubuntu 版本智能选择包

根据 [Toga Issue #3143](https://github.com/beeware/toga/issues/3143) 的解决方案，我们需要根据 Ubuntu 版本选择正确的包：

```bash
# 获取 Ubuntu 版本
UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || echo "unknown")

# 安装基础依赖
sudo apt-get install -y \
  git \
  build-essential \
  pkg-config \
  python3-dev \
  python3-venv \
  libcairo2-dev \
  gir1.2-gtk-3.0 \
  libcanberra-gtk3-module \
  libglib2.0-dev \
  gobject-introspection

# 根据版本选择正确的 girepository 包
if [[ "$UBUNTU_VERSION" =~ ^(24\.|25\.|26\.) ]]; then
  # Ubuntu 24.04+
  sudo apt-get install -y libgirepository-2.0-dev
else
  # Ubuntu 22.04 及更早版本
  sudo apt-get install -y libgirepository1.0-dev
fi
```

### 2. CI 配置更新

我们在 CI 配置中实施了智能版本检测：

```yaml
- name: Install system dependencies
  run: |
    sudo apt-get update
    
    # 获取 Ubuntu 版本
    UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || echo "unknown")
    echo "Ubuntu version: $UBUNTU_VERSION"
    
    # 安装基础依赖
    sudo apt-get install -y git build-essential pkg-config python3-dev python3-venv libcairo2-dev gir1.2-gtk-3.0 libcanberra-gtk3-module libglib2.0-dev gobject-introspection
    
    # 根据 Ubuntu 版本选择正确的 girepository 包
    if [[ "$UBUNTU_VERSION" =~ ^(24\.|25\.|26\.) ]]; then
      echo "Ubuntu 24.04+ detected - using libgirepository-2.0-dev"
      sudo apt-get install -y libgirepository-2.0-dev
    else
      echo "Ubuntu 22.04 or earlier detected - using libgirepository1.0-dev"
      sudo apt-get install -y libgirepository1.0-dev
    fi
```

### 3. 依赖验证

安装后进行验证以确保依赖正确：

```bash
# 验证关键依赖
pkg-config --exists glib-2.0 && echo "✓ glib-2.0 found" || echo "✗ glib-2.0 missing"
pkg-config --exists cairo && echo "✓ cairo found" || echo "✗ cairo missing"
if pkg-config --exists girepository-1.0; then
  echo "✓ girepository-1.0 found"
elif pkg-config --exists girepository-2.0; then
  echo "✓ girepository-2.0 found"
else
  echo "✗ girepository not found"
fi
```

### 3. 依赖检查脚本

创建了 `scripts/check_dependencies.sh` 脚本来系统性地检查依赖状态：

- 检测系统版本
- 列出可用的 GI 包
- 验证 pkg-config 文件
- 测试 Python GI 绑定
- 提供针对性的解决建议

## 修改的文件

1. **`.github/workflows/build.yml`**：
   - 所有构建任务 (Linux, Android) 的依赖安装逻辑
   - 添加智能包检测和验证步骤

2. **`.github/workflows/quality.yml`**：
   - Lint 和 Security 任务的依赖安装逻辑
   - 统一使用相同的智能检测策略

3. **`scripts/check_dependencies.sh`**：
   - 新增的依赖检查脚本
   - 可在本地和 CI 环境中使用

## 使用方法

### 本地调试

```bash
# 运行依赖检查脚本
./scripts/check_dependencies.sh

# Ubuntu 24.04+ 安装命令
sudo apt install git build-essential pkg-config python3-dev python3-venv libgirepository-2.0-dev libcairo2-dev gir1.2-gtk-3.0 libcanberra-gtk3-module

# Ubuntu 22.04 及更早版本安装命令
sudo apt install git build-essential pkg-config python3-dev python3-venv libgirepository1.0-dev libcairo2-dev gir1.2-gtk-3.0 libcanberra-gtk3-module

# 补充安装其他依赖
sudo apt-get install -y libglib2.0-dev gobject-introspection libpango1.0-dev libgtk-3-dev
```

### CI 环境

现在的 CI 配置会自动：
1. 检测 Ubuntu 版本
2. 选择合适的包
3. 验证安装结果
4. 提供诊断信息

## 兼容性

这个解决方案支持：
- ✅ Ubuntu 24.04+ (GitHub Actions ubuntu-latest) - 使用 `libgirepository-2.0-dev`
- ✅ Ubuntu 22.04 (GitHub Actions ubuntu-22.04) - 使用 `libgirepository1.0-dev`
- ✅ Ubuntu 20.04 及更早版本 - 使用 `libgirepository1.0-dev`
- ✅ 其他基于 Debian 的发行版

## 参考链接

- [Toga Issue #3143: PyGObject>=3.51.0 depends on libgirepository 2.0](https://github.com/beeware/toga/issues/3143)
- [PyGObject Dependencies Documentation](https://pygobject.readthedocs.io/en/latest/getting_started.html#ubuntu-getting-started)

## 验证

修改后的 CI 配置会在构建日志中显示：
- 系统版本信息
- 可用包列表
- 安装的包版本
- 依赖验证结果

这样可以更容易地诊断和解决依赖问题。
