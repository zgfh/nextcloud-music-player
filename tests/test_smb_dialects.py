"""smb_dialects 协商补丁单测：模拟 pysmb 协商回调，不发真实网络包。

回归背景：部分 NAS 固件对通配方言串 "SMB 2.???" 不按 [MS-SMB2] 回 0x02FF，
而是按字面选中 "SMB 2.002"。该方言下 pysmb listPath 固定使用的
FileIdBothDirectoryInformation 必须被服务器拒绝（STATUS_INVALID_PARAMETER），
表现为：共享列表正常、进入目录浏览即报错（0xc000000d）。
补丁需识别 0x0202 并补发全方言阶梯的 SMB2 NEGOTIATE 争取升级。
"""

import struct
from unittest.mock import MagicMock

import pytest

from nextcloud_music_player import smb_dialects


@pytest.fixture
def patched_handler():
    smb_dialects.enable_modern_negotiation()
    from smb import base as smb_base

    yield smb_base.SMB._handleNegotiateResponse_SMB2
    smb_dialects.reset()


def _negotiate_response(revision):
    message = MagicMock()
    message.payload.dialect_revision = revision
    return message


def _fake_connection():
    fake = MagicMock()
    # MagicMock 自动属性为 truthy，会误判"已补发"；显式归零
    fake._nmp_phase2_sent = False
    fake._nmp_prefer_311 = True
    return fake


def _prepare(request):
    holder = MagicMock()
    request.payload.prepare(holder)
    return holder.data or b""


def _sent_negotiate_ladders(fake_self):
    """收集所有补发 SMB2 NEGOTIATE 的方言表（忽略原 handler 的 session setup 等）"""
    ladders = []
    for call in fake_self._sendSMBMessage.call_args_list:
        data = _prepare(call.args[0])
        if data[:2] != b"\x24\x00":  # StructureSize=36 才是 NEGOTIATE
            continue
        revisions = []
        offset = 36
        while offset + 2 <= len(data):
            (value,) = struct.unpack_from("<H", data, offset)
            if value == 0:  # 方言表结束（其后为填充与协商上下文）
                break
            revisions.append(value)
            offset += 2
        ladders.append(revisions)
    return ladders


def test_literal_202_selection_triggers_full_ladder_rescue(patched_handler):
    """字面选中 SMB 2.002 → 补发 2.002~3.1.1 全方言 NEGOTIATE"""
    fake = _fake_connection()
    patched_handler(fake, _negotiate_response(0x0202))

    assert fake._nmp_phase2_sent is True
    assert _sent_negotiate_ladders(fake) == [[0x0202, 0x0210, 0x0300, 0x0302, 0x0311]]


def test_02ff_response_still_sends_311_only(patched_handler):
    """0x02FF 通配应答路径不受影响：默认只发 3.1.1 单方言"""
    fake = _fake_connection()
    patched_handler(fake, _negotiate_response(0x02FF))

    assert fake._nmp_phase2_sent is True
    assert _sent_negotiate_ladders(fake) == [[0x0311]]


def test_rescue_fires_only_once_per_connection(patched_handler):
    """已补发过（服务器真的最高只到 2.002）→ 不再重复补发，交回原处理"""
    fake = _fake_connection()
    fake._nmp_phase2_sent = True
    patched_handler(fake, _negotiate_response(0x0202))
    assert _sent_negotiate_ladders(fake) == []


def test_modern_dialect_passes_through(patched_handler):
    """3.x 正常应答 → 不补发，交给 pysmb 原处理"""
    fake = _fake_connection()
    patched_handler(fake, _negotiate_response(0x0311))
    assert _sent_negotiate_ladders(fake) == []
    assert fake._nmp_phase2_sent is False


def test_negotiated_large_read_size_is_capped_to_64k():
    """pysmb 不会为大 READ 设 CreditCharge，必须限制单次请求。"""
    smb_dialects.enable_modern_negotiation()
    from smb import base as smb_base

    conn = smb_base.SMB.__new__(smb_base.SMB)
    payload = MagicMock(
        max_transact_size=8 * 1024 * 1024,
        max_read_size=8 * 1024 * 1024,
        max_write_size=8 * 1024 * 1024,
        security_mode=0,
        capabilities=0,
    )
    try:
        smb_base.SMB._updateServerInfo_SMB2(conn, payload)
        assert conn.max_read_size == 65536
        assert conn.max_transact_size == 65536
    finally:
        smb_dialects.reset()
