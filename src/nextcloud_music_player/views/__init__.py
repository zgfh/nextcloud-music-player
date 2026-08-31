"""
Views package for NextCloud Music Player
"""

from .connection_view import ConnectionView
from .file_list_view import FileListView
from .folder_selector import FolderSelector
from .playback_view import PlaybackView
from .settings_view import SettingsView
from .view_manager import ViewManager

__all__ = [
    "ConnectionView",
    "FileListView",
    "PlaybackView",
    "SettingsView",
    "ViewManager",
    "FolderSelector",
]
