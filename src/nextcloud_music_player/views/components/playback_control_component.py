"""
播放控制组件 - 专门处理播放控制UI和逻辑
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import logging
from typing import Optional, Callable, Any
from ...utils.platform_ui import (
    get_safe_area_bottom_padding, 
    get_button_touch_size, 
    get_control_padding, 
    get_font_sizes
)

logger = logging.getLogger(__name__)

class PlaybackControlComponent:
    """播放控制组件 - 负责播放控制按钮和相关UI"""
    
    def __init__(self, app, playback_controller, on_play_mode_change_callback=None):
        """
        初始化播放控制组件
        
        Args:
            app: 应用实例
            playback_controller: 播放控制器实例
            on_play_mode_change_callback: 播放模式改变回调
        """
        self.app = app
        self.playback_controller = playback_controller
        self.on_play_mode_change_callback = on_play_mode_change_callback
        
        # 防止重复点击的标志
        self._button_busy = False
        
        # 获取平台相关的UI参数
        self.button_sizes = get_button_touch_size()
        self.paddings = get_control_padding()
        self.font_sizes = get_font_sizes()
        self.safe_area_bottom = get_safe_area_bottom_padding()
        
        # 创建UI组件
        self.create_controls()
        
        logger.info("播放控制组件初始化完成")
    
    @property
    def widget(self):
        """获取主要控件容器"""
        return self.container
    
    def create_controls(self):
        """创建播放控制按钮 - 平台自适应的手机操作布局"""
        # 主控制容器 - 使用平台自适应的底部安全区域
        self.container = toga.Box(style=Pack(
            direction=COLUMN,
            padding=self.paddings["container"],  # 使用平台自适应的padding
            alignment="center"
        ))
        
        # 创建播放控制按钮行
        self.create_playback_buttons()
        
        # 创建进度显示区域 - 在按钮上方
        self.create_progress_section()
        
        # 创建音量和播放模式控制 - 一行式布局
        self.create_compact_volume_and_mode_controls()
        
        # 添加到主容器 - 紧凑布局顺序
        self.container.add(self.progress_box)  # 进度条在顶部
        self.container.add(self.volume_mode_box)  # 音量和模式在中间
        self.container.add(self.controls_box)  # 播放按钮在底部
    
    def create_playback_buttons(self):
        """创建播放控制按钮 - 使用相对百分比宽度的响应式设计"""
        self.controls_box = toga.Box(style=Pack(
            direction=ROW,
            padding=self.paddings["controls"],  # 使用平台自适应的padding
            alignment="center",
            flex=1  # 使容器能够填充可用空间
        ))
        
        # 计算平台自适应的高度
        button_height = self.button_sizes["primary_height"]
        secondary_height = self.button_sizes["secondary_height"]
        
        # 上一曲按钮 - 使用flex和百分比宽度
        self.prev_button = toga.Button(
            "⏮️",
            on_press=self._on_previous_song,
            style=Pack(
                flex=0.8,  # 相对宽度，占可用空间的0.8倍
                height=secondary_height,
                padding=self.paddings["button"],
                font_size=self.font_sizes["icon_secondary"],
                background_color="#f8f9fa",
                color="#495057"
            )
        )
        
        # 播放/暂停按钮 - 作为主要控制按钮，稍大一些
        self.play_pause_button = toga.Button(
            "▶️",
            on_press=self._on_toggle_playback,
            style=Pack(
                flex=1.2,  # 相对宽度，占可用空间的1.2倍（最大）
                height=button_height,
                padding=self.paddings["button"],
                font_size=self.font_sizes["icon_primary"],
                background_color="#007bff",
                color="white"
            )
        )
        
        # 下一曲按钮 - 使用flex和百分比宽度
        self.next_button = toga.Button(
            "⏭️",
            on_press=self._on_next_song,
            style=Pack(
                flex=0.8,  # 相对宽度，占可用空间的0.8倍
                height=secondary_height,
                padding=self.paddings["button"],
                font_size=self.font_sizes["icon_secondary"],
                background_color="#f8f9fa",
                color="#495057"
            )
        )
        
        # 停止按钮 - 使用flex和百分比宽度，确保在所有设备上可见
        self.stop_button = toga.Button(
            "⏹️",
            on_press=self._on_stop_playback,
            style=Pack(
                flex=0.8,  # 相对宽度，占可用空间的0.8倍
                height=secondary_height,
                padding=self.paddings["button"],
                font_size=self.font_sizes["icon_secondary"],
                background_color="#dc3545",
                color="white"
            )
        )
        
        # 添加按钮到容器
        self.controls_box.add(self.prev_button)
        self.controls_box.add(self.play_pause_button)
        self.controls_box.add(self.next_button)
        self.controls_box.add(self.stop_button)
    
    def create_compact_volume_and_mode_controls(self):
        """创建紧凑的音量和播放模式控制 - 使用相对百分比宽度的响应式设计"""
        self.volume_mode_box = toga.Box(style=Pack(
            direction=ROW,
            padding=self.paddings["volume_mode"],  # 使用平台自适应的padding
            alignment="center",
            flex=1  # 使容器能够填充可用空间
        ))
        
        # 音量控制 - 使用flex布局，减少占用空间
        volume_box = toga.Box(style=Pack(
            direction=ROW,
            padding=(0, 8, 0, 0),
            alignment="center",
            flex=1  # 音量控制占正常空间
        ))
        
        volume_label = toga.Label(
            "🔊",
            style=Pack(
                font_size=self.font_sizes["text_normal"],
                padding=(0, 3, 0, 0)
            )
        )
        
        self.volume_slider = toga.Slider(
            range=(0, 100),
            value=70,
            on_change=self._on_volume_change,
            style=Pack(
                flex=1,  # 滑块占剩余空间
                padding=(0, 0, 0, 0)
            )
        )
        
        volume_box.add(volume_label)
        volume_box.add(self.volume_slider)
        
        # 播放模式按钮 - 使用flex布局确保所有按钮可见，给更多空间
        mode_box = toga.Box(style=Pack(
            direction=ROW,
            padding=(0, 0, 0, 8),
            alignment="center",
            flex=1.5  # 模式按钮区域占更多空间，让按钮更大
        ))
        
        # 播放模式按钮 - 使用flex确保均匀分布
        self.normal_button = toga.Button(
            "🔁",
            on_press=lambda widget: self._set_play_mode("normal"),
            style=Pack(
                flex=1,  # 均匀分布
                height=self.button_sizes["small_height"],
                padding=self.paddings["mode_button"],
                font_size=self.font_sizes["icon_small"],
                background_color="#f8f9fa",
                color="#495057"
            )
        )
        
        self.repeat_one_button = toga.Button(
            "🔂",
            on_press=lambda widget: self._set_play_mode("repeat_one"),
            style=Pack(
                flex=1,  # 均匀分布
                height=self.button_sizes["small_height"],
                padding=self.paddings["mode_button"],
                font_size=self.font_sizes["icon_small"],
                background_color="#28a745",  # 默认选中状态
                color="white"
            )
        )
        
        self.repeat_all_button = toga.Button(
            "🔁",
            on_press=lambda widget: self._set_play_mode("repeat_all"),
            style=Pack(
                flex=1,  # 均匀分布
                height=self.button_sizes["small_height"],
                padding=self.paddings["mode_button"],
                font_size=self.font_sizes["icon_small"],
                background_color="#f8f9fa",
                color="#495057"
            )
        )
        
        self.shuffle_button = toga.Button(
            "🔀",
            on_press=lambda widget: self._set_play_mode("shuffle"),
            style=Pack(
                flex=1,  # 均匀分布
                height=self.button_sizes["small_height"],
                padding=self.paddings["mode_button"],
                font_size=self.font_sizes["icon_small"],
                background_color="#f8f9fa",
                color="#495057"
            )
        )
        
        mode_box.add(self.normal_button)
        mode_box.add(self.repeat_one_button)
        mode_box.add(self.repeat_all_button)
        mode_box.add(self.shuffle_button)
        
        self.volume_mode_box.add(volume_box)
        self.volume_mode_box.add(mode_box)
    
    def create_volume_and_mode_controls(self):
        """创建音量和播放模式控制"""
        self.volume_mode_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=5,
            alignment="center"
        ))
        
        # 音量控制
        volume_label = toga.Label(
            "🔊 音量",
            style=Pack(
                font_size=12,
                padding=(0, 0, 2, 0),
                text_align="center"
            )
        )
        
        self.volume_slider = toga.Slider(
            range=(0, 100),
            value=70,
            on_change=self._on_volume_change,
            style=Pack(
                width=200,
                padding=(0, 0, 5, 0)
            )
        )
        
        # 播放模式控制
        mode_label = toga.Label(
            "🎵 播放模式",
            style=Pack(
                font_size=12,
                padding=(0, 0, 2, 0),
                text_align="center"
            )
        )
        
        # 播放模式按钮行
        self.mode_buttons_box = toga.Box(style=Pack(
            direction=ROW,
            padding=2,
            alignment="center"
        ))
        
        # 播放模式按钮
        self.normal_button = toga.Button(
            "🔁",
            on_press=lambda widget: self._set_play_mode("normal"),
            style=Pack(
                width=40,
                height=30,
                padding=(0, 2),
                font_size=12
            )
        )
        
        self.repeat_one_button = toga.Button(
            "🔂",
            on_press=lambda widget: self._set_play_mode("repeat_one"),
            style=Pack(
                width=40,
                height=30,
                padding=(0, 2),
                font_size=12
            )
        )
        
        self.repeat_all_button = toga.Button(
            "🔁",
            on_press=lambda widget: self._set_play_mode("repeat_all"),
            style=Pack(
                width=40,
                height=30,
                padding=(0, 2),
                font_size=12
            )
        )
        
        self.shuffle_button = toga.Button(
            "🔀",
            on_press=lambda widget: self._set_play_mode("shuffle"),
            style=Pack(
                width=40,
                height=30,
                padding=(0, 2),
                font_size=12
            )
        )
        
        # 添加模式按钮到容器
        self.mode_buttons_box.add(self.normal_button)
        self.mode_buttons_box.add(self.repeat_one_button)
        self.mode_buttons_box.add(self.repeat_all_button)
        self.mode_buttons_box.add(self.shuffle_button)
        
        # 添加音量和模式控制到容器
        self.volume_mode_box.add(volume_label)
        self.volume_mode_box.add(self.volume_slider)
        self.volume_mode_box.add(mode_label)
        self.volume_mode_box.add(self.mode_buttons_box)
        
        # 创建进度显示区域
        self.create_progress_section()
        
        # 初始化播放模式按钮状态
        self.update_mode_buttons()
    
    def create_progress_section(self):
        """创建播放进度区域 - 使用相对百分比宽度的响应式设计"""
        self.progress_box = toga.Box(style=Pack(
            direction=ROW,  # 改为水平布局，更紧凑
            padding=self.paddings["progress"],  # 使用平台自适应的padding
            alignment="center",
            flex=1  # 使容器能够填充可用空间
        ))
        
        # 当前时间标签 - 使用平台自适应字体大小
        self.current_time_label = toga.Label(
            "00:00",
            style=Pack(
                font_size=self.font_sizes["text_normal"],
                padding=(0, 6, 0, 0),  # 增加右边距
                color="#666666",
                width=45  # 固定宽度确保布局稳定
            )
        )
        
        # 进度条（使用滑块模拟） - 使用flex占据剩余空间
        self.progress_slider = toga.Slider(
            min=0,
            max=100,
            value=0,
            on_change=self._on_seek,
            style=Pack(
                flex=1,         # 占据剩余空间，自适应屏幕宽度
                padding=(0, 8)  # 增加左右间距
            )
        )
        
        # 总时间标签 - 使用平台自适应字体大小
        self.total_time_label = toga.Label(
            "00:00",
            style=Pack(
                font_size=self.font_sizes["text_normal"],
                padding=(0, 0, 0, 6),  # 增加左边距
                color="#666666",
                width=45  # 固定宽度确保布局稳定
            )
        )
        
        # 添加防抖控制变量
        self._updating_progress = False  # 标记是否正在程序更新进度条
        self._last_user_seek_time = 0  # 用户最后一次拖拽时间
        
        self.progress_box.add(self.current_time_label)
        self.progress_box.add(self.progress_slider)
        self.progress_box.add(self.total_time_label)
    
    async def _on_previous_song(self, widget):
        """上一曲按钮点击处理"""
        await self._safe_button_action(self.playback_controller.previous_song, "上一曲")
    
    async def _on_next_song(self, widget):
        """下一曲按钮点击处理"""
        await self._safe_button_action(self.playback_controller.next_song, "下一曲")
    
    async def _on_toggle_playback(self, widget):
        """播放/暂停按钮点击处理"""
        await self._safe_button_action(self.playback_controller.toggle_playback, "播放/暂停")
    
    async def _on_stop_playback(self, widget):
        """停止按钮点击处理"""
        await self._safe_button_action(self.playback_controller.stop_playback, "停止")
    
    async def _safe_button_action(self, action_func, action_name: str):
        """安全的按钮操作，防止重复点击"""
        if self._button_busy:
            logger.warning(f"按钮操作繁忙，忽略{action_name}操作")
            return
        
        try:
            self._button_busy = True
            logger.info(f"执行{action_name}操作")
            
            result = await action_func()
            
            if result is not None and not result:
                logger.warning(f"{action_name}操作失败")
            else:
                logger.info(f"{action_name}操作完成")
                
        except Exception as e:
            logger.error(f"{action_name}操作异常: {e}")
        finally:
            self._button_busy = False
    
    def _on_volume_change(self, widget):
        """音量改变处理"""
        try:
            volume = int(widget.value)
            logger.info(f"音量调整为: {volume}%")
            
            # 这里可以调用播放服务设置音量
            # if hasattr(self.playback_controller.playback_service, 'set_volume'):
            #     self.playback_controller.playback_service.set_volume(volume / 100.0)
            
        except Exception as e:
            logger.error(f"设置音量失败: {e}")
    
    def _set_play_mode(self, mode: str):
        """设置播放模式"""
        try:
            from ...services.playback_controller import PlayMode
            
            # 将字符串模式转换为枚举
            mode_enum = None
            if mode == "normal":
                mode_enum = PlayMode.NORMAL
            elif mode == "repeat_one":
                mode_enum = PlayMode.REPEAT_ONE
            elif mode == "repeat_all":
                mode_enum = PlayMode.REPEAT_ALL
            elif mode == "shuffle":
                mode_enum = PlayMode.SHUFFLE
            
            if mode_enum:
                self.playback_controller.set_play_mode(mode_enum)
                self.update_mode_buttons()
                
                # 通知回调
                if self.on_play_mode_change_callback:
                    self.on_play_mode_change_callback(mode)
                
                logger.info(f"播放模式已设置为: {mode}")
            else:
                logger.error(f"未知的播放模式: {mode}")
                
        except Exception as e:
            logger.error(f"设置播放模式失败: {e}")
    
    def update_mode_buttons(self):
        """更新播放模式按钮状态 - 使用新的颜色样式"""
        try:
            current_mode = self.playback_controller.get_play_mode()
            
            # 重置所有按钮样式
            buttons = {
                "normal": self.normal_button,
                "repeat_one": self.repeat_one_button,
                "repeat_all": self.repeat_all_button,
                "shuffle": self.shuffle_button
            }
            
            for mode, button in buttons.items():
                if hasattr(current_mode, 'value') and current_mode.value == mode:
                    # 选中状态 - 绿色背景
                    button.style.background_color = "#28a745"
                    button.style.color = "white"
                else:
                    # 未选中状态 - 浅灰色背景
                    button.style.background_color = "#f8f9fa"
                    button.style.color = "#495057"
                    
        except Exception as e:
            logger.error(f"更新播放模式按钮状态失败: {e}")
    
    def update_play_pause_button(self, is_playing: bool):
        """更新播放/暂停按钮状态 - 包含颜色样式更新"""
        try:
            if is_playing:
                self.play_pause_button.text = "⏸️"
                self.play_pause_button.style.background_color = "#ffc107"  # 暂停时黄色
            else:
                self.play_pause_button.text = "▶️"
                self.play_pause_button.style.background_color = "#007bff"  # 播放时蓝色
            # 保持白色文字
            self.play_pause_button.style.color = "white"
        except Exception as e:
            logger.error(f"更新播放/暂停按钮失败: {e}")
    
    def set_volume(self, volume: int):
        """设置音量滑块值"""
        try:
            if 0 <= volume <= 100:
                self.volume_slider.value = volume
        except Exception as e:
            logger.error(f"设置音量滑块失败: {e}")
    
    def _on_seek(self, widget):
        """进度条拖拽处理"""
        try:
            # 如果是程序自动更新进度条，直接返回
            if self._updating_progress:
                logger.debug("程序更新进度条，忽略on_change事件")
                return
            
            # 防抖处理
            import time
            current_time = time.time()
            
            # 检查是否在短时间内多次触发
            if hasattr(self, '_last_user_seek_time'):
                time_diff = current_time - self._last_user_seek_time
                if time_diff < 0.5:  # 0.5秒的防抖间隔
                    logger.debug(f"忽略频繁的用户进度条拖拽 (间隔: {time_diff:.2f}s)")
                    return
            
            # 记录用户操作时间
            self._last_user_seek_time = current_time
            logger.info(f"用户拖拽进度条: {widget.value:.1f}%")
            
            # 检查是否正在播放
            if not self.playback_controller.playback_service.is_playing():
                logger.warning("当前没有播放音乐，无法跳转")
                self.reset_progress_to_current()
                return
            
            # 计算新的播放位置
            duration = self.get_current_duration()
            if duration > 0:
                new_position = (widget.value / 100) * duration
                
                # 跳转到新位置
                success = self.playback_controller.playback_service.seek_to_position(new_position)
                if success:
                    logger.info(f"跳转到位置: {new_position:.2f}秒 ({widget.value:.1f}%)")
                    # 立即更新时间显示
                    self.update_time_display(new_position, duration)
                else:
                    logger.warning("跳转失败")
                    self.reset_progress_to_current()
            else:
                logger.warning("无法跳转：未获取到有效的音频时长")
                self.reset_progress_to_current()
                
        except Exception as e:
            logger.error(f"拖拽进度条失败: {e}")
    
    def get_current_duration(self):
        """获取当前歌曲时长"""
        try:
            # 首先尝试从播放器获取
            if self.playback_controller.playback_service.audio_player:
                duration = self.playback_controller.playback_service.audio_player.get_duration()
                if duration > 0:
                    return duration
            
            # 尝试从缓存获取
            if hasattr(self, '_cached_duration') and self._cached_duration > 0:
                return self._cached_duration
            
            # 默认返回0
            return 0
        except Exception as e:
            logger.error(f"获取歌曲时长失败: {e}")
            return 0
    
    def reset_progress_to_current(self):
        """重置进度条到当前位置"""
        try:
            position = self.get_current_position()
            duration = self.get_current_duration()
            
            if duration > 0:
                current_progress = (position / duration) * 100
                self._updating_progress = True
                self.progress_slider.value = current_progress
                self._updating_progress = False
            else:
                self._updating_progress = True
                self.progress_slider.value = 0
                self._updating_progress = False
                
        except Exception as e:
            logger.error(f"重置进度条失败: {e}")
    
    def get_current_position(self):
        """获取当前播放位置"""
        try:
            if self.playback_controller.playback_service.audio_player:
                position = self.playback_controller.playback_service.audio_player.get_position()
                return max(0, position)  # 确保位置不为负数
            return 0
        except Exception as e:
            logger.error(f"获取播放位置失败: {e}")
            return 0
    
    def update_progress(self, position: float = None, duration: float = None):
        """更新播放进度"""
        try:
            # 获取实时位置和时长
            if position is None:
                position = self.get_current_position()
            if duration is None:
                duration = self.get_current_duration()
            
            # 缓存时长
            if duration > 0:
                self._cached_duration = duration
            
            # 更新进度条
            if duration > 0:
                progress_percent = (position / duration) * 100
                
                # 只有在进度变化较大时才更新进度条
                current_progress = getattr(self.progress_slider, 'value', 0)
                if abs(progress_percent - current_progress) > 0.1:  # 只有变化超过0.1%才更新
                    self._updating_progress = True
                    self.progress_slider.value = progress_percent
                    self._updating_progress = False
            
            # 更新时间显示
            self.update_time_display(position, duration)
            
        except Exception as e:
            logger.error(f"更新播放进度失败: {e}")
    
    def update_time_display(self, position: float, duration: float):
        """更新时间显示"""
        try:
            # 格式化时间
            current_min = int(position // 60)
            current_sec = int(position % 60)
            total_min = int(duration // 60)
            total_sec = int(duration % 60)
            
            # 更新显示
            self.current_time_label.text = f"{current_min:02d}:{current_sec:02d}"
            self.total_time_label.text = f"{total_min:02d}:{total_sec:02d}"
            
        except Exception as e:
            logger.error(f"更新时间显示失败: {e}")
    
    def reset_progress(self):
        """重置进度显示"""
        try:
            self._updating_progress = True
            self.progress_slider.value = 0
            self._updating_progress = False
            self.current_time_label.text = "00:00"
            self.total_time_label.text = "00:00"
        except Exception as e:
            logger.error(f"重置进度显示失败: {e}")
    
    def get_volume(self) -> int:
        """获取当前音量值"""
        try:
            return int(self.volume_slider.value)
        except:
            return 70  # 默认音量
    
    def enable_controls(self, enabled: bool = True):
        """启用或禁用控制按钮"""
        try:
            self.prev_button.enabled = enabled
            self.next_button.enabled = enabled
            self.play_pause_button.enabled = enabled
            self.stop_button.enabled = enabled
        except Exception as e:
            logger.error(f"设置控制按钮状态失败: {e}")
    
    @property
    def widget(self):
        """返回组件的主容器widget"""
        return self.container
