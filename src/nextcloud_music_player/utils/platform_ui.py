"""
平台相关的UI适配工具 (Flet 版本)
为不同平台提供合适的UI尺寸和样式
"""

import sys

from .theme import Space


def _is_mobile():
    """检测是否运行在移动平台"""
    return (
        sys.platform == "ios" or "iOS" in str(sys.platform) or sys.platform == "android"
    )


def get_button_height(primary=True, secondary=False):
    """获取按钮高度"""
    if _is_mobile():
        if primary:
            return 60
        elif secondary:
            return 55
        return 42
    else:
        if primary:
            return 45
        elif secondary:
            return 40
        return 32


def get_button_icon_size(primary=True, secondary=False, small=False):
    """获取按钮图标大小"""
    if _is_mobile():
        if primary:
            return 26
        elif secondary:
            return 22
        return 16
    else:
        if primary:
            return 20
        elif secondary:
            return 16
        return 12


def get_nav_bar_height():
    """获取导航栏高度"""
    return 70 if _is_mobile() else 56


def get_control_padding():
    """获取控制区域的padding值 (Flet 格式)"""
    if _is_mobile():
        return {
            "container": ft_padding(all=8),
            "controls": ft_padding(all=12),
            "volume_mode": ft_padding(vertical=4, horizontal=8),
            "progress": ft_padding(vertical=3, horizontal=6),
        }
    else:
        return {
            "container": ft_padding(all=8),
            "controls": ft_padding(all=8),
            "volume_mode": ft_padding(all=4),
            "progress": ft_padding(all=3),
        }


def get_font_sizes():
    """获取适合当前平台的字体大小"""
    if _is_mobile():
        return {
            "icon_primary": 26,
            "icon_secondary": 22,
            "icon_small": 16,
            "text_normal": 12,
            "text_small": 11,
        }
    else:
        return {
            "icon_primary": 20,
            "icon_secondary": 16,
            "icon_small": 12,
            "text_normal": 11,
            "text_small": 10,
        }


def ft_padding(
    all=None,
    vertical=None,
    horizontal=None,
    top=None,
    bottom=None,
    left=None,
    right=None,
):
    """生成 Flet padding 值

    返回一个整数或 ft.Padding 对象的参数字典。
    实际使用时在调用处用 ft.Padding(**result) 构造，或直接传数字。
    简化版：直接返回数值用于 padding=all 的情况。
    """
    if all is not None:
        return all
    # 返回一个可被 ft.Padding() 使用的字典
    result = {}
    if top is not None:
        result["top"] = top
    if bottom is not None:
        result["bottom"] = bottom
    if left is not None:
        result["left"] = left
    if right is not None:
        result["right"] = right
    if vertical is not None:
        result["top"] = vertical
        result["bottom"] = vertical
    if horizontal is not None:
        result["left"] = horizontal
        result["right"] = horizontal
    return result
