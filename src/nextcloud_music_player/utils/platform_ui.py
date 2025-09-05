"""
平台相关的UI适配工具
为不同平台提供合适的UI间距和样式
"""

import platform

def get_safe_area_bottom_padding():
    """
    获取底部安全区域的padding值
    
    Returns:
        int: 底部安全区域的padding值（像素）
    """
    system = platform.system().lower()
    
    if system == "ios":
        # iOS设备需要更多底部间距，避免与底部手势冲突
        return 30
    elif system == "android":
        # Android设备也需要一些底部间距
        return 20
    else:
        # 桌面平台不需要特殊的底部间距
        return 10

def get_button_touch_size():
    """
    获取适合触摸操作的按钮尺寸
    
    Returns:
        dict: 包含width和height的字典
    """
    system = platform.system().lower()
    
    if system in ["ios", "android"]:
        # 移动设备需要更大的按钮尺寸
        return {
            "primary_width": 130,   # 主要按钮（播放/暂停）
            "primary_height": 60,
            "secondary_width": 110, # 次要按钮（上一曲/下一曲/停止）
            "secondary_height": 55,
            "small_width": 50,      # 小按钮（播放模式）
            "small_height": 42
        }
    else:
        # 桌面设备使用较小的按钮尺寸
        return {
            "primary_width": 100,
            "primary_height": 45,
            "secondary_width": 80,
            "secondary_height": 40,
            "small_width": 40,
            "small_height": 32
        }

def get_control_padding():
    """
    获取控制区域的padding值
    
    Returns:
        dict: 包含各种padding值的字典
    """
    system = platform.system().lower()
    
    if system in ["ios", "android"]:
        # 移动设备需要更多间距
        return {
            "container": (8, 8, 25, 8),    # 主容器padding (top, right, bottom, left)
            "controls": (8, 8, 15, 8),     # 控制按钮padding
            "volume_mode": (8, 4, 12, 4),  # 音量模式控制padding
            "progress": (6, 3, 8, 3),      # 进度条padding
            "button": (0, 6),              # 按钮间距
            "mode_button": (0, 3)          # 模式按钮间距
        }
    else:
        # 桌面设备使用较小间距
        return {
            "container": (8, 8, 8, 8),
            "controls": (8, 8, 8, 8),
            "volume_mode": (4, 4, 4, 4),
            "progress": (3, 3, 3, 3),
            "button": (0, 4),
            "mode_button": (0, 2)
        }

def get_font_sizes():
    """
    获取适合当前平台的字体大小
    
    Returns:
        dict: 包含各种字体大小的字典
    """
    system = platform.system().lower()
    
    if system in ["ios", "android"]:
        # 移动设备使用较大字体
        return {
            "icon_primary": 26,     # 主要图标（播放/暂停）
            "icon_secondary": 22,   # 次要图标（上一曲/下一曲等）
            "icon_small": 16,       # 小图标（播放模式）
            "text_normal": 12,      # 普通文本
            "text_small": 11        # 小文本
        }
    else:
        # 桌面设备使用标准字体大小
        return {
            "icon_primary": 20,
            "icon_secondary": 16,
            "icon_small": 12,
            "text_normal": 11,
            "text_small": 10
        }
