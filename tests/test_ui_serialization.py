"""
UI 序列化冒烟测试

背景：FakePage 交互测试只验证视图逻辑（回调/状态/配置），完全绕过 Flet 的
消息序列化层。若控件属性含 msgpack 无法打包的类型（如 set），无头测试全绿，
真机（iOS/桌面）却在首次 page.update() 全量序列化时崩溃——
"TypeError: can not serialize 'set' object" 即由此而来。

本测试复刻真实管线：ObjectPatch.from_diff（page.update 的 diff 算法）
→ patch.to_message()（wire 格式）→ msgpack.packb + Flet 官方 default 编码器，
任何不可序列化的属性值都会在此暴露。
"""

import sys
from pathlib import Path

import msgpack
import pytest
import flet as ft

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from fakes import FakeConfigManager, FakePage, FakeViewManager
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import (
    ClientAction,
    ClientMessage,
    PatchControlBody,
    configure_encode_object_for_msgpack,
)

# 与 flet_dart_bridge_server.send_message 完全一致的编码器
_ENCODE = configure_encode_object_for_msgpack(BaseControl)


def pack_control_tree(root) -> bytes:
    """复刻 iOS 崩溃路径：page.update() → 全量 diff → msgpack 打包"""
    patch, _, _ = ObjectPatch.from_diff(None, root, control_cls=BaseControl)
    message = ClientMessage(
        action=ClientAction.PATCH_CONTROL,
        body=PatchControlBody(id=0, patch=patch.to_message()),
    )
    return msgpack.packb([message.action, message.body], default=_ENCODE)


def make_connection_view(source_type="nextcloud"):
    from nextcloud_music_player.views.connection_view import ConnectionView

    context = {
        "config_manager": FakeConfigManager(
            {"connection": {"source_type": source_type}}
        ),
        "nextcloud_client": None,
        "music_service": None,
        "lyrics_service": None,
    }
    view = ConnectionView(FakePage(), context, FakeViewManager())
    view.build()
    return view


def test_connection_view_serializes_nextcloud():
    """默认 Nextcloud 表单的控件树可完整打包（首次 page.update 的全量序列化）"""
    view = make_connection_view("nextcloud")
    packed = pack_control_tree(view._container)
    assert isinstance(packed, bytes) and len(packed) > 0


def test_connection_view_serializes_smb():
    """切到 SMB 来源后的控件树（含 SegmentedButton/新表单）可完整打包"""
    view = make_connection_view("smb")
    view.source_selector.selected = ["smb"]
    view._on_source_type_changed(None)

    packed = pack_control_tree(view._container)
    assert isinstance(packed, bytes) and len(packed) > 0


def test_set_property_fails_packing():
    """负向对照：selected 传 set 必须在打包时抛 TypeError。

    这是本次 iOS 崩溃的原始 bug 形态——该用例证明上面的冒烟测试
    确实能抓住这类错误，而非形同虚设。
    """
    button = ft.SegmentedButton(
        segments=[ft.Segment(value="smb", label="SMB")],
        selected={"smb"},  # 故意复现原始 bug：类型应为 list[str]
    )
    with pytest.raises(TypeError, match="set"):
        pack_control_tree(button)
