# GObject Introspection 依赖问题解决方案

## 问题描述

在 GitHub Actions 的 Ubuntu 环境中构建项目时，经常遇到以下两种相互矛盾的错误：

1. **删除 `libgobject-2.0-dev` 时**：
   ```
   Dependency 'girepository-2.0' is required but not found.
   ```

2. **保留 `libgobject-2.0-dev` 时**：
   ```
   libgobject-2.0-dev 找不到
   ```

## 问题原因

这个问题源于不同 Ubuntu 版本对 GObject Introspection 包的命名和依赖关系不同：

- **Ubuntu 22.04 及更新版本**：使用 `libgirepository1.0-dev`
- **Ubuntu 20.04 及更早版本**：使用 `libgirepository-2.0-dev`
- **包名变化**：某些版本中 `libgobject-2.0-dev` 不存在或已重命名

## 解决方案

### 1. 官方推荐依赖包

根据 Briefcase 和 Toga 官方文档，最可靠的解决方案是使用官方推荐的依赖包：

```bash
# 官方推荐的完整安装命令
sudo apt install git build-essential pkg-config python3-dev python3-venv libgirepository1.0-dev libcairo2-dev gir1.2-gtk-3.0 libcanberra-gtk3-module

# 补充其他必要依赖
sudo apt-get install -y libglib2.0-dev gobject-introspection libpango1.0-dev libgtk-3-dev
```

### 2. CI 配置更新

我们在 CI 配置中采用了官方推荐的包组合：

```yaml
- name: Install system dependencies
  run: |
    sudo apt-get update
    
    # 使用官方推荐的依赖包安装
    sudo apt-get install -y \
      git \
      build-essential \
      pkg-config \
      python3-dev \
      python3-venv \
      libgirepository1.0-dev \
      libcairo2-dev \
      gir1.2-gtk-3.0 \
      libcanberra-gtk3-module
    
    # 补充其他必要的依赖
    sudo apt-get install -y \
      libglib2.0-dev \
      gobject-introspection \
      libpango1.0-dev \
      libgtk-3-dev
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

# 使用官方推荐命令安装依赖
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
- ✅ Ubuntu 20.04 (GitHub Actions ubuntu-20.04)
- ✅ Ubuntu 22.04 (GitHub Actions ubuntu-22.04) 
- ✅ Ubuntu 24.04 (GitHub Actions ubuntu-latest)
- ✅ 其他基于 Debian 的发行版

## 验证

修改后的 CI 配置会在构建日志中显示：
- 系统版本信息
- 可用包列表
- 安装的包版本
- 依赖验证结果

这样可以更容易地诊断和解决依赖问题。
