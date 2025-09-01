# 📱 移动平台构建指南

本文档详细介绍如何为 NextCloud Music Player 构建移动平台应用。

## 🍎 iOS 平台

### 环境要求

- **操作系统**: macOS 10.15 或更高版本
- **Xcode**: 14.0 或更高版本
- **Python**: 3.8 或更高版本
- **设备**: iOS 12.0 或更高版本

### 构建步骤

1. **安装依赖**
   ```bash
   # 安装系统依赖
   brew install libffi
   
   # 安装 Python 依赖
   pip install briefcase
   pip install -e .
   ```

2. **创建 iOS 项目**
   ```bash
   python -m briefcase create iOS
   ```

3. **构建应用**
   ```bash
   python -m briefcase build iOS
   ```

4. **在 Xcode 中打开**
   ```bash
   python -m briefcase open iOS
   ```

5. **配置签名和部署**
   - 在 Xcode 中配置开发者账户
   - 设置签名证书和描述文件
   - 选择目标设备
   - 点击运行按钮部署到设备

### 发布到 App Store

1. **配置发布签名**
   - 创建 App Store Connect 记录
   - 配置发布证书和描述文件

2. **打包上传**
   ```bash
   python -m briefcase package iOS
   ```

3. **上传到 App Store Connect**
   - 使用 Xcode 或 Application Loader 上传

## 🤖 Android 平台

### 环境要求

- **JDK**: 11 或更高版本
- **Android SDK**: API Level 21 (Android 5.0) 或更高
- **Python**: 3.8 或更高版本
- **内存**: 至少 4GB 可用内存

### 环境配置

1. **安装 JDK**
   ```bash
   # macOS
   brew install openjdk@11
   
   # Ubuntu/Debian
   sudo apt install openjdk-11-jdk
   
   # Windows
   # 下载并安装 Oracle JDK 或 OpenJDK
   ```

2. **安装 Android SDK**
   ```bash
   # 下载 Android Studio 或 Command Line Tools
   # 设置环境变量
   export ANDROID_HOME=/path/to/android/sdk
   export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
   export PATH=$PATH:$ANDROID_HOME/platform-tools
   ```

3. **安装必要的 SDK 组件**
   ```bash
   sdkmanager "platform-tools" "platforms;android-33" "build-tools;33.0.0"
   sdkmanager "ndk;25.1.8937393" "cmake;3.22.1"
   ```

### 构建步骤

1. **创建 Android 项目**
   ```bash
   python -m briefcase create android
   ```

2. **构建应用**
   ```bash
   python -m briefcase build android
   ```

3. **打包 APK**
   ```bash
   python -m briefcase package android
   ```

4. **安装到设备**
   ```bash
   # 连接 Android 设备，启用 USB 调试
   adb install dist/*.apk
   ```

### 发布到 Google Play

1. **生成签名密钥**
   ```bash
   keytool -genkey -v -keystore release-key.keystore -alias alias_name -keyalg RSA -keysize 2048 -validity 10000
   ```

2. **配置签名**
   ```bash
   # 编辑 android/gradle.properties
   MYAPP_RELEASE_STORE_FILE=../release-key.keystore
   MYAPP_RELEASE_KEY_ALIAS=alias_name
   MYAPP_RELEASE_STORE_PASSWORD=your_password
   MYAPP_RELEASE_KEY_PASSWORD=your_password
   ```

3. **构建发布版本**
   ```bash
   python -m briefcase package android --release
   ```

## 🔧 常见问题和解决方案

### iOS 常见问题

**问题**: "No signing certificate found"
**解决**: 
- 在 Xcode 中添加 Apple ID
- 下载开发者证书
- 在项目设置中选择正确的团队和证书

**问题**: "This app cannot be installed because its integrity could not be verified"
**解决**:
- 在设备的"设置 > 通用 > VPN与设备管理"中信任开发者

**问题**: 构建失败，找不到依赖
**解决**:
```bash
# 重新安装 iOS 特定依赖
pip uninstall toga-iOS
pip install toga-iOS
```

### Android 常见问题

**问题**: "ANDROID_HOME not set"
**解决**:
```bash
export ANDROID_HOME=/path/to/android/sdk
# 将此行添加到 ~/.bashrc 或 ~/.zshrc
```

**问题**: "SDK location not found"
**解决**:
```bash
# 创建 local.properties 文件
echo "sdk.dir=/path/to/android/sdk" > android/local.properties
```

**问题**: "Insufficient memory for the Java Runtime Environment"
**解决**:
```bash
# 增加 Java 堆内存
export JAVA_OPTS="-Xmx4g"
```

**问题**: APK 安装失败
**解决**:
- 启用"未知来源"安装
- 检查设备架构是否匹配
- 确保设备 Android 版本 >= 5.0

## 📊 性能优化

### iOS 优化

1. **减小应用大小**
   - 移除未使用的资源
   - 使用资产目录优化图片

2. **启动时间优化**
   - 延迟加载非关键组件
   - 优化初始化代码

### Android 优化

1. **APK 大小优化**
   ```bash
   # 启用 ProGuard 混淆
   python -m briefcase package android --release
   ```

2. **内存使用优化**
   - 及时释放不需要的对象
   - 使用内存分析工具检查泄漏

## 🚀 CI/CD 集成

### GitHub Actions 自动构建

项目已配置自动构建流程：

- **iOS**: 在 macOS 环境中自动构建
- **Android**: 在 Ubuntu 环境中自动构建
- **制品上传**: 构建完成后自动上传到 GitHub Releases

### 本地自动化脚本

使用提供的脚本进行本地测试：

```bash
# 测试所有平台构建
./scripts/test-build.sh

# 仅测试移动平台
# 在脚本执行过程中选择 "y" 进行移动平台测试
```

## 📚 参考资源

- [BeeWare iOS Tutorial](https://docs.beeware.org/en/latest/tutorial/tutorial-5/iOS.html)
- [BeeWare Android Tutorial](https://docs.beeware.org/en/latest/tutorial/tutorial-6/android.html)
- [iOS App Distribution Guide](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases)
- [Android Publishing Guide](https://developer.android.com/studio/publish)

## 💡 提示

1. **开发建议**: 先在桌面平台完成功能开发和测试，再适配移动平台
2. **调试技巧**: 使用 `python -m briefcase dev` 在桌面环境快速调试
3. **版本管理**: 移动平台的版本号需要与 `pyproject.toml` 中保持一致
4. **权限配置**: 移动应用可能需要额外的权限配置（如网络访问、存储访问等）
