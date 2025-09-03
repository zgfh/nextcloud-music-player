"""
播放控制组件 - 专门处理播放控制UI和逻辑
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import logging
from typing import Optional, Callable, Any

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
        
        # 创建UI组件
        self.create_controls()
        
        logger.info("播放控制组件初始化完成")
    
    def create_controls(self):
        """创建播放控制按钮"""
        # 主控制容器
        self.container = toga.Box(style=Pack(
            direction=COLUMN,
            padding=5,
            alignment="center"
        ))
        
        # 创建播放控制按钮行
        self.create_playback_buttons()
        
        # 创建音量和播放模式控制
        self.create_volume_and_mode_controls()
        
        # 添加到主容器
        self.container.add(self.controls_box)
        self.container.add(self.volume_mode_box)
    
    def create_playback_buttons(self):
        """创建播放控制按钮"""
        self.controls_box = toga.Box(style=Pack(
            direction=ROW,
            padding=8,
            alignment="center"
        ))
        
        # 上一曲按钮
        self.prev_button = toga.Button(
            "⏮️",
            on_press=self._on_previous_song,
            style=Pack(
                width=45,
                height=35,
                padding=(0, 3),
                font_size=14
            )
        )
        
        # 播放/暂停按钮
        self.play_pause_button = toga.Button(
            "▶️",
            on_press=self._on_toggle_playback,
            style=Pack(
                width=60,
                height=40,
                padding=(0, 8),
                font_size=16
            )
        )
        
        # 下一曲按钮
        self.next_button = toga.Button(
            "⏭️",
            on_press=self._on_next_song,
            style=Pack(
                width=45,
                height=35,
                padding=(0, 3),
                font_size=14
            )
        )
        
        # 停止按钮
        self.stop_button = toga.Button(
            "⏹️",
            on_press=self._on_stop_playback,
            style=Pack(
                width=45,
                height=35,
                padding=(0, 3),
                font_size=14
            )
        )
        
        # 添加按钮到容器
        self.controls_box.add(self.prev_button)
        self.controls_box.add(self.play_pause_button)
        self.controls_box.add(self.next_button)
        self.controls_box.add(self.stop_button)
    
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
        
        # 初始化播放模式按钮状态
        self.update_mode_buttons()
    
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
        """更新播放模式按钮状态"""
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
                    # 选中状态
                    button.style.background_color = "#007bff"
                    button.style.color = "white"
                else:
                    # 未选中状态
                    button.style.background_color = "#f8f9fa"
                    button.style.color = "black"
                    
        except Exception as e:
            logger.error(f"更新播放模式按钮状态失败: {e}")
    
    def update_play_pause_button(self, is_playing: bool):
        """更新播放/暂停按钮状态"""
        try:
            if is_playing:
                self.play_pause_button.text = "⏸️"
            else:
                self.play_pause_button.text = "▶️"
        except Exception as e:
            logger.error(f"更新播放/暂停按钮失败: {e}")
    
    def set_volume(self, volume: int):
        """设置音量滑块值"""
        try:
            if 0 <= volume <= 100:
                self.volume_slider.value = volume
        except Exception as e:
            logger.error(f"设置音量滑块失败: {e}")
    
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
