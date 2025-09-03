#!/bin/bash
# 测试Android构建修复脚本

echo "🔧 NextCloud Music Player - Android Build Fix Test"
echo "================================================="

# 检查是否在CI环境中
if [ "$CI" = "true" ]; then
    echo "✓ Running in CI environment"
else
    echo "⚠️  Running in local environment"
fi

# 更新包列表
echo "📦 Updating package lists..."
sudo apt-get update -qq

# 安装系统依赖
echo "🔨 Installing system dependencies..."
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

# 验证安装
echo "🔍 Verifying installations..."
echo "Cairo:"
pkg-config --exists cairo && echo "  ✓ cairo found" || echo "  ✗ cairo not found"
pkg-config --modversion cairo 2>/dev/null || echo "  ✗ cairo version not available"

echo "Pango:"
pkg-config --exists pango && echo "  ✓ pango found" || echo "  ✗ pango not found"

echo "GLib:"
pkg-config --exists glib-2.0 && echo "  ✓ glib-2.0 found" || echo "  ✗ glib-2.0 not found"

# 测试pycairo安装
echo "🐍 Testing pycairo installation..."
python3 -m pip install --upgrade pip setuptools wheel
if python3 -m pip install pycairo --verbose; then
    echo "  ✓ pycairo installed successfully"
    if python3 -c "import cairo; print(f'pycairo version: {cairo.version}')"; then
        echo "  ✓ pycairo import successful"
    else
        echo "  ✗ pycairo import failed"
        exit 1
    fi
else
    echo "  ✗ pycairo installation failed"
    exit 1
fi

# 安装其他依赖
echo "📚 Installing Python dependencies..."
python3 -m pip install briefcase toga>=0.4.0 requests>=2.25.0 httpx>=0.24.0

echo ""
echo "🎉 All dependencies installed successfully!"
echo "You can now run: python -m briefcase create android"
