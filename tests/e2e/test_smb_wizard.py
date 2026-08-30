"""端到端 UI 集成测试（flet test）：SMB 向导式连接入口

回归点：
1. SMB 空地址点「建立连接」→ SnackBar 提示（此前版本曾静默无反馈）
2. 填地址后点「建立连接」→ 弹出向导认证对话框（访客/用户登录）

运行方式：flet test --tests-dir tests/e2e -k smb
"""

import flet.testing as ftt


async def _goto_smb(tester):
    await tester.tap(await tester.find_by_text("连接"))
    await tester.pump_and_settle()
    if not (await tester.find_by_key("smb_host")).count:
        await tester.tap(await tester.find_by_text("SMB 共享"))
        await tester.pump_and_settle()


async def test_smb_empty_address_shows_feedback(flet_app: ftt.FletTestApp):
    """空地址直接点击连接：必须出现提示，不能无响应"""
    tester = flet_app.tester
    await tester.pump_and_settle()
    await _goto_smb(tester)

    host_input = await tester.find_by_key("smb_host")
    await tester.enter_text(host_input, "")

    await tester.tap(await tester.find_by_text("建立连接"))
    await tester.pump_and_settle()

    assert (
        await tester.find_by_text_containing("请先输入 SMB 服务器地址")
    ).count >= 1, "空地址点击连接应有 SnackBar 提示"


async def test_smb_address_opens_wizard_dialog(flet_app: ftt.FletTestApp):
    """填入地址点击连接：弹出向导认证对话框（访客/用户登录）"""
    tester = flet_app.tester
    await tester.pump_and_settle()
    await _goto_smb(tester)

    host_input = await tester.find_by_key("smb_host")
    await tester.enter_text(host_input, "192.0.2.1")

    await tester.tap(await tester.find_by_text("建立连接"))
    await tester.pump_and_settle()

    # 向导第一步：身份选择 + 连接按钮
    assert (await tester.find_by_text("访客")).count == 1
    assert (await tester.find_by_text("用户登录")).count == 1

    # 取消关闭向导，不发起网络请求
    await tester.tap(await tester.find_by_text("取消"))
    await tester.pump_and_settle()
    assert (await tester.find_by_text("访客")).count == 0
