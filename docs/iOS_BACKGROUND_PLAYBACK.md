# iOS 后台播放配置指南

## 问题描述
iOS 设备息屏后音乐播放停止的问题是由于 iOS 系统的后台应用限制造成的。为了在 iOS 上实现后台音频播放，需要进行特定的配置。

## 解决方案

### 1. Info.plist 配置
应用需要在 Info.plist 中声明后台音频播放权限：

```xml
<key>UIBackgroundModes</key>
<array>
    <string>audio</string>
</array>
```

### 2. AVAudioSession 配置
在代码中需要正确配置 AVAudioSession：

```python
# 设置音频会话类别为播放模式
session.setCategory("AVAudioSessionCategoryPlayback", error=None)
session.setActive(True, error=None)
```

### 3. 已实现的修复

#### A. pyproject.toml 更新
- 添加了 `UIBackgroundModes = ["audio"]` 配置
- 这将在构建时自动添加到 Info.plist

#### B. iOS 音频播放器增强
- 创建了 `ios_background_audio.py` 模块来管理后台音频
- 更新了 `iOSAudioPlayer` 类以支持后台播放
- 正确配置了 AVAudioSession

#### C. 音频会话管理
- 在播放开始时激活音频会话
- 在应用初始化时配置后台播放权限
- 处理音频中断（如来电等）

### 4. 使用说明

#### 重新构建应用
修改配置后需要重新构建 iOS 应用：

```bash
# 清理之前的构建
briefcase build iOS
```

#### 测试后台播放
1. 启动应用并开始播放音乐
2. 按下设备的电源键使屏幕变黑
3. 音乐应该继续播放
4. 可以通过控制中心或锁屏界面控制播放

### 5. 注意事项

#### iOS 系统限制
- 应用必须正在播放音频才能保持后台活跃
- 如果音频播放停止，应用可能会被系统暂停
- 后台播放时间有限制，通常为几分钟到几小时

#### 权限要求
- 用户可能需要在设置中允许应用的后台应用刷新
- 首次运行时应用会请求音频相关权限

#### 开发者设置
在 Xcode 项目中确保以下设置：
- Background Modes 包含 "Audio, AirPlay, and Picture in Picture"
- App Transport Security 允许网络连接（用于 NextCloud 同步）

### 6. 故障排除

#### 如果后台播放仍然不工作：

1. **检查 Info.plist**：
   确认构建后的 Info.plist 包含 UIBackgroundModes

2. **检查音频会话**：
   查看日志确认 AVAudioSession 配置成功

3. **iOS 设置检查**：
   - 设置 → 通用 → 后台应用刷新 → 确保应用已启用
   - 设置 → 隐私与安全性 → 媒体与 Apple Music → 确保应用有权限

4. **重新安装应用**：
   有时需要完全删除应用并重新安装以应用新的权限

### 7. 相关文件

- `src/nextcloud_music_player/ios_background_audio.py` - iOS 后台音频管理器
- `src/nextcloud_music_player/platform_audio.py` - 更新的 iOS 音频播放器
- `pyproject.toml` - 添加了后台播放权限配置
- `ios-info-template.plist` - 完整的 Info.plist 模板示例

通过这些修改，iOS 应用现在应该能够在息屏后继续播放音乐。
