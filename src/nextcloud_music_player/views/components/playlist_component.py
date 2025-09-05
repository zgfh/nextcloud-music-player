"""
播放列表视图组件 - 专门处理播放列表界面显示和交互
从播放视图中分离出来，提供独立的播放列表管理界面
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import logging
from typing import Optional, Dict, List, Any, Callable

logger = logging.getLogger(__name__)

class PlaylistViewComponent:
    """播放列表视图组件 - 负责播放列表的界面显示和用户交互"""
    
    def __init__(self, app, playlist_manager, on_song_select_callback=None, on_playlist_change_callback=None, playback_service=None):
        """
        初始化播放列表视图组件
        
        Args:
            app: 应用实例
            playlist_manager: 播放列表管理器
            on_song_select_callback: 选择歌曲时的回调函数
            on_playlist_change_callback: 播放列表改变时的回调函数
            playback_service: 播放服务实例，用于获取播放状态
        """
        self.app = app
        self.playlist_manager = playlist_manager
        self.on_song_select_callback = on_song_select_callback
        self.on_playlist_change_callback = on_playlist_change_callback
        self.playback_service = playback_service
        
        # UI组件
        self.playlist_box = None
        self.playlist_info_label = None
        self.playlist_table = None
        self.playlist_controls_box = None
        
        # 创建UI
        self.create_ui()
        
        # 初始加载播放列表
        self.refresh_display()
    
    def create_ui(self):
        """创建播放列表UI"""
        # 主容器
        self.playlist_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=3,
            background_color="#ffffff",
            flex=1
        ))
        
        # 播放列表头部 - 信息和控制按钮在同一行
        self.create_playlist_header()
        
        # 播放列表表格
        self.playlist_table = toga.DetailedList(
            data=[],
            on_select=self.on_song_selected,
            style=Pack(
                flex=1,
                padding=(2, 0)
            )
        )
        
        # 组装UI
        self.playlist_box.add(self.playlist_header_box)
        self.playlist_box.add(self.playlist_table)
    
    def create_playlist_header(self):
        """创建播放列表头部 - 信息标签和控制按钮在同一行"""
        self.playlist_header_box = toga.Box(style=Pack(
            direction=ROW,  # 改为水平布局，让信息标签和控制按钮在同一行
            padding=2,
            alignment="center"
        ))
        
        # 播放列表信息标签 - 占据左侧剩余空间
        self.playlist_info_label = toga.Label(
            "正在加载播放列表...",
            style=Pack(
                font_size=11,
                padding=(2, 5, 2, 0),  # 右侧留出一些空间
                color="#666666",
                text_align="left",  # 左对齐
                flex=1  # 占据剩余空间
            )
        )
        
        # 控制按钮容器
        self.playlist_controls_box = toga.Box(style=Pack(
            direction=ROW,
            padding=(2, 0),
            alignment="center"
        ))
        
        # 创建紧凑的控制按钮 - 手机操作优化
        clear_button = toga.Button(
            "🗑️",
            on_press=self.clear_playlist,
            style=Pack(
                width=40,
                height=32,
                padding=(0, 3),
                font_size=12
            )
        )
        
        remove_button = toga.Button(
            "❌",
            on_press=self.remove_selected_song,
            style=Pack(
                width=40,
                height=32,
                padding=(0, 3),
                font_size=12
            )
        )
        
        refresh_button = toga.Button(
            "🔄",
            on_press=self.refresh_display_action,
            style=Pack(
                width=40,
                height=32,
                padding=(0, 3),
                font_size=12
            )
        )
        
        manage_button = toga.Button(
            "📋",
            on_press=self.show_playlist_manager,
            style=Pack(
                width=40,
                height=32,
                padding=(0, 3),
                font_size=12
            )
        )
        
        # 添加按钮到控制按钮容器
        self.playlist_controls_box.add(clear_button)
        self.playlist_controls_box.add(remove_button)
        self.playlist_controls_box.add(refresh_button)
        self.playlist_controls_box.add(manage_button)
        
        # 组装头部 - 信息标签在左，控制按钮在右
        self.playlist_header_box.add(self.playlist_info_label)
        self.playlist_header_box.add(self.playlist_controls_box)
    
        
    def refresh_display(self):
        """刷新播放列表显示"""
        try:
            # 确保有当前播放列表
            current_playlist = self.playlist_manager.create_default_playlist_if_needed()
            
            # 更新播放列表信息
            self.update_playlist_info(current_playlist)
            
            # 更新播放列表内容
            self.update_playlist_content(current_playlist)
            
        except Exception as e:
            logger.error(f"刷新播放列表显示失败: {e}")
            self.show_error_message("刷新播放列表失败")
    
    def update_playlist_info(self, playlist_data: Dict[str, Any]):
        """更新播放列表信息标签"""
        try:
            stats = self.playlist_manager.get_playlist_stats()
            
            info_text = f"📋 {stats['playlist_name']} ({stats['current_index']}/{stats['total_songs']})"
            
            if stats['folder_path']:
                info_text += f" | 📁 {stats['folder_path']}"
            
            self.playlist_info_label.text = info_text
            
        except Exception as e:
            logger.error(f"更新播放列表信息失败: {e}")
            self.playlist_info_label.text = "播放列表信息加载失败"
    
    def update_playlist_content(self, playlist_data: Dict[str, Any]):
        """更新播放列表内容表格"""
        try:
            # 清空现有数据
            self.playlist_table.data.clear()
            
            songs = playlist_data.get('songs', [])
            current_index = playlist_data.get('current_index', 0)
            
            if not songs:
                # 显示空列表提示
                self.playlist_table.data.append({
                    'icon': "📝",
                    'title': "播放列表为空",
                    'subtitle': "请从文件列表添加音乐或导入播放列表"
                })
                return
            
            # 添加歌曲到表格
            for i, song_entry in enumerate(songs):
                self.add_song_to_table(song_entry, i, current_index)
                
        except Exception as e:
            logger.error(f"更新播放列表内容失败: {e}")
    
    def add_song_to_table(self, song_entry: Dict[str, Any], index: int, current_index: int):
        """添加单首歌曲到表格"""
        try:
            song_info = song_entry.get("info", {})
            song_state = song_entry.get("state", {})
            
            # 获取歌曲显示名称
            title = song_info.get('title', song_info.get('display_name', song_entry.get('name', '未知歌曲')))
            if title.endswith('.mp3'):
                title = title[:-4]
            
            # 获取艺术家信息
            artist = song_info.get('artist', '未知艺术家')
            
            # 确定图标和状态
            if index == current_index:
                # 检查播放状态 - 使用 playback_service 获取真实状态
                if self.playback_service:
                    is_playing = self.playback_service.is_playing()
                    is_paused = getattr(self.playback_service, 'current_song_state', {}).get('is_paused', False)
                    
                    if is_playing:
                        icon = "播放中 🔊"
                        status = "播放中"
                    elif is_paused:
                        icon = "暂停 ⏸"
                        status = "暂停"
                    else:
                        icon = "待播放 ●"
                        status = "待播放"
                else:
                    # 如果没有 playback_service，回退到 app 属性检查
                    if getattr(self.app, 'is_playing', False):
                        icon = "播放中 🔊"
                        status = "播放中"
                    elif getattr(self.app, 'is_paused', False):
                        icon = "暂停 ⏸"
                        status = "暂停"
                    else:
                        icon = "待播放 ●"
                        status = "待播放"
            else:
                icon = "🎶"
                status = ""
            
            # 检查下载状态
            is_downloaded = song_info.get('is_downloaded', False)
            download_icon = "📁" if is_downloaded else "☁️"
            
            # 播放统计
            play_count = song_state.get('play_count', 0)
            is_favorite = song_state.get('is_favorite', False)
            
            # 构建副标题
            subtitle_parts = [download_icon]
            
            if status:
                subtitle_parts.append(status)
            
            if artist and artist != '未知艺术家':
                subtitle_parts.append(f"🎤 {artist}")
            
            if play_count > 0:
                subtitle_parts.append(f"🔄 {play_count}次")
            
            if is_favorite:
                subtitle_parts.append("❤️")
            
            subtitle = " | ".join(subtitle_parts)
            
            # 添加到表格
            self.playlist_table.data.append({
                'icon': icon,
                'title': title,
                'subtitle': subtitle
            })
            
        except Exception as e:
            logger.error(f"添加歌曲到表格失败: {e}")
    
    def on_song_selected(self, widget):
        """处理歌曲选择事件"""
        try:
            if not widget.selection:
                return
            
            selected_index = self.get_selected_index()
            if selected_index < 0:
                return
            
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist:
                return
            
            songs = current_playlist.get('songs', [])
            if selected_index >= len(songs):
                return
            
            # 如果选择的是空列表提示，则返回
            if not songs:
                return
            
            # 更新当前播放索引
            current_playlist['current_index'] = selected_index
            self.playlist_manager.save_current_playlist(current_playlist)
            
            # 调用选择回调
            if self.on_song_select_callback:
                selected_song = songs[selected_index]
                self.on_song_select_callback(selected_song, selected_index)
            
            # 只更新播放状态指示器，不刷新整个列表以保持选择状态
            self.update_playing_indicator(selected_index)
            
        except Exception as e:
            logger.error(f"处理歌曲选择失败: {e}")
    
    def get_selected_index(self) -> int:
        """获取当前选中的索引"""
        try:
            if not self.playlist_table.selection:
                return -1
            
            # 获取选中项在数据中的索引
            selected_item = self.playlist_table.selection
            for i, item in enumerate(self.playlist_table.data):
                if item == selected_item:
                    return i
            
            return -1
            
        except Exception as e:
            logger.error(f"获取选中索引失败: {e}")
            return -1
    
    def clear_playlist(self, widget):
        """清空播放列表"""
        try:
            success = self.playlist_manager.clear_current_playlist()
            if success:
                self.refresh_display()
                if self.on_playlist_change_callback:
                    self.on_playlist_change_callback("cleared")
                self.show_success_message("播放列表已清空")
            else:
                self.show_error_message("清空播放列表失败")
        except Exception as e:
            logger.error(f"清空播放列表失败: {e}")
            self.show_error_message("清空播放列表失败")
    
    def remove_selected_song(self, widget):
        """移除选中的歌曲"""
        try:
            selected_index = self.get_selected_index()
            if selected_index < 0:
                self.show_error_message("请先选择要移除的歌曲")
                return
            
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist or not current_playlist.get('songs'):
                self.show_error_message("播放列表为空")
                return
            
            songs = current_playlist.get('songs', [])
            if selected_index >= len(songs):
                self.show_error_message("选择的歌曲索引无效")
                return
            
            success = self.playlist_manager.remove_song_from_current_playlist(selected_index)
            if success:
                self.refresh_display()
                if self.on_playlist_change_callback:
                    self.on_playlist_change_callback("song_removed")
                self.show_success_message("歌曲已移除")
            else:
                self.show_error_message("移除歌曲失败")
                
        except Exception as e:
            logger.error(f"移除歌曲失败: {e}")
            self.show_error_message("移除歌曲失败")
    
    def refresh_display_action(self, widget):
        """刷新显示按钮响应"""
        self.playlist_manager.invalidate_cache()
        self.refresh_display()
        self.show_success_message("播放列表已刷新")
    
    def show_playlist_manager(self, widget):
        """显示播放列表管理界面"""
        # 这里可以扩展为显示播放列表管理窗口
        # 目前简单地刷新显示
        self.refresh_display()
        self.show_info_message("播放列表管理功能开发中...")
    
    def add_song_to_playlist(self, song_info: Dict[str, Any]) -> bool:
        """添加歌曲到播放列表"""
        try:
            success = self.playlist_manager.add_song_to_current_playlist(song_info)
            if success:
                self.refresh_display()
                if self.on_playlist_change_callback:
                    self.on_playlist_change_callback("song_added")
                return True
            return False
        except Exception as e:
            logger.error(f"添加歌曲到播放列表失败: {e}")
            return False

    def add_songs_to_playlist_batch(self, song_infos: List[Dict[str, Any]]) -> int:
        """批量添加歌曲到播放列表，返回实际添加的歌曲数量"""
        try:
            added_count = self.playlist_manager.add_songs_to_current_playlist_batch(song_infos)
            if added_count > 0:
                # 只刷新一次显示
                self.refresh_display()
                if self.on_playlist_change_callback:
                    self.on_playlist_change_callback("songs_added_batch")
                logger.info(f"批量添加完成，共添加 {added_count} 首歌曲")
            return added_count
        except Exception as e:
            logger.error(f"批量添加歌曲到播放列表失败: {e}")
            return 0
    
    def create_playlist_from_folder(self, folder_path: str, name: str = None) -> bool:
        """从文件夹创建播放列表"""
        try:
            playlist = self.playlist_manager.create_playlist_from_folder(folder_path, name)
            if playlist:
                self.refresh_display()
                if self.on_playlist_change_callback:
                    self.on_playlist_change_callback("playlist_created")
                return True
            return False
        except Exception as e:
            logger.error(f"从文件夹创建播放列表失败: {e}")
            return False
    
    def get_widget(self) -> toga.Widget:
        """获取主要的UI组件"""
        return self.playlist_box
    
    def show_success_message(self, message: str):
        """显示成功消息"""
        try:
            # 可以在这里实现消息显示逻辑
            # 简单地记录日志
            logger.info(f"[SUCCESS] {message}")
        except Exception as e:
            logger.error(f"显示成功消息失败: {e}")
    
    def show_error_message(self, message: str):
        """显示错误消息"""
        try:
            # 可以在这里实现错误消息显示逻辑
            # 简单地记录日志
            logger.error(f"[ERROR] {message}")
        except Exception as e:
            logger.error(f"显示错误消息失败: {e}")
    
    def show_info_message(self, message: str):
        """显示信息消息"""
        try:
            # 可以在这里实现信息消息显示逻辑
            # 简单地记录日志
            logger.info(f"[INFO] {message}")
        except Exception as e:
            logger.error(f"显示信息消息失败: {e}")
    
    def update_playing_indicator(self, current_index: int):
        """更新播放状态指示器，不重新构建整个列表"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist:
                return
            
            songs = current_playlist.get('songs', [])
            if not songs or current_index >= len(songs):
                return
            
            # 更新表格中每个项目的图标，只更新必要的部分
            for i, data_item in enumerate(self.playlist_table.data):
                if i >= len(songs):
                    continue
                    
                song_entry = songs[i]
                song_info = song_entry.get("info", {})
                
                # 确定新的图标
                if i == current_index:
                    # 检查播放状态 - 使用 playback_service 获取真实状态
                    if self.playback_service:
                        is_playing = self.playback_service.is_playing()
                        is_paused = getattr(self.playback_service, 'current_song_state', {}).get('is_paused', False)
                        
                        if is_playing:
                            new_icon = "播放中 🔊"
                            status = "播放中"
                        elif is_paused:
                            new_icon = "暂停 ⏸"
                            status = "暂停"
                        else:
                            new_icon = "待播放 ●"
                            status = "待播放"
                    else:
                        # 如果没有 playback_service，回退到 app 属性检查
                        if getattr(self.app, 'is_playing', False):
                            new_icon = "播放中 🔊"
                            status = "播放中"
                        elif getattr(self.app, 'is_paused', False):
                            new_icon = "暂停 ⏸"
                            status = "暂停"
                        else:
                            new_icon = "待播放 ●"
                            status = "待播放"
                else:
                    new_icon = "🎶"
                    status = ""
                
                # 更新图标 - 检查data_item是否为字典
                if hasattr(data_item, 'icon'):
                    # 如果是Row对象，直接设置属性
                    if data_item.icon != new_icon:
                        data_item.icon = new_icon
                        
                        # 更新副标题中的状态信息
                        subtitle_parts = data_item.subtitle.split(" | ")
                        
                        # 移除旧的状态信息
                        subtitle_parts = [part for part in subtitle_parts if part not in ["播放中", "暂停", "待播放"]]
                        
                        # 添加新的状态信息
                        if status:
                            subtitle_parts.insert(1, status)  # 在下载状态后插入
                        
                        data_item.subtitle = " | ".join(subtitle_parts)
                elif isinstance(data_item, dict):
                    # 如果是字典，按字典方式访问
                    if data_item.get('icon') != new_icon:
                        data_item['icon'] = new_icon
                        
                        # 更新副标题中的状态信息
                        subtitle_parts = data_item['subtitle'].split(" | ")
                        
                        # 移除旧的状态信息
                        subtitle_parts = [part for part in subtitle_parts if part not in ["播放中", "暂停", "待播放"]]
                        
                        # 添加新的状态信息
                        if status:
                            subtitle_parts.insert(1, status)  # 在下载状态后插入
                        
                        data_item['subtitle'] = " | ".join(subtitle_parts)
            
            logger.debug(f"更新播放指示器完成，当前索引: {current_index}")
            
        except Exception as e:
            logger.error(f"更新播放指示器失败: {e}")

    def update_current_song_indicator(self, song_index: int):
        """更新当前播放歌曲的指示器"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if current_playlist:
                current_playlist['current_index'] = song_index
                self.playlist_manager.save_current_playlist(current_playlist)
                # 使用新的更新方法而不是刷新整个列表
                self.update_playing_indicator(song_index)
        except Exception as e:
            logger.error(f"更新当前歌曲指示器失败: {e}")
    
    def get_current_song_info(self) -> Optional[Dict[str, Any]]:
        """获取当前播放的歌曲信息"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist:
                logger.debug("get_current_song_info: 没有当前播放列表")
                return None
            
            songs = current_playlist.get('songs', [])
            current_index = current_playlist.get('current_index', 0)
            
            logger.debug(f"get_current_song_info: 播放列表有 {len(songs)} 首歌，当前索引: {current_index}")
            
            if 0 <= current_index < len(songs):
                song_info = songs[current_index]
                logger.debug(f"get_current_song_info: 返回当前歌曲: {song_info.get('name', 'Unknown')}")
                return song_info
            
            logger.debug("get_current_song_info: 索引超出范围")
            return None
            
        except Exception as e:
            logger.error(f"获取当前歌曲信息失败: {e}")
            return None
    
    def get_next_song_info(self) -> Optional[Dict[str, Any]]:
        """获取下一首歌曲信息"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist:
                return None
            
            songs = current_playlist.get('songs', [])
            current_index = current_playlist.get('current_index', 0)
            next_index = (current_index + 1) % len(songs) if songs else 0
            
            if 0 <= next_index < len(songs):
                return songs[next_index]
            
            return None
            
        except Exception as e:
            logger.error(f"获取下一首歌曲信息失败: {e}")
            return None
    
    def get_previous_song_info(self) -> Optional[Dict[str, Any]]:
        """获取上一首歌曲信息"""
        try:
            current_playlist = self.playlist_manager.get_current_playlist()
            if not current_playlist:
                return None
            
            songs = current_playlist.get('songs', [])
            current_index = current_playlist.get('current_index', 0)
            prev_index = (current_index - 1) % len(songs) if songs else 0
            
            if 0 <= prev_index < len(songs):
                return songs[prev_index]
            
            return None
            
        except Exception as e:
            logger.error(f"获取上一首歌曲信息失败: {e}")
            return None
    
    def update_display(self):
        """更新显示（与refresh_display相同，为了兼容性）"""
        self.refresh_display()
    
    @property
    def view(self):
        """返回主要的UI容器"""
        return self.playlist_box
