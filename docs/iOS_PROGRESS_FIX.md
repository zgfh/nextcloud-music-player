# iOS 音频播放进度修复说明

## 问题描述
在iOS设备上，音乐播放时：
1. 总时间和播放时间一直显示为 0
2. 拖拽进度条后，时间会立即重置为 0

## 原因分析
1. **AVAudioPlayer API误用**：在iOS的AVAudioPlayer中，`duration`和`currentTime`是属性，不是方法，但代码中错误地调用了`duration()`和`currentTime()`
2. **返回值处理错误**：原代码中当播放器不支持某功能时返回`-1`，但修复后改为返回`0`，导致UI层逻辑需要相应调整
3. **时长缓存问题**：在iOS平台上，如果无法从播放器获取时长，需要从其他来源（如文件元数据）获取并缓存

## 修复内容

### 1. 修复 iOS 音频播放器 API 调用
**文件**：`src/nextcloud_music_player/platform_audio.py`

- 修复 `get_duration()` 方法：
  ```python
  # 错误的调用（修复前）
  duration = self._player.duration()
  
  # 正确的属性访问（修复后）
  duration = self._player.duration
  ```

- 修复 `get_position()` 方法：
  ```python
  # 错误的调用（修复前）
  position = self._player.currentTime()
  
  # 正确的属性访问（修复后）
  position = self._player.currentTime
  ```

- 修复 `seek()` 方法：
  ```python
  # 错误的调用（修复前）
  self._player.setCurrentTime(position)
  
  # 正确的属性赋值（修复后）
  self._player.currentTime = position
  ```

### 2. 改进返回值处理
- iOS播放器现在返回 `0.0` 而不是 `-1.0` 表示无效值
- 添加了详细的调试日志用于排查问题

### 3. 增强时长缓存机制
**文件**：`src/nextcloud_music_player/services/playback_service.py`

- 在 `play_music()` 方法中添加时长缓存：
  ```python
  # 获取并缓存音频时长
  try:
      duration = self.audio_player.get_duration()
      if duration > 0:
          self.current_song_state['duration'] = duration
          logger.info(f"缓存音频时长: {duration:.2f}秒")
  except Exception as e:
      logger.warning(f"获取音频时长失败: {e}")
  ```

- 改进 `get_duration()` 方法的逻辑：
  ```python
  if duration > 0:  # 改为检查 > 0 而不是 >= 0
      return duration
  ```

### 4. 优化UI层进度更新逻辑
**文件**：`src/nextcloud_music_player/views/playback_view.py`

- 改进 `update_progress_only()` 方法：
  - 更好的错误处理和缓存机制
  - 当播放器无法提供时长时，尝试从缓存或歌曲元数据获取
  - 添加更详细的调试日志

- 改进 `on_seek()` 方法：
  - 增强时长获取逻辑
  - 更好的错误处理
  - 在拖拽后强制更新UI显示

## 测试验证
1. ✅ 桌面版本正常工作（使用pygame播放器）
2. 🔄 iOS版本正在测试中（使用AVAudioPlayer）

## 预期效果
修复后，在iOS设备上：
1. 播放音乐时能正确显示总时长和当前播放时间
2. 拖拽进度条后时间不会重置为0
3. 进度条能正确反映播放进度
4. 时间显示格式正确（MM:SS格式）

## 兼容性
- ✅ 保持与桌面版本的完全兼容
- ✅ 保持与现有播放列表功能的兼容
- ✅ 保持与现有配置系统的兼容
