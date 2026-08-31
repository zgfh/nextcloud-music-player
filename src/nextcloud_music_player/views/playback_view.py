"""
播放视图 - Flet 版本
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import flet as ft

from ..services.playback_controller import PlaybackController, PlayMode
from ..services.playback_service import PlaybackService
from ..services.playlist_manager import PlaylistManager
from ..utils.notify import show_snack_bar
from ..utils.theme import (
    Color,
    FontSize,
    Radius,
    Space,
    glow,
    glow_soft,
    tint,
)
from .components.lyrics_component import LyricsDisplayComponent
from .components.playback_control_component import PlaybackControlComponent
from .components.playlist_component import PlaylistViewComponent

logger = logging.getLogger(__name__)


class PlaybackView:
    """播放视图"""

    def __init__(self, page: ft.Page, app_context: dict, view_manager):
        self.page = page
        self.app_context = app_context
        self.view_manager = view_manager
        self.play_mode = PlayMode.REPEAT_ONE

        config_manager = app_context["config_manager"]
        music_service = app_context.get("music_service")

        # 初始化播放服务
        self.playback_service = PlaybackService(
            config_manager=config_manager,
            music_service=music_service,
            play_music_callback=None,
            add_background_task_callback=lambda task: (
                asyncio.create_task(task)
                if asyncio.iscoroutine(task)
                else asyncio.create_task(task())
            ),
            page=page,
        )

        # 播放列表管理器
        self.playlist_manager = PlaylistManager(
            config_manager=config_manager, music_service=music_service
        )

        # 播放控制器
        self.playback_controller = PlaybackController(
            playback_service=self.playback_service,
            playlist_manager=self.playlist_manager,
            play_song_callback=self.play_selected_song,
            ui_update_callback=self.on_playback_state_changed,
        )

        # 播放控制组件
        self.playback_control_component = PlaybackControlComponent(
            page=page,
            app_context=app_context,
            playback_controller=self.playback_controller,
            on_play_mode_change_callback=self.on_play_mode_changed,
        )

        # 播放列表组件
        self.playlist_component = PlaylistViewComponent(
            page=page,
            app_context=app_context,
            playlist_manager=self.playlist_manager,
            on_song_select_callback=self.on_playlist_song_selected,
            on_playlist_change_callback=self.on_playlist_changed,
            playback_service=self.playback_service,
        )

        # 歌词组件
        lyrics_service = app_context.get("lyrics_service")
        self.lyrics_component = LyricsDisplayComponent(
            page=page,
            app_context=app_context,
            config_manager=config_manager,
            lyrics_service=lyrics_service,
        )

        # 播放列表回调
        self.playback_service.set_playback_callbacks(
            pause_callback=None,
            stop_callback=None,
            get_play_mode_callback=None,
            get_is_playing_callback=None,
            set_volume_callback=lambda v: None,
            seek_to_position_callback=None,
            get_duration_callback=None,
            set_play_mode_callback=None,
        )

        configured_mode = config_manager.get("player.play_mode", "repeat_one")
        configured_enum = {
            "normal": PlayMode.NORMAL,
            "repeat_one": PlayMode.REPEAT_ONE,
            "repeat_all": PlayMode.REPEAT_ALL,
            "shuffle": PlayMode.SHUFFLE,
        }.get(configured_mode, PlayMode.REPEAT_ONE)
        self.play_mode = configured_enum
        self.playback_controller.set_play_mode(configured_enum)
        self.playback_service.set_play_mode(configured_enum)

        # 状态
        self.current_song_info = None
        self._song_completed = False
        self._last_position = 0
        self._switching_song = False
        self._built = False
        self._view_active = False
        self._ui_task = None
        # 播放请求序号：每次新的播放请求自增，仍在进行的旧请求（下载/播放）完成后发现
        # 序号已过期即丢弃，避免慢网络下旧下载完成把用户最新选择的歌曲顶掉
        self._play_request_seq = 0

    def rebuild(self):
        """重建视图（Flet 0.86 控件脱离页面后被冻结且不可复用，切回时必须重建）"""
        self._cancel_ui_timer()
        self._built = False
        for component in (
            self.playback_control_component,
            self.playlist_component,
            self.lyrics_component,
        ):
            if hasattr(component, "_built"):
                component._built = False
        # 旧的歌词行控件也已冻结，清空避免后台继续更新它们
        if hasattr(self.lyrics_component, "_lyric_items"):
            self.lyrics_component._lyric_items = []
        return self.build()

    def on_view_deactivated(self):
        """视图切出：停止 UI 定时刷新，避免更新已冻结控件"""
        self._view_active = False
        self._cancel_ui_timer()

    def _cancel_ui_timer(self):
        if self._ui_task and not self._ui_task.done():
            self._ui_task.cancel()
        self._ui_task = None

    @staticmethod
    def _is_destroyed_session_error(error: Exception) -> bool:
        """判断 Flet 客户端是否已经销毁当前会话。"""
        return "destroyed session" in str(error).lower()

    def build(self):
        """构建并返回视图"""
        if self._built and hasattr(self, "_container"):
            return self._container

        # === 正在播放卡：渐变 + 霓虹描边 ===
        self.album_art = ft.Container(
            content=ft.Icon(ft.Icons.GRAPHIC_EQ, color=Color.PRIMARY, size=28),
            width=52,
            height=52,
            border_radius=Radius.LG,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=["#0E2434", "#1A1030"],
            ),
            border=ft.Border.all(1, tint(Color.PRIMARY, "40")),
            shadow=glow(Color.PRIMARY, radius=14, alpha="26"),
        )
        self.song_title_label = ft.Text(
            "未选择歌曲",
            size=FontSize.SUBTITLE + 2,
            weight=ft.FontWeight.BOLD,
            color=Color.TEXT_PRIMARY,
            # 不能加 expand：Column 中的 expand 是竖向 flex，
            # 处于外层 Column 的无限高滚动内容中会触发
            # "non-zero flex but unbounded constraints" 渲染异常
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.status_label = ft.Text(
            "停止",
            size=FontSize.MICRO,
            color=Color.STATUS_STOPPED,
            weight=ft.FontWeight.BOLD,
            style=ft.TextStyle(letter_spacing=1),
        )
        self.status_chip = ft.Container(
            content=self.status_label,
            bgcolor=tint(Color.STATUS_STOPPED, "1F"),
            border=ft.Border.all(1, tint(Color.STATUS_STOPPED, "40")),
            padding=ft.Padding(left=10, right=10, top=4, bottom=4),
            border_radius=Radius.CIRCLE,
        )
        now_playing = ft.Container(
            content=ft.Row(
                [
                    self.album_art,
                    ft.Column(
                        [
                            self.song_title_label,
                            ft.Text(
                                "NOW PLAYING",
                                size=FontSize.MICRO,
                                color=Color.TEXT_MUTED,
                                style=ft.TextStyle(letter_spacing=3),
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    self.status_chip,
                ],
                spacing=Space.MD,
            ),
            bgcolor=Color.BG_SURFACE,
            border=ft.Border.all(1, Color.BORDER),
            border_radius=Radius.LG,
            padding=Space.MD,
            shadow=glow_soft(Color.ACCENT),
        )

        # Tab 切换 - SegmentedButton + Visibility（不使用 Tabs/TabBarView：
        # PageView 在 flutter test 视口下给子页 unbounded 高度，触发
        # "non-zero flex but unbounded constraints" 渲染异常）
        playlist_view = self.playlist_component.build()
        lyrics_view = self.lyrics_component.build()

        self.tab_selector = ft.SegmentedButton(
            selected=["playlist"],
            segments=[
                ft.Segment(
                    value="playlist", label="播放列表", icon=ft.Icons.QUEUE_MUSIC
                ),
                ft.Segment(value="lyrics", label="歌词", icon=ft.Icons.LYRICS_OUTLINED),
            ],
            allow_multiple_selection=False,
            allow_empty_selection=False,
            on_change=self._on_tab_change,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.SELECTED: tint(Color.PRIMARY, "26"),
                    ft.ControlState.DEFAULT: Color.BG_SURFACE_ALT,
                },
                color={
                    ft.ControlState.SELECTED: Color.PRIMARY,
                    ft.ControlState.DEFAULT: Color.TEXT_SECONDARY,
                },
                side=ft.BorderSide(1, Color.BORDER),
                shape=ft.RoundedRectangleBorder(radius=Radius.MD),
            ),
        )

        self.playlist_panel = ft.Container(content=playlist_view, expand=True)
        self.lyrics_panel = ft.Container(
            content=lyrics_view, expand=True, visible=False
        )

        # 播放控制
        controls = self.playback_control_component.build()

        # 组装（顶部/底部安全区由 ViewManager 的全局 SafeArea 统一处理）
        self._container = ft.Container(
            content=ft.Column(
                [
                    now_playing,
                    self.tab_selector,
                    self.playlist_panel,
                    self.lyrics_panel,
                    controls,
                ],
                spacing=Space.SM,
                expand=True,
            ),
            padding=Space.LG,
            expand=True,
            bgcolor=Color.BG_APP,
        )

        self._built = True
        self._view_active = True

        # 初始化模式按钮
        self.playback_control_component.update_mode_buttons()

        # 启动 UI 定时器（在 build 完成后启动；旧的先取消）
        # flet test 环境跳过：周期 page.update 会让 Dart 侧 testWidgets
        # 在结束时留下未完成的帧而被判失败（FLET_TEST_* 由 flet test 注入
        # 并透传至 embedded Python）
        self._cancel_ui_timer()
        if not (
            os.environ.get("FLET_TEST_DEVICE_MODE")
            or os.environ.get("FLET_TEST_PLATFORM")
        ):
            self._ui_task = asyncio.create_task(self._schedule_ui_update())

        return self._container

    def _on_tab_change(self, e):
        """Tab 切换（SegmentedButton 控制两个面板的可见性）"""
        try:
            selected = self.tab_selector.selected
            current = next(iter(selected), "playlist")
        except Exception:
            current = "playlist"
        self.playlist_panel.visible = current == "playlist"
        self.lyrics_panel.visible = current == "lyrics"
        self.page.update()

    def _set_status(self, text: str, color: str):
        """更新播放状态胶囊（文字 + 霓虹 tint）"""
        self.status_label.value = text
        self.status_label.color = color
        self.status_chip.bgcolor = tint(color, "1F")
        self.status_chip.border = ft.Border.all(1, tint(color, "40"))
        self.album_art.border = ft.Border.all(1, tint(color, "59"))
        self.album_art.shadow = (
            glow(color, radius=14, alpha="33") if text != "停止" else None
        )

    async def on_playlist_song_selected(self, song_entry: Dict[str, Any], index: int):
        """播放列表歌曲选择回调"""
        try:
            song_info = song_entry.get("info", {})
            song_name = song_entry.get("name", "")
            self.current_song_info = song_info
            self._update_current_song_info()

            if self.lyrics_component and song_name:
                self.lyrics_component.load_lyrics_for_song(song_name)

            auto_play = self.app_context["config_manager"].get(
                "player.auto_play_on_select", True
            )
            if auto_play:
                # 用刷新后的歌曲信息（下载状态/本地路径可能是加入列表后更新的）
                await self.play_selected_song(self.current_song_info or song_info)
        except Exception as e:
            logger.error(f"处理播放列表歌曲选择失败: {e}")

    def on_playlist_changed(self, change_type: str):
        """播放列表改变回调"""
        logger.info(f"播放列表发生改变: {change_type}")
        if change_type == "cleared":
            asyncio.create_task(self._stop_music())

    def on_play_mode_changed(self, mode: str):
        """播放模式改变回调"""
        mode_map = {
            "normal": PlayMode.NORMAL,
            "repeat_one": PlayMode.REPEAT_ONE,
            "repeat_all": PlayMode.REPEAT_ALL,
            "shuffle": PlayMode.SHUFFLE,
        }
        self.play_mode = mode_map.get(mode, PlayMode.REPEAT_ONE)
        self.playback_service.set_play_mode_by_string(mode)

    def on_playback_state_changed(self, is_playing: bool, is_stopped: bool = False):
        """播放状态改变回调"""
        if self.playback_control_component:
            self.playback_control_component.update_play_pause_button(is_playing)
        if is_stopped:
            self._song_completed = False
            if self.playback_control_component:
                self.playback_control_component.reset_progress()
            self._set_status("停止", Color.STATUS_STOPPED)
        elif is_playing:
            self._set_status("播放中", Color.STATUS_PLAYING)
        else:
            self._set_status("暂停", Color.STATUS_PAUSED)
        self.page.update()

    async def play_selected_song(self, song_info: Dict[str, Any]) -> bool:
        """播放选中的歌曲。

        每次调用都视为一次新的播放请求：先停掉旧歌并给出"切换中"反馈
        （未下载的歌曲在慢网络下要等很久，不能没有任何提示），
        请求序号用于让更早的、仍在下载的旧请求在完成后被丢弃。
        """
        request_id = self._play_request_seq + 1
        self._play_request_seq = request_id

        def superseded() -> bool:
            return request_id != self._play_request_seq

        try:
            if (
                self.playback_service.is_playing()
                or self.playback_service.current_song_state.get("is_paused")
            ):
                await self.playback_service.stop_music()
            self._set_status("切换中...", Color.INFO)
            self.page.update()

            song_name = song_info.get("name", "")
            music_service = self.app_context.get("music_service")

            # 先按真实文件检查本地缓存；不要只依赖可能过期的元数据标记。
            local_path = (
                music_service.get_local_file_path(song_name)
                if music_service and song_name
                else ""
            )
            if local_path and os.path.exists(local_path):
                return await self.play_music_file(local_path, request_id=request_id)

            remote_path = song_info.get("remote_path", "")
            if not (music_service and remote_path):
                self._set_status("无法播放", Color.DANGER_TEXT)
                self.page.update()
                return False

            self._set_status("下载中...", Color.INFO)
            self.page.update()
            try:
                success = await music_service.download_file(remote_path, song_name)
            except Exception as dl_error:
                logger.error(f"下载歌曲失败: {song_name} - {dl_error}")
                success = False

            if superseded():
                logger.info(f"播放请求已过期，丢弃下载结果: {song_name}")
                return False
            if not success:
                self._set_status("下载失败", Color.DANGER_TEXT)
                self.page.update()
                return False

            music_library = self.app_context.get("music_library")
            updated_info = (
                music_library.get_song_info(song_name) if music_library else None
            )
            if updated_info and updated_info.get("filepath"):
                return await self.play_music_file(
                    updated_info["filepath"], request_id=request_id
                )

            self._set_status("播放失败", Color.DANGER_TEXT)
            self.page.update()
            return False
        except Exception as e:
            logger.error(f"播放选中歌曲失败: {e}")
            return False

    async def play_music_file(
        self, file_path: str, request_id: Optional[int] = None
    ) -> bool:
        """播放音乐文件（request_id 过期时放弃播放）"""
        try:
            if request_id is not None and request_id != self._play_request_seq:
                logger.info(f"播放请求已过期，放弃播放: {file_path}")
                return False

            self.playback_service.set_current_song(file_path)
            try:
                played = await asyncio.wait_for(
                    self.playback_service.play_music(), timeout=15.0
                )
            except asyncio.TimeoutError:
                logger.error("播放音乐超时")
                self._set_status("播放失败", Color.DANGER_TEXT)
                self.page.update()
                return False

            if not played:
                self._set_status("播放失败", Color.DANGER_TEXT)
                self.page.update()
                return False

            if self.lyrics_component:
                song_name = os.path.basename(file_path)
                self.lyrics_component.load_lyrics_for_song(
                    song_name, auto_download=True
                )

            self._set_status("播放中", Color.STATUS_PLAYING)
            self.update_ui()
            return True
        except Exception as e:
            logger.error(f"播放音乐文件失败: {e}")
            return False

    async def _stop_music(self):
        """停止播放"""
        await self.playback_service.stop_music()
        self._set_status("停止", Color.STATUS_STOPPED)
        self.page.update()

    async def _schedule_ui_update(self):
        """定时更新 UI（仅在视图激活时刷新，避免更新已冻结控件）"""
        from ..platform_audio import is_ios

        update_interval = 2.0 if is_ios() else 0.5

        while True:
            await asyncio.sleep(update_interval)
            if not self._view_active or not self._built:
                continue
            if getattr(self.view_manager, "app_backgrounded", False):
                # 应用在后台：Flet websocket 可能已被系统冻结，
                # page.update 会阻塞事件循环并拖慢下载协程
                continue
            try:
                self._update_progress_only()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if self._is_destroyed_session_error(e):
                    # 客户端关闭或热重载会直接销毁 Flet session，不一定触发
                    # 视图切出回调；此时结束永久刷新任务，避免持续访问失效页面。
                    self._view_active = False
                    logger.info("Flet会话已销毁，停止播放页UI刷新")
                    break
                logger.error(f"UI更新失败: {e}")

    def _update_progress_only(self):
        """只更新播放进度"""
        if not self._built:
            return
        try:
            if self.playback_control_component:
                self.playback_control_component.update_progress()

            position = (
                self.playback_control_component.get_current_position()
                if self.playback_control_component
                else 0
            )
            duration = (
                self.playback_control_component.get_current_duration()
                if self.playback_control_component
                else 0
            )

            if self.lyrics_component:
                self.lyrics_component.update_lyrics_position(position)

            # 优先使用播放器的自然结束事件。部分原生后端结束时会立即把
            # position 归零，旧的“进度接近 100%”判断会因此漏掉续播。
            completed = self.playback_service.has_completed()
            if completed and not self._song_completed:
                self._song_completed = True
                asyncio.create_task(self._auto_play_next_song())
            elif duration > 0 and position > 0:
                progress_ratio = position / duration
                from ..platform_audio import is_ios

                threshold = 0.98 if is_ios() else 0.99

                if progress_ratio >= threshold and not self._song_completed:
                    self._song_completed = True
                    asyncio.create_task(self._auto_play_next_song())
                elif progress_ratio < 0.95 and self._song_completed:
                    self._song_completed = False

            # 更新状态
            is_playing = self.playback_service.is_playing()
            is_paused = getattr(self.playback_service, "current_song_state", {}).get(
                "is_paused", False
            )

            if is_playing:
                self._set_status("播放中", Color.STATUS_PLAYING)
                self.playback_control_component.update_play_pause_button(True)
            elif is_paused:
                self._set_status("暂停", Color.STATUS_PAUSED)
                self.playback_control_component.update_play_pause_button(False)
            else:
                self._set_status("停止", Color.STATUS_STOPPED)
                self.playback_control_component.update_play_pause_button(False)
        except Exception as e:
            if self._is_destroyed_session_error(e):
                # 交给定时任务终止循环，不把正常的会话关闭误报为播放故障。
                raise
            logger.error(f"更新播放进度失败: {e}")

    async def _auto_play_next_song(self):
        """自动播放下一曲"""
        if self._switching_song:
            return
        await asyncio.sleep(0.2)
        self._switching_song = True
        try:
            success = await self.playback_controller.auto_play_next_song()
            if success:
                self._song_completed = False
                if self.playlist_component:
                    self.playlist_component.refresh_display()
                self.update_ui()
        finally:
            self._switching_song = False

    def update_ui(self):
        """更新 UI 显示"""
        try:
            self._update_current_song_info()
            current_song = self._get_current_song_entry()

            if current_song and self.current_song_info:
                song_info = self.current_song_info
                display_title = song_info.get(
                    "title", song_info.get("name", "未知歌曲")
                )
                if display_title.endswith(".mp3"):
                    display_title = display_title[:-4]
                artist = song_info.get("artist", "未知艺术家")
                if artist and artist != "未知艺术家":
                    new_title = f"{display_title} - {artist}"
                else:
                    new_title = display_title

                if self.song_title_label.value != new_title:
                    self.song_title_label.value = new_title
            else:
                self.song_title_label.value = "未选择歌曲"

            self.page.update()
        except Exception as e:
            logger.error(f"更新UI失败: {e}")

    def _update_current_song_info(self):
        """更新当前歌曲信息"""
        try:
            current_song = self.playlist_component.get_current_song_info()
            if not current_song:
                self.current_song_info = None
                return
            song_info = current_song.get("info", {})
            music_library = self.app_context.get("music_library")
            if music_library:
                song_name = current_song.get("name") or song_info.get("name")
                if song_name:
                    detailed = music_library.get_song_info(song_name)
                    if detailed:
                        self.current_song_info = {**song_info, **detailed}
                    else:
                        self.current_song_info = song_info
            else:
                self.current_song_info = song_info
        except Exception as e:
            logger.error(f"更新当前歌曲信息失败: {e}")

    def _get_current_song_entry(self) -> Optional[Dict[str, Any]]:
        """获取当前播放歌曲条目"""
        try:
            playlist = self.playlist_manager.get_current_playlist()
            if not playlist or not playlist.get("songs"):
                return None
            current_index = playlist.get("current_index", 0)
            songs = playlist["songs"]
            if 0 <= current_index < len(songs):
                return songs[current_index]
            return None
        except:
            return None

    def show_message(self, message: str, message_type: str = "info"):
        """在页面顶部显示消息。"""
        show_snack_bar(self.page, message, message_type)

    def handle_play_selected(
        self, music_files: List[Dict[str, Any]], start_index: int = 0
    ):
        """处理从文件列表播放选中歌曲"""
        logger.info(
            f"处理播放选中歌曲请求，文件数: {len(music_files)}, 开始索引: {start_index}"
        )
        try:
            if music_files:
                self.playlist_manager.clear_current_playlist()
                added = self.playlist_component.add_songs_to_playlist_batch(music_files)
                logger.info(f"批量添加 {added} 首歌曲")

                current_playlist = self.playlist_manager.get_current_playlist()
                if current_playlist and 0 <= start_index < len(music_files):
                    current_playlist["current_index"] = start_index
                    self.playlist_manager.save_current_playlist(current_playlist)

                auto_play = self.app_context["config_manager"].get(
                    "player.auto_play_on_select", True
                )
                if auto_play and music_files:
                    target = (
                        music_files[start_index]
                        if start_index < len(music_files)
                        else music_files[0]
                    )
                    asyncio.create_task(self._play_or_skip_unavailable(target))
        except Exception as e:
            logger.error(f"处理播放选中歌曲请求失败: {e}")

    async def _play_or_skip_unavailable(self, target: Dict[str, Any]):
        """播放选中歌曲；来源连接或下载失败时继续下一首。"""
        if await self.play_selected_song(target):
            return True
        logger.warning("歌曲不可用，自动跳过: %s", target.get("name", ""))
        return await self.playback_controller.next_song()

    def on_view_activated(self):
        """视图激活"""
        if self.playlist_component:
            self.playlist_component.refresh_display()
        self.update_ui()
