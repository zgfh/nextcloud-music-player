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

# ====== 使用 Flet 构建 iOS IPA ======
log_message "${YELLOW}🔨 使用 Flet 构建 iOS IPA...${NC}"

# 使用 venv 中的 flet
FLET_CMD="/Users/zzg/code/nextcloud-music-player/.venv/bin/flet"

if [ ! -f "$FLET_CMD" ]; then
    log_message "${RED}❌ 未找到 flet 命令: $FLET_CMD${NC}"
    log_message "${YELLOW}请先安装: pip install flet${NC}"
    exit 1
fi

$FLET_CMD build ipa --no-rich-output 2>&1 | tail -20

# 查找构建产物
IPA_PATH=$(find build -name "*.ipa" -type f 2>/dev/null | head -1)

if [ -z "$IPA_PATH" ]; then
    log_message "${RED}❌ 构建失败，未找到 IPA 文件${NC}"
    exit 1
fi

log_message "${GREEN}✅ 构建成功: $IPA_PATH${NC}"

# ====== 安装 ======
log_message "${YELLOW}📲 安装到 $DEVICE_NAME...${NC}"
xcrun devicectl device install app --device "$DEVICE_ID" "$IPA_PATH" -t 600 2>&1

log_message "${GREEN}🎉 完成！应用已安装到 $DEVICE_NAME${NC}"
