"""
pysmb 现代协商补丁 —— 支持 SMB 2.1 / 3.0 / 3.0.2 / 3.1.1 服务器（iOS 可用）

pysmb 原生只提供 SMB1（NT LM 0.12）与 SMB 2.002 方言，服务器设置
`server min protocol >= SMB2_10 / SMB3_00` 时会拒绝协商并报：
    ProtocolError: Server does not support any of the pysmb dialects

本补丁做三件事（仅标准库 monkeypatch，serious-python 打包不受影响）：

1. 方言列表追加魔法串 "SMB 2.???"（[MS-SMB2] 规定的多协议协商写法，
   表示"我支持 SMB2+，请告知你的版本"）。注意 "SMB 2.1"/"SMB 3.0"
   不是合法的 SMB1 协商字符串，服务器不会识别。
2. 服务器对魔法串的应答 DialectRevision=0x02FF 是中间态：要求客户端
   再发一次真正的 SMB2 NEGOTIATE 才算协商完成。pysmb 误把它当最终
   结果直接进入会话建立，导致连接被服务器丢弃。这里拦截该应答并按
   连接策略补发第二阶段 SMB2 NEGOTIATE（见 enable_modern_negotiation /
   configure_connection）：
   - prefer_311=True（默认）：先只提供 0x0311 单方言并附预认证完整性
     协商上下文（[MS-SMB2] 2.2.3.1，SHA-512，3.1.1 必带）。现代服务器
     （Windows 10+/Samba 4.3+/主流 NAS）一次协商到位。
   - prefer_311=False：回退策略，提供 [2.002, 2.1, 3.0, 3.0.2] 多方言
     由服务器自选（老服务器 / macOS 等 3.1.1 之前的实现）。
     smb_client 在 3.1.1 协商被拒时自动切换到该策略重连。
   部分 NAS 固件不用 0x02FF 应答通配串，而是按字面选中 "SMB 2.002"
   （0x0202）；该方言下 pysmb listPath 固定的 FileIdBothDirectoryInformation
   按 [MS-SMB2] 3.3.5.18 必须被拒（STATUS_INVALID_PARAMETER，表现为
   共享列表正常而目录列举全挂）。对这类服务器补发一次全方言阶梯
   [2.002, 2.1, 3.0, 3.0.2, 3.1.1] 的 SMB2 NEGOTIATE，争取升级到现代方言。
3. 修正第二阶段 NEGOTIATE 请求的固定头布局：[MS-SMB2] 2.2.3 规定
   StructureSize(2) DialectCount(2) SecurityMode(2) Reserved(2)
   Capabilities(4) ClientGuid(16) 共 28 字节，此前的实现多打包了
   2 字节零填充，导致 ClientGuid 与方言表整体后移、服务器把
   ClientGuid 末 2 字节当作第一个方言解析，实际只能协商到 SMB 2.1。

仍不支持：强制签名（SMB3 要求 AES-CMAC）或强制加密（AES-CCM/GCM）的
服务器——纯 Python 环境没有可用的 AES 实现；Windows 11 24H2+/Server 2025
默认强制签名，这类服务器协商失败后由 smb_client 翻译为明确的中文提示。
（3.1.1 的预认证完整性哈希仅用于签名/加密密钥派生，未签名会话无需计算，
因此本补丁只声明 SHA-512 能力而不实际维护哈希链。）
"""

import logging
import os
import struct

logger = logging.getLogger(__name__)

BASE_DIALECTS2 = [b"SMB 2.002"]
MAGIC_DIALECTS2 = [b"SMB 2.002", b"SMB 2.???"]

# 回退阶段 SMB2 NEGOTIATE 提供的方言：
# 0x0202=2.002, 0x0210=2.1, 0x0300=3.0, 0x0302=3.0.2（Server 2012 R2）
SMB2_DIALECT_REVISIONS = (0x0202, 0x0210, 0x0300, 0x0302)

