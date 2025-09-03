"""
文件列表视图 - 显示和管理NextCloud音乐文件
基于 music_list.json 的增删查改操作
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from ..services.music_service import MusicService
import threading

logger = logging.getLogger(__name__)

class FileListView:
    """文件列表管理视图"""
    
    def __init__(self, music_service: MusicService, view_manager):
        self.music_service = music_service
        self.view_manager = view_manager
        self.music_files = []
        self.selected_files = set()
        self.is_syncing = False
        
        # 设置服务回调
        self.music_service.set_playlist_change_callback(self._on_playlist_changed)
        self.music_service.set_sync_folder_change_callback(self._on_sync_folder_changed)
        
        # 创建滚动视图容器以适配iOS设备
        self.container = toga.ScrollContainer(
            content=toga.Box(style=Pack(direction=COLUMN, padding=10)),
            style=Pack(flex=1)
        )
        
        # 构建界面
        self.build_interface()
        logger.info("文件列表视图初始化完成")
        
        # 从 music_list.json 加载音乐列表
        self.reload_music_list()
        # 软件启动时异步更新下载状态 - 使用线程调用同步版本
        threading.Timer(0.5, self.update_download_status_sync).start()
        
    def _on_playlist_changed(self, playlist: List[str], start_index: int):
        """播放列表变化回调"""
        # 可以在这里处理播放列表变化的UI更新
        logger.info(f"播放列表已更新: {len(playlist)} 首歌曲")
    
    def _on_sync_folder_changed(self, sync_folder: str):
        """同步文件夹变化回调"""
        # 可以在这里处理同步文件夹变化的UI更新
        logger.info(f"同步文件夹已更新: {sync_folder}")
        
        # 从 music_list.json 加载音乐列表
        self.reload_music_list()
    
    def build_interface(self):
        """构建文件列表界面 - iOS优化版本"""
        # 获取滚动容器的内容
        content_box = self.container.content
        
        # 标题 - 减小字体和填充
        title = toga.Label(
            "📁 音乐文件列表",
            style=Pack(
                padding=(0, 0, 5, 0),
                font_size=16,
                font_weight="bold",
                text_align="center",
                color="#212529"
            )
        )
        
        # 操作栏 - 减少填充
        action_bar = toga.Box(style=Pack(direction=ROW, padding=5))
        
        # 同步按钮 - 减小尺寸
        self.sync_button = toga.Button(
            "📥 同步",
            on_press=self.sync_music_list,
            style=Pack(
                padding=3,
                background_color="#34C759",
                color="white",
                font_size=11,
                width=60,
                height=30
            )
        )
        
        # 文件夹输入 - 减小字体
        self.folder_input = toga.TextInput(
            placeholder="指定同步文件夹路径 (可选)",
            style=Pack(flex=1, padding=(0, 3, 0, 3), font_size=11)
        )
        
        # 搜索输入框 - 减小字体
        self.search_input = toga.TextInput(
            placeholder="搜索歌曲、艺术家或专辑...",
            style=Pack(flex=1, padding=(0, 3, 0, 3), font_size=11)
        )
        
        # 搜索按钮 - 减小尺寸
        self.search_button = toga.Button(
            "🔍",
            on_press=self.search_music,
            style=Pack(padding=3, width=30, height=30, font_size=10)
        )
        
        action_bar.add(self.sync_button)
        action_bar.add(self.folder_input)
        action_bar.add(self.search_input)
        action_bar.add(self.search_button)
        
        # 播放控制栏 - 减小填充和按钮
        playback_bar = toga.Box(style=Pack(direction=ROW, padding=5))
        
        # 合并操作按钮
        self.add_to_playlist_button = toga.Button(
            "🎵 添加",
            on_press=self.add_to_playlist,
            style=Pack(
                padding=3,
                background_color="#007bff",
                color="white",
                font_size=10,
                width=60,
                height=25
            )
        )
        
        self.play_selected_button = toga.Button(
            "▶️ 播放",
            on_press=self.play_selected_files,
            style=Pack(
                padding=3,
                background_color="#28a745",
                color="white",
                font_size=10,
                width=60,
                height=25
            )
        )
        
        self.select_all_button = toga.Button(
            "☑️ 全选",
            on_press=self.select_all_files,
            style=Pack(padding=3, font_size=10, width=60, height=25)
        )
        
        self.delete_selected_button = toga.Button(
            "🗑️ 删除",
            on_press=self.delete_selected_files,
            style=Pack(
                padding=3,
                background_color="#dc3545",
                color="white",
                font_size=10,
                width=60,
                height=25
            )
        )
        
        playback_bar.add(self.add_to_playlist_button)
        playback_bar.add(self.play_selected_button)
        playback_bar.add(self.select_all_button)
        playback_bar.add(self.delete_selected_button)
        
        # 统计信息 - 减小填充
        self.stats_box = toga.Box(style=Pack(
            direction=ROW,
            padding=5,
            background_color="#f0f0f0"
        ))
        
        self.stats_label = toga.Label(
            "总文件: 0 | 已选择: 0 | 已下载: 0",
            style=Pack(
                flex=1,
                color="#495057",
                font_size=10
            )
        )
        
        self.stats_box.add(self.stats_label)
        
        # 文件列表 - 减小高度
        self.music_list = toga.DetailedList(
            data=[],
            style=Pack(flex=1, height=200),
            on_select=self.on_file_select
        )
        
        # 下载控制栏 - 简化
        download_bar = toga.Box(style=Pack(direction=ROW, padding=5))
        
        self.download_selected_button = toga.Button(
            "⬇️ 下载",
            on_press=self.download_selected_files,
            enabled=False,
            style=Pack(
                padding=3,
                background_color="#007AFF",
                color="white",
                font_size=10,
                width=60,
                height=25
            )
        )
        
        self.clear_cache_button = toga.Button(
            "🗑️ 清缓存",
            on_press=self.clear_cache,
            style=Pack(padding=3, font_size=10, width=70, height=25)
        )
        
        download_bar.add(self.download_selected_button)
        download_bar.add(self.clear_cache_button)
        
        # 下载状态显示 - 减小填充
        self.download_status_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=5,
            background_color="#f9f9f9"
        ))
        
        # 消息显示区域 - 减小填充
        self.message_box = toga.Box(style=Pack(
            direction=COLUMN,
            padding=5
        ))
        
        # 组装界面 - 使用滚动容器的内容
        content_box.add(title)
        content_box.add(action_bar)
        content_box.add(playback_bar)
        content_box.add(self.stats_box)
        content_box.add(self.music_list)
        content_box.add(download_bar)
        content_box.add(self.download_status_box)
        content_box.add(self.message_box)
    
    def reload_music_list(self, music_files: Optional[List[Dict]] = None):
        """从 music_list.json 重新加载音乐列表"""
        # 从音乐服务获取所有歌曲信息
        if music_files is None:
            music_files = self.music_service.get_all_songs()

        self.music_files = music_files
        # 更新音乐文件到列表
        self.music_list.data.clear()
        for file_info in self.music_files:
            # 检查文件是否已下载
            is_downloaded = file_info.get('is_downloaded', False)
            download_status = "✅" if is_downloaded else "⬇️"
            
            # 检查文件是否被选中
            file_title = file_info.get('display_name', file_info['name'])
            is_selected = file_info['title'] in self.selected_files
            selection_status = "☑️" if is_selected else "☐"
            
            # 格式化显示信息，包含选择状态
            title = f"{selection_status} {file_title}"
            subtitle = f"{download_status} 大小: {self.format_file_size(file_info.get('size', 0))}"
            
            # 不使用图标以避免加载错误
            self.music_list.data.append({
                'title': title,
                'subtitle': subtitle,
                'file_info': file_info
            })

        self.update_stats()

    async def sync_music_list(self, widget):
        """同步音乐列表"""
        if self.is_syncing:
            self.show_message("正在同步中，请稍候...", "info")
            return
        
        try:
            self.is_syncing = True
            self.sync_button.enabled = False
            self.sync_button.text = "📥 同步中..."
            
            # 获取同步文件夹路径
            sync_folder = self.folder_input.value.strip()
            
            logger.info(f"开始同步音乐文件，文件夹路径: '{sync_folder}'")
            self.show_message(f"正在同步文件夹: {sync_folder or '根目录'}", "info")
            
            # 通过服务同步音乐文件
            self.music_files = await self.music_service.sync_music_files(sync_folder)
            
            logger.info(f"同步结果: 找到 {len(self.music_files) if self.music_files else 0} 个音乐文件")
            self.show_message(f"同步完成，共 {len(self.music_files) if self.music_files else 0} 个音乐文件", "success")
            
            self.reload_music_list()
        except Exception as e:
            logger.error(f"同步失败: {e}")
            self.show_message(f"同步失败: {str(e)}", "error")
        finally:
            self.is_syncing = False
            self.sync_button.enabled = True
            self.sync_button.text = "📥 同步音乐列表"
            
    def check_file_downloaded(self, filename: str) -> bool:
        """检查文件是否已下载"""
        try:
            return self.music_service.is_file_cached(filename)
        except Exception:
            return False
    
    def format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小显示"""
        if size_bytes == 0:
            return "未知"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def on_file_select(self, widget):
        """文件选择事件"""
        if widget.selection:
            selected_item = widget.selection
            file_info = selected_item.file_info
            logger.info(f"选中文件信息: {file_info}")
            # 切换选择状态
            file_path = file_info['title']
            if file_path in self.selected_files:
                self.selected_files.remove(file_path)
            else:
                self.selected_files.add(file_path)
            
            # 刷新列表显示以更新选择状态
            self.reload_music_list()
            self.update_button_states()
    
    def add_to_playlist(self, widget):
        """将选中文件添加到播放列表"""
        try:
            if not self.selected_files:
                self.show_message("请先选择要添加的文件", "warning")
                return
            
            # 获取选中的文件信息
            selected_music_files = []
            for file_info in self.music_files:
                if file_info['title'] in self.selected_files:
                    selected_music_files.append(file_info)
            
            # 获取播放界面并调用添加方法
            playback_view = self.view_manager.get_view("playback")
            if playback_view:
                playback_view.handle_play_selected(selected_music_files, start_index=0)
                # 切换到播放界面
                self.view_manager.switch_to_view("playback")
                self.show_message(f"已添加 {len(selected_music_files)} 首歌曲到播放列表", "success")

        except Exception as e:
            logger.error(f"添加到播放列表失败: {e}")
            self.show_message(f"添加失败: {str(e)}", "error")
    
    def delete_selected_files(self, widget):
        """删除选中的文件 (删操作)"""
        try:
            if not self.selected_files:
                self.show_message("请先选择要删除的文件", "warning")
                return
            
            # 获取选中的文件信息
            selected_file_names = []
            for file_info in self.music_files:
                if file_info['title'] in self.selected_files:
                    selected_file_names.append(file_info['name'])
            
            if not selected_file_names:
                self.show_message("没有找到有效的选中文件", "error")
                return
            
            # 从音乐服务中删除选中的歌曲 (删操作)
            deleted_count = 0
            for song_name in selected_file_names:
                if self.music_service.has_song(song_name):
                    self.music_service.remove_song(song_name)
                    deleted_count += 1
            
            # 清空选择
            self.selected_files.clear()
            
            # 从 music_list.json 重新加载列表 (查操作)
            self.reload_music_list()
            
            self.show_message(f"已删除 {deleted_count} 首歌曲", "success")
            logger.info(f"删除歌曲并更新 music_list.json: {deleted_count} 首")
            
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            self.show_message(f"删除失败: {str(e)}", "error")
    
    async def edit_selected_file(self, widget):
        """编辑选中文件的信息 (改操作)"""
        try:
            if len(self.selected_files) != 1:
                self.show_message("请选择一个文件进行编辑", "warning")
                return
            
            # 获取选中的文件信息
            selected_path = list(self.selected_files)[0]
            file_info = None
            for info in self.music_files:
                if info['title'] == selected_path:
                    file_info = info
                    break
            
            if not file_info:
                self.show_message("找不到选中的文件信息", "error")
                return
            
            # 获取当前的歌曲信息
            song_name = file_info['name']
            current_info = self.music_service.get_song_info(song_name)
            
            # 创建编辑对话框
            await self.show_edit_dialog(song_name, current_info)
            
        except Exception as e:
            logger.error(f"编辑文件信息失败: {e}")
            self.show_message(f"编辑失败: {str(e)}", "error")
    
    async def show_edit_dialog(self, song_name: str, current_info: dict):
        """显示编辑对话框"""
        try:
            # 创建编辑界面
            edit_box = toga.Box(style=Pack(direction=COLUMN, padding=20))
            
            # 标题输入
            title_label = toga.Label("歌曲标题:", style=Pack(padding=(0, 0, 5, 0)))
            title_input = toga.TextInput(
                value=current_info.get('title', ''),
                style=Pack(width=300, padding=(0, 0, 10, 0))
            )
            
            # 艺术家输入
            artist_label = toga.Label("艺术家:", style=Pack(padding=(0, 0, 5, 0)))
            artist_input = toga.TextInput(
                value=current_info.get('artist', ''),
                style=Pack(width=300, padding=(0, 0, 10, 0))
            )
            
            # 专辑输入
            album_label = toga.Label("专辑:", style=Pack(padding=(0, 0, 5, 0)))
            album_input = toga.TextInput(
                value=current_info.get('album', ''),
                style=Pack(width=300, padding=(0, 0, 10, 0))
            )
            
            # 添加到编辑框
            edit_box.add(title_label)
            edit_box.add(title_input)
            edit_box.add(artist_label)
            edit_box.add(artist_input)
            edit_box.add(album_label)
            edit_box.add(album_input)
            
            # 简化的保存操作（在实际应用中应该有正确的对话框）
            # 这里直接更新信息作为演示
            new_title = title_input.value.strip() or current_info.get('title', song_name)
            new_artist = artist_input.value.strip() or current_info.get('artist', '未知艺术家')
            new_album = album_input.value.strip() or current_info.get('album', '未知专辑')
            
            # 更新歌曲信息 (改操作)
            updated_info = current_info.copy()
            updated_info.update({
                'title': new_title,
                'artist': new_artist,
                'album': new_album
            })
            
            # 保存到音乐服务
            self.music_service.update_song_info(song_name, updated_info)
            
            # 从 music_list.json 重新加载列表 (查操作)
            self.reload_music_list()
            
            self.show_message(f"已更新歌曲信息: {song_name}", "success")
            logger.info(f"更新歌曲信息并保存到 music_list.json: {song_name}")
            
        except Exception as e:
            logger.error(f"保存编辑信息失败: {e}")
            self.show_message(f"保存失败: {str(e)}", "error")
    
    def search_music(self, widget):
        """搜索音乐 (查操作)"""
        try:
            search_query = self.search_input.value.strip()
            if not search_query:
                # 如果搜索框为空，显示所有歌曲
                self.reload_music_list()
                self.show_message("显示所有歌曲", "info")
                return
            
            # 从音乐服务搜索 (查操作)
            search_results = self.music_service.search_songs(search_query)
            
            self.reload_music_list(search_results)
            self.show_message(f"找到 {len(search_results)} 个匹配结果", "success")
            logger.info(f"搜索 '{search_query}' 找到 {len(search_results)} 个结果")
                
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            self.show_message(f"搜索失败: {str(e)}", "error")
    
    def play_selected_files(self, widget):
        """播放选中的文件"""
        try:
            if not self.selected_files:
                self.show_message("请先选择要播放的文件", "warning")
                return
            
            # 获取选中的文件信息
            selected_music_files = []
            for file_info in self.music_files:
                if file_info['title'] in self.selected_files:
                    selected_music_files.append(file_info)
            
            if not selected_music_files:
                self.show_message("没有找到选中的文件信息", "error")
                return
            
            # 获取播放界面并调用播放方法
            playback_view = self.view_manager.get_view("playback")
            if playback_view:
                playback_view.handle_play_selected(selected_music_files, start_index=0)
                # 切换到播放界面
                self.view_manager.switch_to_view("playback")
                self.show_message(f"新实现开始播放 {len(selected_music_files)} 首歌曲", "success")

            logger.info(f"播放选中文件: {len(selected_music_files)} 首")
            
        except Exception as e:
            logger.error(f"播放选中文件失败: {e}")
            self.show_message(f"播放失败: {str(e)}", "error")
    
    def select_all_files(self, widget):
        """全选/取消全选文件"""
        if len(self.selected_files) == len(self.music_files):
            # 取消全选
            self.selected_files.clear()
            self.select_all_button.text = "☑️ 全选"
        else:
            # 全选
            self.selected_files = {file_info['title'] for file_info in self.music_files}
            self.select_all_button.text = "☐ 取消全选"
        
        # 刷新列表显示以更新选择状态
        self.reload_music_list()
        self.update_button_states()
    
    def update_button_states(self):
        """更新按钮状态"""
        has_selection = len(self.selected_files) > 0
        
        self.download_selected_button.enabled = has_selection
        self.play_selected_button.enabled = has_selection
        self.delete_selected_button.enabled = has_selection
    
    def update_stats(self):
        """更新统计信息"""
        total_files = len(self.music_files)
        selected_files = len(self.selected_files)
        downloaded_files = sum(1 for file_info in self.music_files 
                             if file_info.get('is_downloaded', False))
        
        self.stats_label.text = f"总文件: {total_files} | 已选择: {selected_files} | 已下载: {downloaded_files}"
    
    async def download_selected_files(self, widget):
        """下载选中的文件"""
        if not self.selected_files:
            self.show_message("请先选择要下载的文件", "error")
            return
        
        if not self.music_service.has_nextcloud_client():
            self.show_message("NextCloud连接已断开", "error")
            return
        
        try:
            # 获取选中的文件信息
            selected_file_infos = [
                file_info for file_info in self.music_files
                if file_info['title'] in self.selected_files
            ]
            
            self.show_message(f"开始下载 {len(selected_file_infos)} 个文件...", "info")
            
            # 启动下载任务
            await self.download_files(selected_file_infos)
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self.show_message(f"下载失败: {str(e)}", "error")
    
    async def download_files(self, file_infos: List[Dict]):
        """下载文件列表"""
        downloaded_count = 0
        failed_count = 0
        
        for i, file_info in enumerate(file_infos):
            try:
                filename = file_info['name']
                file_path = file_info['remote_path']
                
                # 更新下载状态path
                self.show_download_progress(f"正在下载: {filename} ({i+1}/{len(file_infos)})")
                logger.info(f"开始下载: {filename}")
                # 下载文件
                success = await self.music_service.download_file(file_path, filename)
                
                if success:
                    downloaded_count += 1
                    logger.info(f"下载成功: {filename}")
                else:
                    failed_count += 1
                    logger.error(f"下载失败: {filename}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"下载文件 {file_info['name']} 失败: {e}")
        
        # 下载完成，从 music_list.json 重新加载显示 (查操作)
        self.reload_music_list()
        
        if failed_count == 0:
            self.show_message(f"所有文件下载完成！成功: {downloaded_count}", "success")
        else:
            self.show_message(f"下载完成！成功: {downloaded_count}, 失败: {failed_count}", "info")
        
        # 清空下载状态显示
        self.download_status_box.clear()
    
    def show_download_progress(self, message: str):
        """显示下载进度"""
        self.download_status_box.clear()
        
        progress_label = toga.Label(
            message,
            style=Pack(
                padding=5,
                background_color="#d1ecf1",
                text_align="center"
            )
        )
        
        self.download_status_box.add(progress_label)
    
    
    async def clear_cache(self, widget):
        """清除缓存 (删操作)"""
        try:
            # 清除音乐服务缓存 (删操作)
            self.music_service.clear_cache()
            
            # 清空当前列表
            self.music_files.clear()
            self.selected_files.clear()
            self.music_list.data.clear()
            self.update_stats()
            
            self.show_message("缓存已清除，music_list.json 已删除", "success")
            logger.info("清除缓存并删除 music_list.json")
            
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            self.show_message(f"清除缓存失败: {str(e)}", "error")
    
    def show_message(self, message: str, message_type: str = "info"):
        """显示消息"""
        # 清空之前的消息
        self.message_box.clear()
        
        # 根据消息类型设置样式
        if message_type == "success":
            bg_color = "#d4edda"
            text_color = "#155724"
            icon = "✅"
        elif message_type == "error":
            bg_color = "#f8d7da"
            text_color = "#721c24"
            icon = "❌"
        else:  # info
            bg_color = "#d1ecf1"
            text_color = "#0c5460"
            icon = "ℹ️"
        
        message_label = toga.Label(
            f"{icon} {message}",
            style=Pack(
                padding=10,
                background_color=bg_color,
                color=text_color,
                text_align="center"
            )
        )
        
        self.message_box.add(message_label)
        logger.info(f"[{message_type.upper()}] {message}")
    
    def on_view_activated(self):
        """当视图被激活时调用 (查操作)"""
        # 从 music_list.json 刷新显示状态
        self.reload_music_list()
        
        # 从连接视图加载文件夹路径
        # 获取连接配置信息
        connection_config = self.music_service.get_connection_config()
        default_folder = connection_config.get("default_sync_folder", "")
        if default_folder and not self.folder_input.value:
            self.folder_input.value = default_folder
            
    async def update_download_status(self):
        """异步更新下载状态"""
        # 更新下载状态
        for file_info in self.music_files:
            file_info['is_downloaded'] = self.check_file_downloaded(file_info['name'])
            await asyncio.sleep(0.1)
    
    def update_download_status_sync(self):
        """同步更新下载状态（用于线程调用）"""
        logger.info("开始同步更新下载状态")
        try:
            # 更新下载状态
            for file_info in self.music_files:
                file_info['is_downloaded'] = self.check_file_downloaded(file_info['name'])
                logger.debug(f"检查文件 {file_info['name']} 下载状态: {file_info['is_downloaded']}")
            logger.info(f"完成下载状态检查，共 {len(self.music_files)} 个文件")
        except Exception as e:
            logger.error(f"更新下载状态失败: {e}")