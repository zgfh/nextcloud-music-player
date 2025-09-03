# iOS 构建和签名指南

## 🔐 iOS 签名问题详解

### 为什么 iOS 构建会有签名问题？

iOS 应用必须经过数字签名才能在真实设备上运行，这是 Apple 的安全机制：

1. **开发者证书要求**：需要有效的 Apple Developer 证书
2. **设备授权**：设备必须注册到开发者账户中
3. **Provisioning Profile**：需要匹配应用、证书和设备的配置文件
4. **CI 环境限制**：GitHub Actions 无法访问私人的开发者证书

## 🏗️ 当前的构建策略

我们的 CI 配置采用了多层策略来处理签名问题：

### 策略 1: Ad-hoc 签名
```bash
python -m briefcase package iOS --adhoc-sign
```
- **适用场景**：开发和测试
- **限制**：只能在注册的设备上运行
- **成功率**：在 CI 中通常会失败（缺少证书）

### 策略 2: 构建无签名 .app
```bash
python -m briefcase build iOS
```
- **适用场景**：获取原始应用包
- **优势**：不需要签名证书
- **用途**：后续可以手动签名

### 策略 3: 手动创建未签名 IPA
```bash
mkdir -p Payload
cp -r "App.app" Payload/
zip -r "App-unsigned.ipa" Payload/
```
- **适用场景**：分发和后续签名
- **优势**：标准 IPA 格式
- **用途**：可以用第三方工具重新签名

## 📦 分发包内容

我们的 iOS 构建会创建 `ios-build.tar.gz`，包含：

```
ios-distribution/
├── README.md                           # 详细安装说明
├── ios/                               # 完整 Xcode 项目
│   └── xcode/
│       └── NextCloud Music Player.xcodeproj
├── NextCloud Music Player.app/       # 应用包（如果构建成功）
├── NextCloud-Music-Player.ipa        # 签名 IPA（如果签名成功）
└── NextCloud-Music-Player-unsigned.ipa # 未签名 IPA（如果创建成功）
```

## 🛠️ 用户安装选项

### 选项 1: 使用 Xcode 项目（推荐）

**适用场景**：开发者，有 Xcode 和开发者账户

**步骤**：
1. 下载并解压 `ios-build.tar.gz`
2. 打开 `ios/xcode/NextCloud Music Player.xcodeproj`
3. 在 Xcode 中：
   - 选择 Project → Signing & Capabilities
   - 设置你的 Development Team
   - 连接 iOS 设备
   - 点击 Run 按钮

**优势**：
- ✅ 最可靠的方法
- ✅ 自动处理签名和设备安装
- ✅ 支持调试

### 选项 2: 重新签名 IPA

**适用场景**：有开发者证书但不想用 Xcode

**步骤**：
```bash
# 使用 codesign 重新签名
codesign -f -s "iPhone Developer: Your Name" NextCloud-Music-Player-unsigned.ipa

# 或使用第三方工具如 ios-app-signer
```

### 选项 3: 企业签名或侧载

**适用场景**：越狱设备或企业证书

**工具**：
- AltStore
- Sideloadly
- 3uTools
- Cydia Impactor

## 🚀 CI/CD 改进建议

### 如果你有 Apple Developer 账户：

1. **添加签名证书到 GitHub Secrets**：
```yaml
- name: Import Code-Signing Certificates
  uses: Apple-Actions/import-codesign-certs@v1
  with:
    p12-file-base64: ${{ secrets.CERTIFICATES_P12 }}
    p12-password: ${{ secrets.CERTIFICATES_P12_PASSWORD }}

- name: Download Provisioning Profiles
  uses: Apple-Actions/download-provisioning-profiles@v1
  with:
    bundle-id: com.yourcompany.nextcloud-music-player
    issuer-id: ${{ secrets.APPSTORE_ISSUER_ID }}
    api-key-id: ${{ secrets.APPSTORE_KEY_ID }}
    api-private-key: ${{ secrets.APPSTORE_PRIVATE_KEY }}
```

2. **自动构建签名 IPA**：
```yaml
- name: Build signed iOS app
  run: |
    python -m briefcase package iOS
```

### 当前无证书的解决方案：

我们当前的配置会：
1. ✅ 构建 Xcode 项目（总是成功）
2. ✅ 尝试创建 .app 文件
3. ✅ 尝试创建未签名 IPA
4. ✅ 提供完整的安装说明
5. ✅ 让用户选择最适合的安装方法

## 📱 测试和验证

### 验证构建结果：
```bash
# 检查 .app 结构
ls -la "NextCloud Music Player.app"

# 检查 IPA 内容
unzip -l NextCloud-Music-Player-unsigned.ipa

# 验证代码签名状态
codesign -dv "NextCloud Music Player.app"
```

### 常见问题解决：

**问题：应用崩溃或无法启动**
- 检查设备是否已添加到开发者账户
- 确认 Bundle ID 正确
- 检查权限设置

**问题：无法安装到设备**
- 确认设备信任开发者证书
- 检查 iOS 版本兼容性
- 尝试使用 Xcode 直接安装

这种多层策略确保了用户总能获得可用的 iOS 构建产物，无论 CI 环境的签名状态如何。
