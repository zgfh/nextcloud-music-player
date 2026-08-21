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

# ====== 1. Flet 打包 Python + 生成 Flutter 工程 ======
# 注意: flet 0.86 的 `build ipa` 在没有 provisioning profile 时会走 --no-codesign，
# 无法产出可用 IPA，因此这里只用它完成打包/生成工程，签名在下一步用 flutter 完成。
log_message "${YELLOW}🔨 打包 Python 应用并生成 Flutter 工程...${NC}"

FLET_CMD="/Users/zzg/code/iso-demo/.venv/bin/flet"

if [ ! -f "$FLET_CMD" ]; then
    log_message "${RED}❌ 未找到 flet 命令: $FLET_CMD${NC}"
    log_message "${YELLOW}请先安装: pip install flet${NC}"
    exit 1
fi

$FLET_CMD build ipa --yes --no-rich-output 2>&1 | tail -10 || true

# ====== 2. 写入自动签名 exportOptions ======
log_message "${YELLOW}🔏 配置自动签名 (development / team 6CS69Y977H)...${NC}"

cat > build/flutter/ios/exportOptions.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>development</string>
    <key>teamID</key>
    <string>6CS69Y977H</string>
    <key>signingStyle</key>
    <string>automatic</string>
    <key>compileBitcode</key>
    <false/>
    <key>stripSwiftSymbols</key>
    <true/>
    <key>uploadSymbols</key>
    <false/>
</dict>
</plist>
PLIST

# ====== 3. flutter 构建签名 IPA ======
log_message "${YELLOW}📦 构建签名 IPA...${NC}"

export PATH="$HOME/flutter/3.44.8/bin:/usr/local/bin:$PATH"
(cd build/flutter && flutter build ipa --release --export-options-plist ios/exportOptions.plist 2>&1 | tail -15)

# ====== 4. 查找 IPA 并安装 ======
IPA_PATH=$(find build/flutter/build/ios -name "*.ipa" -type f 2>/dev/null | head -1)

if [ -z "$IPA_PATH" ]; then
    log_message "${RED}❌ 构建失败，未找到 IPA 文件${NC}"
    exit 1
fi

log_message "${GREEN}✅ 构建成功: $IPA_PATH${NC}"

log_message "${YELLOW}📲 安装到 $DEVICE_NAME...${NC}"
xcrun devicectl device install app --device "$DEVICE_ID" "$IPA_PATH" -t 600 2>&1

log_message "${GREEN}🎉 完成！应用已安装到 $DEVICE_NAME${NC}"
