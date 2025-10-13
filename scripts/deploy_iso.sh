#!/bin/bash
set -e

# 设置完整的环境变量
export PATH="/usr/local/opt/openjdk/bin:/usr/local/bin:/System/Cryptexes/App/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/local/bin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/bin:/var/run/com.apple.security.cryptexd/codex.system/bootstrap/usr/appleinternal/bin:/Library/Apple/usr/bin:/Applications/iTerm.app/Contents/Resources/utilities:$PATH"

env

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 检查参数
if [ $# -ne 1 ]; then
    log_message "错误: 需要提供设备 ID"
    log_message "用法: $0 <DEVICE_ID>"
    exit 1
fi

log_message " ${GREEN}🚀 开始 iOS 自动化构建和部署...${NC}"

# 设置变量
PROJECT_NAME="NextCloud Music Player"
SCHEME_NAME="NextCloud Music Player"
DEVICE_ID=${1}

# 1. 检查设备连接
log_message -e "${YELLOW}📱 检查设备连接...${NC}"
if xcrun xctrace list devices | grep -q "$DEVICE_ID"; then
    log_message " ${GREEN}✅ 设备已连接: $DEVICE_ID${NC}"
else
    log_message " ${RED}❌ 设备未连接，请检查设备连接${NC}"
    exit 1
fi

# 3. 获取项目路径
PROJECT_PATH="build/nextcloud-music-player/ios/xcode/$PROJECT_NAME.xcodeproj"

if [ ! -d "$PROJECT_PATH" ]; then
    log_message " ${RED}❌ Xcode 项目未找到: $PROJECT_PATH${NC}"
    exit 1
fi


# 4. 构建项目
log_message " ${YELLOW}🔨 构建 iOS 项目...${NC}"
xcodebuild -project "$PROJECT_PATH" \
           -scheme "$SCHEME_NAME" \
           -configuration Release \
           -destination "id=$DEVICE_ID" \
           -allowProvisioningUpdates \
           clean build

# 5. 查找构建后的 .app 文件
log_message " ${YELLOW}� 查找构建产物...${NC}"

# 可能的构建输出路径
POSSIBLE_PATHS=(
    "build/nextcloud-music-player/ios/xcode/build/Release-iphoneos/$PROJECT_NAME.app"
    "build/nextcloud-music-player/ios/xcode/build/Release-iphoneos/NextCloud Music Player.app"
    "$HOME/Library/Developer/Xcode/DerivedData/NextCloud_Music_Player-*/Build/Products/Release-iphoneos/$PROJECT_NAME.app"
    "$HOME/Library/Developer/Xcode/DerivedData/NextCloud_Music_Player-*/Build/Products/Release-iphoneos/NextCloud Music Player.app"
    "$HOME/Library/Developer/Xcode/DerivedData/*/Build/Intermediates.noindex/ArchiveIntermediates/NextCloud*/InstallationBuildProductsLocation/Applications/$PROJECT_NAME.app"
    "$HOME/Library/Developer/Xcode/DerivedData/*/Build/Intermediates.noindex/ArchiveIntermediates/NextCloud*/InstallationBuildProductsLocation/Applications/NextCloud Music Player.app"
)

APP_PATH=""
for path in "${POSSIBLE_PATHS[@]}"; do
    # 使用 find 来处理通配符
    found_paths=$(find $(dirname "$path") -name "$(basename "$path")" -type d 2>/dev/null || true)
    if [ -n "$found_paths" ]; then
        APP_PATH=$(echo "$found_paths" | head -n 1)
        log_message " ${GREEN}✅ 找到 .app 文件: $APP_PATH${NC}"
        break
    fi
done

if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
    log_message " ${RED}❌ 未找到构建的 .app 文件${NC}"
    log_message " ${YELLOW}尝试在以下位置查找:${NC}"
    for path in "${POSSIBLE_PATHS[@]}"; do
        echo "  - $path"
    done
    
    # 使用更广泛的搜索
    log_message " ${YELLOW}🔍 广泛搜索 .app 文件...${NC}"
    find . -name "*.app" -type d 2>/dev/null | head -10
    find "$HOME/Library/Developer/Xcode/DerivedData" -name "*NextCloud*.app" -type d 2>/dev/null | head -10
    exit 1
fi

# 6. 创建临时目录并复制 .app 文件
log_message " ${YELLOW}📁 创建临时目录...${NC}"
TEMP_DIR="build/tmp_$(date +%s)"
mkdir -p "$TEMP_DIR"
TEMP_APP_PATH="$TEMP_DIR/NextCloudMusicPlayer.app"

log_message " ${YELLOW}📋 复制 .app 到临时目录...${NC}"
cp -R "$APP_PATH" "$TEMP_APP_PATH"

if [ ! -d "$TEMP_APP_PATH" ]; then
    log_message " ${RED}❌ 复制失败${NC}"
    exit 1
fi

log_message " ${GREEN}✅ 复制成功: $TEMP_APP_PATH${NC}"

# 7. 安装到设备
log_message " ${YELLOW}📲 安装到设备...${NC}"
xcrun devicectl device install app --device "$DEVICE_ID" "$TEMP_APP_PATH" -t 600

if [ $? -eq 0 ]; then
    log_message " ${GREEN}🎉 安装成功！${NC}"
else
    log_message " ${RED}❌ 安装失败${NC}"
    exit 1
fi

# 9. 清理临时文件
log_message " ${YELLOW}🧹 清理临时文件...${NC}"
rm -rf "$TEMP_DIR"

log_message " ${GREEN}✅ 所有步骤完成！${NC}"