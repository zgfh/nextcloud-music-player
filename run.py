#!/usr/bin/env python3
"""
启动脚本 - Cloud Music Player (Flet)
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import flet as ft

from nextcloud_music_player.app import main

if __name__ == '__main__':
    ft.run(main)