# 救援阶梯：服务器按字面选中 "SMB 2.002" 时一次性提供全部现代方言
# （3.1.1 与旧方言混列合法，预认证完整性上下文随行）
SMB2_DIALECT_REVISIONS_ALL = (0x0202, 0x0210, 0x0300, 0x0302, 0x0311)

SMB2_DIALECT_002 = 0x0202
SMB2_DIALECT_311 = 0x0311

# 服务器应答 0x02FF 表示"选择了 SMB 2.???，等待真正的 SMB2 NEGOTIATE"
SMB_2FF = 0x02FF

# [MS-SMB2] 2.2.3.1 SMB2_NEGOTIATE_CONTEXT 类型：预认证完整性能力
SMB2_PREAUTH_INTEGRITY_CAPABILITIES = 0x0001

# 预认证完整性哈希算法：SHA-512
PREAUTH_HASH_SHA512 = 0x0001

# QUERY_DIRECTORY / QUERY_INFO 输出缓冲上限。pysmb 直接把服务器协商的
# MaxTransactSize（可达 8 MiB）当请求值，部分服务器对 transact 类命令
# 校验更严，超限回 STATUS_INVALID_PARAMETER(0xC000000D)；64 KiB 是
# 各 SMB 客户端事实上的安全值
QUERY_OUTPUT_BUFFER_CAP = 65536

# pysmb 会把服务器协商的 MaxReadSize 直接用于单次 SMB2 READ。SMB 3.x
# 对超过 64 KiB 的请求需要正确设置 CreditCharge；pysmb 当前没有设置，
# 部分服务器因此返回 STATUS_INVALID_PARAMETER。限制为 64 KiB 后由 pysmb
# 自身的循环继续分块读取，不影响最终文件内容。
READ_BUFFER_CAP = 65536

# SMB2 消息头 64 字节 + 固定结构 36 字节 + 单方言 2 字节 = 102，
# 补齐到 8 字节对齐（协商上下文要求）后上下文位于 104
_SMB2_HEADER_SIZE = 64
_NEGOTIATE_CONTEXT_ALIGN = 8
PREAUTH_SALT_SIZE = 32

_patched = False
_original_handle_negotiate = None
_original_update_server_info = None


def _make_negotiate_payload_class(revisions, negotiate_contexts=b""):
    """构造 [MS-SMB2] 2.2.3 SMB2 NEGOTIATE 请求 payload

    固定头 28 字节（StructureSize/DialectCount/SecurityMode/Reserved/
    Capabilities/ClientGuid）；带协商上下文（3.1.1）时追加
    NegotiateContextOffset/Count/Reserved2 共 8 字节，方言表后补零至
    8 字节对齐再接上下文。
    """
    from smb.smb2_structs import SMB2_COM_NEGOTIATE, Structure

    client_guid = os.urandom(16)
    has_contexts = bool(negotiate_contexts)
    dialect_bytes = b"".join(struct.pack("<H", d) for d in revisions)
    padding = b""

    if has_contexts:
        # 头 64 + 固定 36 + 方言表 -> 按 8 字节对齐即为上下文偏移
        context_offset = _SMB2_HEADER_SIZE + 36 + len(dialect_bytes)
        context_offset += -context_offset % _NEGOTIATE_CONTEXT_ALIGN
        padding = b"\x00" * (
            context_offset - _SMB2_HEADER_SIZE - 36 - len(dialect_bytes)
        )

    class _SMB2NegotiateRequest(Structure):
        """[MS-SMB2] 2.2.3 SMB2 NEGOTIATE Request"""

        def initMessage(self, message):
            message.command = SMB2_COM_NEGOTIATE

        def prepare(self, message):
            # SecurityMode=0：不启用签名。SMB3 的签名算法是 AES-CMAC，
            # pysmb 仅实现 SMB2 的 HMAC-SHA256，开启反而会导致签名不匹配
            fixed = struct.pack(
                "<HHHHI16s",
                36,  # StructureSize
                len(revisions),  # DialectCount
                0,  # SecurityMode
                0,  # Reserved
                0,  # Capabilities
                client_guid,
            )
            if has_contexts:
                fixed += struct.pack(
                    "<IHH",
                    context_offset,  # NegotiateContextOffset（相对 SMB2 头）
                    1,  # NegotiateContextCount
                    0,  # Reserved2
                )
            message.data = fixed + dialect_bytes + padding + negotiate_contexts

    return _SMB2NegotiateRequest()


