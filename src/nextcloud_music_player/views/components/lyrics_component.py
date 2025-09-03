"""
歌词显示组件 - 负责在UI中显示歌词
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import logging
import asyncio
from typing import Optional, List, Dict, Any

from ...services.lyrics_service import LyricsService, LyricLine

logger = logging.getLogger(__name__)


class LyricsDisplayComponent:
    """歌词显示组件"""
    
    def __init__(self, app, config_manager=None, lyrics_service=None):
        self.app = app
        self.config_manager = config_manager
        
        # 使用传入的歌词服务或创建新的
        if lyrics_service:
            self.lyrics_service = lyrics_service
        else:
            self.lyrics_service = LyricsService(config_manager)
        
        # UI组件
        self.container = None
        self.lyrics_scroll = None
        self.lyrics_box = None
        self.title_label = None
        self.no_lyrics_label = None
        self.download_button = None  # 添加下载按钮
        self.lyrics_labels = []  # 歌词行标签列表
        
        # 状态
        self.is_visible = True
        self.current_position = 0.0
        self.current_song_name = None
        self.auto_scroll = True  # 是否自动滚动
        
        # 显示设置
        self.context_lines = self.config_manager.get("lyrics.context_lines", 3) if config_manager else 3
        self.font_size = self.config_manager.get("lyrics.font_size", 12) if config_manager else 12
        self.highlight_color = self.config_manager.get("lyrics.highlight_color", "#007bff") if config_manager else "#007bff"
        self.normal_color = self.config_manager.get("lyrics.normal_color", "#666666") if config_manager else "#666666"
        
        self.build_interface()
        logger.info("歌词显示组件初始化完成")
    
    def build_interface(self):
        """构建歌词显示界面"""
        # 主容器
        self.container = toga.Box(style=Pack(
            direction=COLUMN,
            padding=8,
            flex=1
        ))
        
        # 标题栏
        title_box = toga.Box(style=Pack(
            direction=ROW,
            padding=(0, 0, 5, 0),
            alignment="center"
        ))
        
        self.title_label = toga.Label(
            "🎵 歌词",
            style=Pack(
                flex=1,
                font_size=14,
                font_weight="bold",
                color="#212529"
            )
        )
        
        # 设置按钮（暂时隐藏，将来可以用于歌词设置）
        self.settings_button = toga.Button(
            "⚙️",
            on_press=self.show_lyrics_settings,
            style=Pack(
                width=30,
                height=25,
                font_size=10,
                visibility="hidden"  # 暂时隐藏
            )
        )
        
        # 下载歌词按钮
        self.download_button = toga.Button(
            "📥",
            on_press=self.download_lyrics_manually,
            style=Pack(
                width=30,
                height=25,
                font_size=10,
                visibility="hidden"  # 初始隐藏，只在需要时显示
            )
        )
        
        title_box.add(self.title_label)
        title_box.add(self.download_button)
        title_box.add(self.settings_button)
        
        # 歌词显示区域（可滚动）
        self.lyrics_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=5
        ))
        
        self.lyrics_scroll = toga.ScrollContainer(
            content=self.lyrics_box,
            style=Pack(
                flex=1,
                background_color="#f8f9fa"
            )
        )
        
        # 无歌词提示
        self.no_lyrics_label = toga.Label(
            "暂无歌词\n歌词文件格式: [歌曲名].lrc",
            style=Pack(
                text_align="center",
                color="#999999",
                font_size=11,
                padding=20
            )
        )
        
        # 初始显示无歌词状态
        self.lyrics_box.add(self.no_lyrics_label)
        
        # 组装界面
        self.container.add(title_box)
        self.container.add(self.lyrics_scroll)
    
    def get_widget(self):
        """获取组件的主要widget"""
        return self.container
    
    def load_lyrics_for_song(self, song_name: str, auto_download: bool = True) -> bool:
        """
        为指定歌曲加载歌词
        
        Args:
            song_name: 歌曲名称
            auto_download: 是否自动下载歌词
            
        Returns:
            是否成功加载歌词
        """
        try:
            logger.info(f"加载歌词: {song_name}")
            
            # 清除当前显示
            self.clear_lyrics_display()
            
            # 加载歌词（支持自动下载）
            success = self.lyrics_service.load_lyrics(song_name, auto_download)
            self.current_song_name = song_name
            
            if success:
                # 隐藏下载按钮
                self.download_button.style.visibility = "hidden"
                
                # 更新标题显示歌曲名
                display_name = song_name
                if display_name.endswith('.mp3'):
                    display_name = display_name[:-4]
                self.title_label.text = f"🎵 {display_name}"
                
                # 显示歌词元数据（如果有）
                metadata = self.lyrics_service.get_lyrics_metadata()
                if metadata:
                    self.add_metadata_display(metadata)
                
                # 显示所有歌词行
                self.display_all_lyrics()
                
                logger.info(f"成功加载并显示歌词: {song_name}")
                return True
            else:
                # 显示无歌词状态和下载按钮
                self.show_no_lyrics_message(song_name)
                self.download_button.style.visibility = "visible"
                logger.info(f"未找到歌词文件: {song_name}")
                return False
                
        except Exception as e:
            logger.error(f"加载歌词失败: {song_name}, 错误: {e}")
            self.show_no_lyrics_message(song_name, f"加载失败: {str(e)}")
            self.download_button.style.visibility = "visible"
            return False
    
    def clear_lyrics_display(self):
        """清除歌词显示"""
        try:
            self.lyrics_box.clear()
            self.lyrics_labels = []
            logger.debug("已清除歌词显示")
        except Exception as e:
            logger.error(f"清除歌词显示失败: {e}")
    
    def show_no_lyrics_message(self, song_name: str = None, error_msg: str = None):
        """显示无歌词消息"""
        try:
            self.clear_lyrics_display()
            
            if error_msg:
                message = f"歌词加载失败\n{error_msg}"
            elif song_name:
                display_name = song_name
                if display_name.endswith('.mp3'):
                    display_name = display_name[:-4]
                message = f"暂无歌词\n歌曲: {display_name}\n歌词文件: {display_name}.lrc"
            else:
                message = "暂无歌词\n歌词文件格式: [歌曲名].lrc"
            
            self.no_lyrics_label.text = message
            self.lyrics_box.add(self.no_lyrics_label)
            
            # 重置标题
            self.title_label.text = "🎵 歌词"
            
        except Exception as e:
            logger.error(f"显示无歌词消息失败: {e}")
    
    def add_metadata_display(self, metadata: Dict[str, str]):
        """添加歌词元数据显示"""
        try:
            if not metadata:
                return
            
            # 创建元数据显示区域
            metadata_box = toga.Box(style=Pack(
                direction=COLUMN,
                padding=(0, 0, 10, 0),
                background_color="#e9ecef"
            ))
            
            # 显示常见的元数据
            display_fields = [
                ('ti', '标题'),
                ('ar', '艺术家'),
                ('al', '专辑'),
                ('by', '制作')
            ]
            
            for field, label in display_fields:
                if field in metadata and metadata[field]:
                    info_label = toga.Label(
                        f"{label}: {metadata[field]}",
                        style=Pack(
                            font_size=10,
                            color="#495057",
                            padding=(2, 5)
                        )
                    )
                    metadata_box.add(info_label)
            
            if len(metadata_box.children) > 0:
                self.lyrics_box.add(metadata_box)
                
        except Exception as e:
            logger.error(f"添加元数据显示失败: {e}")
    
    def display_all_lyrics(self):
        """显示所有歌词行"""
        try:
            lyrics_lines = self.lyrics_service.get_all_lyrics_lines()
            if not lyrics_lines:
                self.show_no_lyrics_message(self.current_song_name)
                return
            
            # 创建歌词行标签
            for i, lyric_line in enumerate(lyrics_lines):
                lyric_label = self.create_lyric_label(lyric_line, i)
                self.lyrics_box.add(lyric_label)
                self.lyrics_labels.append(lyric_label)
            
            logger.debug(f"显示了 {len(lyrics_lines)} 行歌词")
            
        except Exception as e:
            logger.error(f"显示歌词失败: {e}")
    
    def create_lyric_label(self, lyric_line: LyricLine, index: int) -> toga.Label:
        """
        创建歌词行标签
        
        Args:
            lyric_line: 歌词行对象
            index: 行索引
            
        Returns:
            歌词标签
        """
        # 格式化时间显示
        minutes = int(lyric_line.time_seconds // 60)
        seconds = int(lyric_line.time_seconds % 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        # 创建标签文本
        text = lyric_line.text if lyric_line.text else "♪"
        display_text = f"[{time_str}] {text}"
        
        # 创建标签
        label = toga.Label(
            display_text,
            style=Pack(
                font_size=self.font_size,
                color=self.normal_color,
                padding=(3, 5),
                background_color="transparent"
            )
        )
        
        # 存储相关信息到标签
        label.lyric_line = lyric_line
        label.line_index = index
        
        return label
    
    def update_lyrics_position(self, position_seconds: float):
        """
        更新歌词显示位置
        
        Args:
            position_seconds: 播放位置（秒）
        """
        try:
            if not self.lyrics_service.has_lyrics():
                return
            
            self.current_position = position_seconds
            
            # 获取当前歌词行
            current_line = self.lyrics_service.get_current_lyric_line(position_seconds)
            
            # 更新歌词行的高亮状态
            self.update_lyrics_highlight(current_line)
            
            # 如果启用自动滚动，滚动到当前行
            if self.auto_scroll and current_line:
                self.scroll_to_current_line(current_line)
                
        except Exception as e:
            logger.error(f"更新歌词位置失败: {e}")
    
    def update_lyrics_highlight(self, current_line: Optional[LyricLine]):
        """
        更新歌词行的高亮状态
        
        Args:
            current_line: 当前歌词行
        """
        try:
            for label in self.lyrics_labels:
                if hasattr(label, 'lyric_line'):
                    if current_line and label.lyric_line.time_seconds == current_line.time_seconds:
                        # 高亮当前行
                        label.style.color = self.highlight_color
                        label.style.font_weight = "bold"
                        label.style.background_color = "#fff3cd"
                    else:
                        # 恢复普通样式
                        label.style.color = self.normal_color
                        label.style.font_weight = "normal"
                        label.style.background_color = "transparent"
                        
        except Exception as e:
            logger.error(f"更新歌词高亮失败: {e}")
    
    def scroll_to_current_line(self, current_line: LyricLine):
        """
        滚动到当前歌词行
        
        Args:
            current_line: 当前歌词行
        """
        try:
            # 找到对应的标签
            target_label = None
            for label in self.lyrics_labels:
                if hasattr(label, 'lyric_line') and label.lyric_line.time_seconds == current_line.time_seconds:
                    target_label = label
                    break
            
            if target_label:
                # 这里可以实现滚动到指定标签的逻辑
                # Toga的ScrollContainer目前可能不直接支持滚动到特定位置
                # 可以在未来的版本中实现
                logger.debug(f"滚动到歌词行: {current_line.text}")
                
        except Exception as e:
            logger.error(f"滚动到歌词行失败: {e}")
    
    def toggle_auto_scroll(self):
        """切换自动滚动"""
        self.auto_scroll = not self.auto_scroll
        logger.info(f"自动滚动: {'开启' if self.auto_scroll else '关闭'}")
    
    def set_font_size(self, size: int):
        """
        设置字体大小
        
        Args:
            size: 字体大小
        """
        try:
            self.font_size = max(8, min(20, size))  # 限制字体大小范围
            
            # 更新所有歌词标签的字体大小
            for label in self.lyrics_labels:
                label.style.font_size = self.font_size
            
            logger.info(f"歌词字体大小设置为: {self.font_size}")
            
        except Exception as e:
            logger.error(f"设置字体大小失败: {e}")
    
    def show_lyrics_settings(self, widget):
        """显示歌词设置（暂时未实现）"""
        logger.info("歌词设置功能暂未实现")
    
    async def download_lyrics_manually(self, widget):
        """手动下载歌词按钮回调"""
        try:
            if not self.current_song_name:
                logger.warning("没有当前歌曲，无法下载歌词")
                return
            
            # 更新按钮状态
            original_text = widget.text
            widget.text = "⏳"
            widget.enabled = False
            
            # 显示下载状态
            self.show_download_status("正在下载歌词...")
            
            # 获取歌曲的远程路径信息
            song_remote_path = None
            if hasattr(self.app, 'music_library') and self.app.music_library:
                song_info = self.app.music_library.get_song_info(self.current_song_name)
                if song_info:
                    song_remote_path = song_info.get('remote_path')
            
            # 尝试下载歌词
            success = await self.lyrics_service.download_lyrics(self.current_song_name, song_remote_path)
            
            if success:
                # 下载成功，重新加载歌词
                self.load_lyrics_for_song(self.current_song_name, auto_download=False)
                self.show_download_status("歌词下载成功！")
                logger.info(f"手动下载歌词成功: {self.current_song_name}")
                
                # 3秒后隐藏状态
                await asyncio.sleep(3)
                self.hide_download_status()
            else:
                self.show_download_status("歌词下载失败，可能不存在对应的歌词文件")
                logger.warning(f"手动下载歌词失败: {self.current_song_name}")
                
                # 3秒后隐藏状态
                await asyncio.sleep(3)
                self.hide_download_status()
            
        except Exception as e:
            logger.error(f"手动下载歌词失败: {e}")
            self.show_download_status(f"下载失败: {str(e)}")
            await asyncio.sleep(3)
            self.hide_download_status()
        finally:
            # 恢复按钮状态
            widget.text = original_text
            widget.enabled = True
    
    def show_download_status(self, message: str):
        """显示下载状态信息"""
        try:
            # 创建或更新状态标签
            if not hasattr(self, 'download_status_label'):
                self.download_status_label = toga.Label(
                    message,
                    style=Pack(
                        text_align="center",
                        padding=5,
                        color="#007bff",
                        font_size=10,
                        background_color="#e7f3ff"
                    )
                )
                # 插入到歌词显示区域的顶部
                if len(self.lyrics_box.children) > 0:
                    self.lyrics_box.insert(0, self.download_status_label)
                else:
                    self.lyrics_box.add(self.download_status_label)
            else:
                self.download_status_label.text = message
                self.download_status_label.style.visibility = "visible"
                
        except Exception as e:
            logger.error(f"显示下载状态失败: {e}")
    
    def hide_download_status(self):
        """隐藏下载状态信息"""
        try:
            if hasattr(self, 'download_status_label'):
                self.download_status_label.style.visibility = "hidden"
        except Exception as e:
            logger.error(f"隐藏下载状态失败: {e}")
    
    def set_visibility(self, visible: bool):
        """
        设置歌词显示的可见性
        
        Args:
            visible: 是否可见
        """
        try:
            self.is_visible = visible
            self.container.style.visibility = "visible" if visible else "hidden"
            logger.debug(f"歌词显示可见性: {visible}")
        except Exception as e:
            logger.error(f"设置歌词可见性失败: {e}")
    
    def refresh_display(self):
        """刷新歌词显示"""
        try:
            if self.current_song_name:
                self.load_lyrics_for_song(self.current_song_name)
                # 如果有当前播放位置，更新显示
                if self.current_position > 0:
                    self.update_lyrics_position(self.current_position)
        except Exception as e:
            logger.error(f"刷新歌词显示失败: {e}")
    
    def get_service(self) -> LyricsService:
        """获取歌词服务实例"""
        return self.lyrics_service
