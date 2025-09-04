#!/bin/bash

# 依赖检查脚本 - 用于调试 CI 构建问题
# 这个脚本会检查当前系统上的 GObject Introspection 依赖

echo "======================================="
echo "  NextCloud Music Player 依赖检查"
echo "======================================="

# 系统信息
echo ""
echo "=== 系统信息 ==="
if command -v lsb_release >/dev/null 2>&1; then
    lsb_release -a
elif [ -f /etc/os-release ]; then
    cat /etc/os-release
else
    uname -a
fi

# 检查包管理器
echo ""
echo "=== 包管理器 ==="
if command -v apt-get >/dev/null 2>&1; then
    echo "使用 APT (Debian/Ubuntu)"
    PKG_MGR="apt"
elif command -v yum >/dev/null 2>&1; then
    echo "使用 YUM (CentOS/RHEL)"
    PKG_MGR="yum"
elif command -v dnf >/dev/null 2>&1; then
    echo "使用 DNF (Fedora)"
    PKG_MGR="dnf"
else
    echo "未找到支持的包管理器"
    PKG_MGR=""
fi

# 检查 pkg-config
echo ""
echo "=== pkg-config 检查 ==="
if command -v pkg-config >/dev/null 2>&1; then
    echo "✓ pkg-config 已安装"
    echo "版本: $(pkg-config --version)"
    echo "搜索路径: $(pkg-config --variable pc_path pkg-config 2>/dev/null || echo "无法获取")"
else
    echo "✗ pkg-config 未安装"
fi

# 检查 GObject Introspection 相关包
echo ""
echo "=== GObject Introspection 检查 ==="

if [ "$PKG_MGR" = "apt" ]; then
    echo "检查官方推荐的包:"
    for pkg in "libgirepository1.0-dev" "libcairo2-dev" "gir1.2-gtk-3.0" "libcanberra-gtk3-module"; do
        if apt-cache show "$pkg" >/dev/null 2>&1; then
            echo "✓ $pkg 可用"
        else
            echo "✗ $pkg 不可用"
        fi
    done
    
    echo ""
    echo "检查已安装的 GI 相关包:"
    dpkg -l | grep -E "(girepository|gobject|gir1.2)" | grep -E "(1\.0|2\.0)" || echo "未找到已安装的 GI 包"
fi

# 检查 pkg-config 文件
echo ""
echo "=== pkg-config 文件检查 ==="
for pkg in "girepository-1.0" "girepository-2.0" "glib-2.0" "cairo" "cairo-gobject"; do
    if pkg-config --exists "$pkg" 2>/dev/null; then
        version=$(pkg-config --modversion "$pkg" 2>/dev/null)
        echo "✓ $pkg (版本: $version)"
    else
        echo "✗ $pkg"
    fi
done

# 查找 girepository .pc 文件
echo ""
echo "=== 查找 girepository .pc 文件 ==="
find /usr -name "*girepository*.pc" 2>/dev/null | head -10 || echo "未找到 girepository .pc 文件"

# 检查 Python GI 绑定
echo ""
echo "=== Python GI 绑定检查 ==="
if command -v python3 >/dev/null 2>&1; then
    echo "测试 Python GI 导入:"
    python3 -c "
try:
    import gi
    print('✓ gi 模块可用')
    try:
        gi.require_version('GLib', '2.0')
        from gi.repository import GLib
        print('✓ GLib 绑定可用 (版本: {})'.format(GLib.MAJOR_VERSION))
    except Exception as e:
        print('✗ GLib 绑定失败:', e)
    try:
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        print('✓ Gtk 绑定可用')
    except Exception as e:
        print('✗ Gtk 绑定失败:', e)
except ImportError as e:
    print('✗ gi 模块不可用:', e)
" 2>/dev/null || echo "Python3 不可用或 GI 测试失败"
else
    echo "Python3 不可用"
fi

# 建议的解决方案
echo ""
echo "======================================="
echo "  建议的解决方案"
echo "======================================="

if [ "$PKG_MGR" = "apt" ]; then
    if pkg-config --exists girepository-1.0; then
        echo "✓ 当前配置正常，girepository-1.0 可用"
    elif pkg-config --exists girepository-2.0; then
        echo "✓ 当前配置正常，girepository-2.0 可用"
    else
        echo "根据 Ubuntu 版本使用不同的 girepository 包:"
        echo ""
        echo "Ubuntu 24.04+:"
        echo "  sudo apt install libgirepository-2.0-dev libcairo2-dev gir1.2-gtk-3.0"
        echo ""
        echo "Ubuntu 22.04 及更早版本:"
        echo "  sudo apt install libgirepository1.0-dev libcairo2-dev gir1.2-gtk-3.0"
        echo ""
        echo "完整的官方推荐安装命令:"
        echo "  sudo apt install git build-essential pkg-config python3-dev python3-venv libcairo2-dev gir1.2-gtk-3.0 libcanberra-gtk3-module"
        echo "  # 然后根据版本添加对应的 girepository 包"
        echo ""
        echo "参考: https://github.com/beeware/toga/issues/3143"
    fi
fi

echo ""
echo "检查完成！"