def _build_preauth_integrity_context(salt=None):
    """打包 SMB2_PREAUTH_INTEGRITY_CAPABILITIES 协商上下文（仅声明 SHA-512）"""
    salt = salt if salt is not None else os.urandom(PREAUTH_SALT_SIZE)
    data = (
        struct.pack("<HH", 1, len(salt))  # HashAlgorithmCount, SaltLength
        + struct.pack("<H", PREAUTH_HASH_SHA512)
        + salt
    )
    return (
        struct.pack(
            "<HHI",
            SMB2_PREAUTH_INTEGRITY_CAPABILITIES,
            len(data),  # DataLength
            0,  # Reserved
        )
        + data
    )


def _build_negotiate_request_payload():
    """回退策略：多方言 SMB2 NEGOTIATE（无协商上下文）"""
    return _make_negotiate_payload_class(SMB2_DIALECT_REVISIONS)


def _build_negotiate_311_request_payload():
    """优先策略：0x0311 单方言 + 预认证完整性上下文（3.1.1 必带）"""
    return _make_negotiate_payload_class(
        (SMB2_DIALECT_311,), _build_preauth_integrity_context()
    )


def _build_rescue_negotiate_payload():
    """救援策略：全方言阶梯 + 预认证完整性上下文

    用于服务器按字面选中 "SMB 2.002"（未按 [MS-SMB2] 用 0x02FF 应答通配串）
    的情况：一次给齐 2.002~3.1.1，让服务器选出现代方言。
    """
    return _make_negotiate_payload_class(
        SMB2_DIALECT_REVISIONS_ALL, _build_preauth_integrity_context()
    )


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
            self._nmp_phase2_sent = True
            if getattr(self, "_nmp_prefer_311", True):
                logger.info("服务器应答 SMB 2.???(0x02FF)，补发 SMB 3.1.1 NEGOTIATE")
                self._sendSMBMessage(
                    SMB2Message(_build_negotiate_311_request_payload())
                )
            else:
                logger.info("服务器应答 SMB 2.???(0x02FF)，补发多方言 SMB2 NEGOTIATE")
                self._sendSMBMessage(SMB2Message(_build_negotiate_request_payload()))
            return
        if revision == SMB2_DIALECT_002 and not getattr(
            self, "_nmp_phase2_sent", False
        ):
            # 服务器未按 [MS-SMB2] 用 0x02FF 应答通配串，而是按字面选中
            # "SMB 2.002"（部分 NAS 固件）。2.002 方言不支持
            # FileIdBothDirectoryInformation（pysmb listPath 固定使用，
            # [MS-SMB2] 3.3.5.18 规定必须拒绝并返回 STATUS_INVALID_PARAMETER），
            # 目录列举会全挂。补发一次全方言 SMB2 NEGOTIATE 争取升级到现代方言；
            # 若服务器仍选 2.002（真的只支持到 2.002）则照常接受。
            self._nmp_phase2_sent = True
            logger.info(
                "服务器按字面选中 SMB 2.002，补发全方言 SMB2 NEGOTIATE 争取升级"
            )
            self._sendSMBMessage(SMB2Message(_build_rescue_negotiate_payload()))
            return
        if revision == SMB2_DIALECT_311:
            logger.info("✅ SMB 3.1.1 协商成功（未签名/未加密）")
        return original(self, message)

    smb_base.SMB._handleNegotiateResponse_SMB2 = patched
    _patched = True
    logger.info("已安装 pysmb 两阶段 SMB2 协商补丁")


