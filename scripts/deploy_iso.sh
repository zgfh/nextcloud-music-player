#!/bin/bash
set -e

# 确保在项目根目录执行
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_message() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ====== 自动检测设备 ======
log_message "${YELLOW}📱 查找连接的 iOS 设备...${NC}"

DEVICE_LINE=$(xcrun devicectl list devices 2>&1 | grep -i "iphone" | grep -v "Simulator" | head -1)

if [ -z "$DEVICE_LINE" ]; then
    log_message "${RED}❌ 未找到连接的 iOS 设备，请连接后重试${NC}"
    exit 1
fi

DEVICE_ID=$(echo "$DEVICE_LINE" | grep -oE '[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}' | head -1)
DEVICE_NAME=$(echo "$DEVICE_LINE" | awk '{print $1}')

log_message "${GREEN}✅ 找到设备: $DEVICE_NAME ($DEVICE_ID)${NC}"

# ====== 项目配置 ======
PROJECT_NAME="NextCloud Music Player"
SCHEME_NAME="NextCloud Music Player"
PROJECT_DIR="build/nextcloud-music-player/ios/xcode"
PROJECT_PATH="$PROJECT_DIR/$PROJECT_NAME.xcodeproj"

if [ ! -d "$PROJECT_PATH" ]; then
    log_message "${RED}❌ Xcode 项目未找到: $PROJECT_PATH${NC}"
    exit 1
fi

# ====== 获取构建输出目录 ======
BUILD_DIR=$(xcodebuild -project "$PROJECT_PATH" \
    -scheme "$SCHEME_NAME" \
    -configuration Debug \
    -destination "id=$DEVICE_ID" \
    -showBuildSettings 2>/dev/null | grep " CONFIGURATION_BUILD_DIR" | head -1 | sed 's/.*= //')

if [ -z "$BUILD_DIR" ]; then
    log_message "${RED}❌ 无法获取构建目录${NC}"
    exit 1
fi

APP_PATH="$BUILD_DIR/$PROJECT_NAME.app"

# ====== 构建 ======
log_message "${YELLOW}🔨 构建 iOS 项目 (Debug)...${NC}"
xcodebuild -project "$PROJECT_PATH" \
           -scheme "$SCHEME_NAME" \
           -configuration Debug \
           -destination "id=$DEVICE_ID" \
           -allowProvisioningUpdates \
           build 2>&1 | grep -E "(BUILD SUCCE|BUILD FAIL|error:)" || true

if [ ! -d "$APP_PATH" ]; then
    log_message "${RED}❌ 构建失败，未找到: $APP_PATH${NC}"
    exit 1
fi

log_message "${GREEN}✅ 构建成功: $APP_PATH${NC}"

# ====== 安装 ======
log_message "${YELLOW}📲 安装到 $DEVICE_NAME...${NC}"
xcrun devicectl device install app --device "$DEVICE_ID" "$APP_PATH" -t 600 2>&1

log_message "${GREEN}🎉 完成！应用已安装到 $DEVICE_NAME${NC}"
