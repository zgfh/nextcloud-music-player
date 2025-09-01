"""
Views package for NextCloud Music Player
"""

from .connection_view import ConnectionView
from .file_list_view import FileListView  
from .playback_view import PlaybackView
from .view_manager import ViewManager

__all__ = ['ConnectionView', 'FileListView', 'PlaybackView', 'ViewManager']