def patch_query_output_buffer_cap():
    """安装 QUERY 输出缓冲钳制补丁（幂等）

    pysmb 的 listPath/getSecurity 把协商的 MaxTransactSize 原样作为
    QUERY_DIRECTORY / QUERY_INFO 的 OutputBufferLength（实测有服务器
    协商 8 MiB 却对该值回 STATUS_INVALID_PARAMETER）。钳制到 64 KiB
    只影响单次请求的批量大小，多批次循环由 pysmb 自动完成。
    """
    global _original_update_server_info
    if _original_update_server_info is not None:
        return

    from smb import base as smb_base

    original = smb_base.SMB._updateServerInfo_SMB2
    _original_update_server_info = original

    def patched(self, payload):
        original(self, payload)
        if self.max_read_size > READ_BUFFER_CAP:
            logger.debug(
                "MaxReadSize %d 钳制为 %d（兼容 SMB3 credit charge）",
                self.max_read_size,
                READ_BUFFER_CAP,
            )
            self.max_read_size = READ_BUFFER_CAP
        if self.max_transact_size > QUERY_OUTPUT_BUFFER_CAP:
            logger.debug(
                "MaxTransactSize %d 钳制为 %d（transact 类命令输出缓冲）",
                self.max_transact_size,
                QUERY_OUTPUT_BUFFER_CAP,
            )
            self.max_transact_size = QUERY_OUTPUT_BUFFER_CAP

    smb_base.SMB._updateServerInfo_SMB2 = patched
    logger.info("已安装 SMB READ/QUERY 缓冲钳制补丁（64 KiB）")


def enable_modern_negotiation():
    """启用现代协商：魔法串 + 两阶段补丁（幂等）"""
    import smb.smb_structs as structs

    # ComNegotiateRequest.prepare 每次发送协商时读取模块级 DIALECTS2，
    # 原位替换即可对后续连接生效；保持 "SMB 2.002" 首位（索引常量依赖）
    if list(structs.DIALECTS2) != MAGIC_DIALECTS2:
        structs.DIALECTS2[:] = MAGIC_DIALECTS2
        logger.info("SMB 协商方言: SMB1 / SMB 2.002 / SMB 2.???")
    patch_two_stage_negotiate()
    patch_query_output_buffer_cap()


def configure_connection(conn, prefer_311: bool = True):
    """为单条连接选择第二阶段协商策略（须在 connect() 之前调用）

    prefer_311=True：先试 SMB 3.1.1（现代服务器一步到位）；
    False：多方言由服务器自选（3.1.1 之前的老服务器）。
    """
    conn._nmp_prefer_311 = bool(prefer_311)


def is_dialect_rejection(exc: Exception) -> bool:
    """判断异常是否为'协商阶段被服务器拒绝'（可换方言策略重试）"""
    msg = str(exc)
    # 第一阶段（SMB1 NEGOTIATE）拒绝
    if "does not support any of the" in msg or "Unknown dialect index" in msg:
        return True
    # 第二阶段（SMB2 NEGOTIATE）非 0 状态：服务器不支持所提供的方言
    return "Unknown status value" in msg and "SMB2_COM_NEGOTIATE" in msg


def reset():
    """恢复 pysmb 原生行为（测试用）"""
    global _patched, _original_update_server_info
    import smb.smb_structs as structs
    from smb import base as smb_base

    structs.DIALECTS2[:] = BASE_DIALECTS2
    if _patched and _original_handle_negotiate is not None:
        smb_base.SMB._handleNegotiateResponse_SMB2 = _original_handle_negotiate
    _patched = False
    if _original_update_server_info is not None:
        smb_base.SMB._updateServerInfo_SMB2 = _original_update_server_info
        _original_update_server_info = None
