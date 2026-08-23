"""
UI 主题系统 - 「深空霓虹 AURORA」科技风设计语言
所有视图文件应从此模块导入样式常量，避免硬编码

设计要点：
- 深蓝黑背景营造空间纵深感
- 电光青 (#00E5FF) 主色 + 紫罗兰 (#7C4DFF) 渐变点缀
- 卡片用微弱描边 + 霓虹发光阴影（glow）代替传统投影
"""

import flet as ft


class Color:
    """统一颜色系统 - 深色科技风"""

    # === 主操作色（电光青 → 紫罗兰） ===
    PRIMARY = "#00E5FF"  # 电光青（霓虹主色）
    PRIMARY_DARK = "#00B8D4"  # 按下态
    PRIMARY_LIGHT = "#0E2A3A"  # 主色浅背景（半透明青 tint 基色）
    PRIMARY_TINT = "#1400E5FF"  # 8% 青 tint
    PRIMARY_PRESSED = "#00B8D4"
    PRIMARY_TEXT = "#06131A"  # 霓虹青上的深色文字（对比更科技）

    ACCENT = "#7C4DFF"  # 紫罗兰（渐变终点）

    # === 语义色（霓虹化） ===
    SUCCESS = "#00E676"  # 霓虹绿
    SUCCESS_LIGHT = "#0C2B1C"
    SUCCESS_TEXT = "#7DFFC1"

    DANGER = "#FF5370"  # 霓虹粉红
    DANGER_LIGHT = "#331520"
    DANGER_TEXT = "#FF9EB0"

    WARNING = "#FFC107"  # 琥珀
    WARNING_LIGHT = "#332910"
    WARNING_TEXT = "#FFD95E"

    INFO = "#5B8CFF"  # 星际蓝
    INFO_LIGHT = "#131F3D"
    INFO_TEXT = "#9DB9FF"
    INFO_STATUS = "#141C33"

    # === 中性色 - 背景层次（深空蓝黑） ===
    BG_APP = "#0A0E1A"  # 应用底色（近黑深蓝）
    BG_APP_ALT = "#0C1220"  # 次级底色
    BG_SURFACE = "#111828"  # 卡片/面板
    BG_SURFACE_ALT = "#0E1524"  # 次级面板（now-playing、输入框）
    BG_SUBTLE = "#182136"  # 分隔/统计栏
    BG_ELEVATED = "#1B2540"  # 悬浮层

    BORDER = "#223050"  # 卡片描边
    BORDER_STRONG = "#2E4270"  # 强调描边（选中态）

    # === 中性色 - 文字层次 ===
    TEXT_PRIMARY = "#EAF0FF"  # 标题、主要文字（冷白）
    TEXT_SECONDARY = "#94A0C0"  # 标签、次要文字
    TEXT_MUTED = "#5E6A8A"  # 时间标签、静默信息
    TEXT_DISABLED = "#3C4662"  # 占位符、禁用文字

    # === 播放状态色 ===
    STATUS_PLAYING = "#00E676"
    STATUS_PAUSED = "#FFC107"
    STATUS_STOPPED = "#5E6A8A"

    # === 播放模式按钮 ===
    MODE_ACTIVE_BG = "#100A2E5FF"  # 4% 青底由 tint 表达（见 tint() 辅助）
    MODE_ACTIVE_TEXT = "#00E5FF"
    MODE_INACTIVE_BG = None
    MODE_INACTIVE_TEXT = "#5E6A8A"

    # === 导航/Tab 状态 ===
    NAV_ACTIVE_BG = "#00E5FF"
    NAV_ACTIVE_TEXT = "#00E5FF"
    NAV_INACTIVE_BG = "#111828"
    NAV_INACTIVE_TEXT = "#5E6A8A"

    # === 歌词 ===
    LYRICS_HIGHLIGHT = "#00E5FF"
    LYRICS_HIGHLIGHT_BG = "#12202E"
    LYRICS_NORMAL = "#7A86A6"
    LYRICS_BG = "#0D1322"

    # === 音频可视化/装饰 ===
    GLOW_CYAN = "#00E5FF"
    GLOW_VIOLET = "#7C4DFF"


class Gradient:
    """渐变预设"""

    # 主渐变：电光青 → 星际蓝 → 紫罗兰
    PRIMARY = ["#00E5FF", "#5B8CFF", "#7C4DFF"]
    # 播放卡背景：深空微光
    SURFACE = ["#101A30", "#0C1322"]
    # 霓虹绿（播放中）
    SUCCESS = ["#00E676", "#00B8FF"]
    # 琥珀（暂停）
    WARNING = ["#FFC107", "#FF8A00"]

    @staticmethod
    def primary(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1)):
        return ft.LinearGradient(begin=begin, end=end, colors=Gradient.PRIMARY)

    @staticmethod
    def surface():
        return ft.LinearGradient(
            begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=Gradient.SURFACE
        )


def glow(color: str = Color.GLOW_CYAN, radius: float = 18, alpha: str = "66") -> list:
    """生成霓虹发光阴影（列表，可直接赋给 Container.shadow）"""
    hex_color = color.lstrip("#")
    return [
        ft.BoxShadow(
            blur_radius=radius,
            color=f"#{alpha}{hex_color}",
            offset=ft.Offset(0, 0),
        )
    ]


def glow_soft(color: str = Color.GLOW_CYAN) -> list:
    """柔和光晕（用于卡片）"""
    return glow(color, radius=24, alpha="2E")


class Space:
    """4 点网格间距系统"""

    NONE = 0
    XS = 4  # 紧密元素间（标签到输入框）
    SM = 8  # 表单字段间
    MD = 12  # 区域间
    LG = 16  # 主要区域/视图内边距
    XL = 24  # 大间距
    XXL = 32  # iOS 安全区域


class FontSize:
    """统一字号系统"""

    TITLE = 16  # 视图标题
    SUBTITLE = 14  # 歌曲名、歌词标题
    BODY = 12  # 正文、导航按钮、表单
    STATUS = 13  # 播放状态标签
    CAPTION = 11  # 开关、播放列表信息
    MICRO = 10  # 小图标按钮（密码切换、搜索）


# 圆角体系
class Radius:
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    CIRCLE = 999


def tint(hex_color: str, alpha: str = "1A") -> str:
    """为 6 位 HEX 颜色追加 alpha 通道，如 tint('#00E5FF', '26') -> '#2600E5FF'"""
    return f"#{alpha}{hex_color.lstrip('#')}"


def get_message_style(message_type: str):
    """
    返回消息类型的样式元组（深色霓虹版）

    Returns:
        tuple: (background_color, text_color, icon)
    """
    styles = {
        "success": (tint(Color.SUCCESS, "26"), Color.SUCCESS_TEXT, "✅"),
        "error": (tint(Color.DANGER, "26"), Color.DANGER_TEXT, "❌"),
        "warning": (tint(Color.WARNING, "26"), Color.WARNING_TEXT, "⚠️"),
        "info": (tint(Color.INFO, "26"), Color.INFO_TEXT, "ℹ️"),
    }
    return styles.get(message_type, styles["info"])
