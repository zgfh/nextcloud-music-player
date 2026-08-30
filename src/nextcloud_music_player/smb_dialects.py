"""
pysmb 现代协商补丁 —— 支持 SMB 2.1 / SMB 3.0 服务器（iOS 可用）

pysmb 原生只提供 SMB1（NT LM 0.12）与 SMB 2.002 方言，服务器设置
`server min protocol >= SMB2_10 / SMB3_00` 时会拒绝协商并报：
    ProtocolError: Server does not support any of the pysmb dialects

本补丁做两件事（仅标准库 monkeypatch，serious-python 打包不受影响）：

1. 方言列表追加魔法串 "SMB 2.???"（[MS-SMB2] 规定的多协议协商写法，
   表示"我支持 SMB2+，请告知你的版本"）。注意 "SMB 2.1"/"SMB 3.0"
   不是合法的 SMB1 协商字符串，服务器不会识别。
2. 服务器对魔法串的应答 DialectRevision=0x02FF 是中间态：要求客户端
   再发一次真正的 SMB2 NEGOTIATE 才算协商完成。pysmb 误把它当最终
   结果直接进入会话建立，导致连接被服务器丢弃。这里拦截该应答并补发
   SMB2 NEGOTIATE，方言表 [SMB 2.002, SMB 2.1, SMB 3.0] 由服务器自选：
   - 服务器上限 SMB 2.1 → 协商 2.1（HMAC-SHA256 签名，pysmb 已实现）
   - 服务器上限 SMB 3.x → 协商 3.0（不启用签名/加密）

仍不支持：服务器 min protocol = SMB3_11（需预认证完整性）、强制签名
（SMB3 下要求 AES-CMAC）或强制加密（AES-CCM/GCM）的服务器——这类
服务器协商失败后由 smb_client 翻译为明确的中文提示。
"""

import logging
import os
import struct

logger = logging.getLogger(__name__)

BASE_DIALECTS2 = [b"SMB 2.002"]
MAGIC_DIALECTS2 = [b"SMB 2.002", b"SMB 2.???"]

# 第二阶段 SMB2 NEGOTIATE 提供的方言（0x0202=2.002, 0x0210=2.1, 0x0300=3.0）
SMB2_DIALECT_REVISIONS = (0x0202, 0x0210, 0x0300)

# 服务器应答 0x02FF 表示"选择了 SMB 2.???，等待真正的 SMB2 NEGOTIATE"
SMB_2FF = 0x02FF

_patched = False
_original_handle_negotiate = None


def _build_negotiate_request_payload():
    from smb.smb2_structs import SMB2_COM_NEGOTIATE, Structure

    revisions = SMB2_DIALECT_REVISIONS
    client_guid = os.urandom(16)

    class _SMB2NegotiateRequest(Structure):
        """[MS-SMB2] 2.2.3 SMB2 NEGOTIATE Request（无协商上下文）"""

        def initMessage(self, message):
            message.command = SMB2_COM_NEGOTIATE

        def prepare(self, message):
            dialect_bytes = b"".join(
                struct.pack("<H", d) for d in revisions
            )
            # SecurityMode=0：不启用签名。SMB3 的签名算法是 AES-CMAC，
            # pysmb 仅实现 SMB2 的 HMAC-SHA256，开启反而会导致签名不匹配
            message.data = (
                struct.pack(
                    "<HHHII16s",
                    36,  # StructureSize
                    len(revisions),  # DialectCount
                    0,  # SecurityMode
                    0,  # Reserved
                    0,  # Capabilities
                    client_guid,
                )
                + dialect_bytes
            )

    return _SMB2NegotiateRequest()


def patch_two_stage_negotiate():
    """安装第二阶段协商补丁（幂等）"""
    global _patched
    if _patched:
        return

    from smb import base as smb_base
    from smb.smb2_structs import SMB2Message

    global _original_handle_negotiate
    # _handleNegotiateResponse_SMB2 定义在基类 SMB 上（SMBConnection 继承）
    original = smb_base.SMB._handleNegotiateResponse_SMB2
    _original_handle_negotiate = original

    def patched(self, message):
        revision = getattr(message.payload, "dialect_revision", 0)
        if revision == SMB_2FF:
            logger.info(
                "服务器应答 SMB 2.???(0x02FF)，补发 SMB2 NEGOTIATE 完成协商"
            )
            self._sendSMBMessage(
                SMB2Message(_build_negotiate_request_payload())
            )
            return
        return original(self, message)

    smb_base.SMB._handleNegotiateResponse_SMB2 = patched
    _patched = True
    logger.info("已安装 pysmb 两阶段 SMB2 协商补丁")


def enable_modern_negotiation():
    """启用现代协商：魔法串 + 两阶段补丁（幂等）"""
    import smb.smb_structs as structs

    # ComNegotiateRequest.prepare 每次发送协商时读取模块级 DIALECTS2，
    # 原位替换即可对后续连接生效；保持 "SMB 2.002" 首位（索引常量依赖）
    if list(structs.DIALECTS2) != MAGIC_DIALECTS2:
        structs.DIALECTS2[:] = MAGIC_DIALECTS2
        logger.info("SMB 协商方言: SMB1 / SMB 2.002 / SMB 2.???")
    patch_two_stage_negotiate()


def is_dialect_rejection(exc: Exception) -> bool:
    """判断异常是否为'服务器不支持所提供方言'的协商拒绝"""
    msg = str(exc)
    return "does not support any of the" in msg or "Unknown dialect index" in msg


def reset():
    """恢复 pysmb 原生行为（测试用）"""
    global _patched
    import smb.smb_structs as structs
    from smb import base as smb_base

    structs.DIALECTS2[:] = BASE_DIALECTS2
    if _patched and _original_handle_negotiate is not None:
        smb_base.SMB._handleNegotiateResponse_SMB2 = (
            _original_handle_negotiate
        )
    _patched = False
