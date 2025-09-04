# lyrics_component.py\n\n歌词显示组件 - 负责在UI中显示歌词
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
                message = f"歌词加载失败\n\n