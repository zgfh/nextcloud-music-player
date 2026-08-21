"""
UI 主题系统 - 集中管理颜色、间距、字号常量
所有视图文件应从此模块导入样式常量，避免硬编码
"""


class Color:
    """统一颜色系统 - 柔和现代色调"""

    # === 主操作色 ===
    PRIMARY = "#2E6BE6"           # 柔和蓝（替代刺眼的 #007AFF）
    PRIMARY_LIGHT = "#E8F0FE"     # 主色浅色背景
    PRIMARY_PRESSED = "#1E54C7"  # 按下态深蓝
    PRIMARY_TEXT = "#FFFFFF"      # 主色上的文字

    # === 语义色 ===
    SUCCESS = "#2EA043"          # 成功/播放中
    SUCCESS_LIGHT = "#DAF1DE"    # 成功消息背景
    SUCCESS_TEXT = "#1A5E2A"     # 成功消息文字

    DANGER = "#D5393B"           # 危险/停止
    DANGER_LIGHT = "#F9E0E0"     # 错误消息背景
    DANGER_TEXT = "#7A1C1E"      # 错误消息文字

    WARNING = "#D7900B"          # 警告/暂停
    WARNING_LIGHT = "#FFF4D6"    # 警告消息背景
    WARNING_TEXT = "#6B5400"     # 警告消息文字

    INFO = "#3A8FBE"             # 信息/浏览
    INFO_LIGHT = "#D9EDF6"       # 信息消息背景
    INFO_TEXT = "#0B4A6B"        # 信息消息文字
    INFO_STATUS = "#E7F2FC"      # 下载状态等浅信息背景

    # === 中性色 - 背景层次 ===
    BG_APP = "#F4F4F8"          # 应用/导航栏背景
    BG_SURFACE = "#FFFFFF"       # 卡片/播放列表
    BG_SURFACE_ALT = "#F8F8FB"  # 次级面板（now-playing、次要按钮）
    BG_SUBTLE = "#EEEEF2"       # 分隔/统计栏

    # === 中性色 - 文字层次 ===
    TEXT_PRIMARY = "#1A1A2E"    # 标题、主要文字
    TEXT_SECONDARY = "#5A5A6E"  # 标签、次要文字
    TEXT_MUTED = "#8A8A9E"      # 时间标签、静默信息
    TEXT_DISABLED = "#B0B0BE"   # 占位符、禁用文字

    # === 播放状态色 ===
    STATUS_PLAYING = "#2EA043"
    STATUS_PAUSED = "#D7900B"
    STATUS_STOPPED = "#8A8A9E"

    # === 播放模式按钮 ===
    MODE_ACTIVE_BG = "#2EA043"
    MODE_ACTIVE_TEXT = "#FFFFFF"
    MODE_INACTIVE_BG = "#F8F8FB"
    MODE_INACTIVE_TEXT = "#5A5A6E"

    # === 导航/Tab 状态 ===
    NAV_ACTIVE_BG = "#2E6BE6"
    NAV_ACTIVE_TEXT = "#FFFFFF"
    NAV_INACTIVE_BG = "#F4F4F8"
    NAV_INACTIVE_TEXT = "#5A5A6E"

    # === 歌词 ===
    LYRICS_HIGHLIGHT = "#2E6BE6"
    LYRICS_HIGHLIGHT_BG = "#FFF4D6"
    LYRICS_NORMAL = "#8A8A9E"
    LYRICS_BG = "#F8F8FB"


class Space:
    """4 点网格间距系统"""

    NONE = 0
    XS = 4    # 紧密元素间（标签到输入框）
    SM = 8    # 表单字段间
    MD = 12   # 区域间
    LG = 16   # 主要区域/视图内边距
    XL = 24   # 大间距
    XXL = 32  # iOS 安全区域


class FontSize:
    """统一字号系统"""

    TITLE = 16      # 视图标题
    SUBTITLE = 14   # 歌曲名、歌词标题
    BODY = 12       # 正文、导航按钮、表单
    STATUS = 13     # 播放状态标签
    CAPTION = 11    # 开关、播放列表信息
    MICRO = 10      # 小图标按钮（密码切换、搜索）


def get_message_style(message_type: str):
    """
    返回消息类型的样式元组

    Returns:
        tuple: (background_color, text_color, icon)
    """
    styles = {
        "success": (Color.SUCCESS_LIGHT, Color.SUCCESS_TEXT, "✅"),
        "error": (Color.DANGER_LIGHT, Color.DANGER_TEXT, "❌"),
        "warning": (Color.WARNING_LIGHT, Color.WARNING_TEXT, "⚠️"),
        "info": (Color.INFO_LIGHT, Color.INFO_TEXT, "ℹ️"),
    }
    return styles.get(message_type, styles["info"])
