"""Full packaged-app E2E against an in-process Mock Nextcloud/WebDAV server."""

import asyncio

import flet.testing as ftt

from mock_nextcloud import PASSWORD, SONG_NAME, USERNAME


async def _settle_network(tester, seconds=0.5):
    await asyncio.sleep(seconds)
    await tester.pump_and_settle()


async def _open_nextcloud_form(tester):
    await tester.tap(await tester.find_by_text("连接"))
    await tester.pump_and_settle()
    if not (await tester.find_by_key("nextcloud_url")).count:
        await tester.tap(await tester.find_by_text("Nextcloud"))
        await tester.pump_and_settle()


async def _fill_credentials(tester, url, username, password):
    await tester.enter_text(await tester.find_by_key("nextcloud_url"), url)
    await tester.enter_text(await tester.find_by_key("nextcloud_username"), username)
    await tester.enter_text(await tester.find_by_key("nextcloud_password"), password)
    await tester.enter_text(
        await tester.find_by_key("nextcloud_sync_folder"), "/music"
    )


async def test_nextcloud_sync_download_and_playback(
    flet_app: ftt.FletTestApp, mock_nextcloud_server
):
    tester = flet_app.tester
    await tester.pump_and_settle()

    await _open_nextcloud_form(tester)
    await _fill_credentials(
        tester, mock_nextcloud_server.url, USERNAME, PASSWORD
    )

    await tester.tap(await tester.find_by_text("建立连接"))
    await _settle_network(tester, 1.0)
    assert (await tester.find_by_text("同步")).count == 1

    await tester.tap(await tester.find_by_text("同步"))
    await _settle_network(tester, 1.0)
    assert (await tester.find_by_key(f"song:{SONG_NAME}")).count == 1

    await tester.tap(await tester.find_by_key(f"song:{SONG_NAME}"))
    await tester.pump_and_settle()
    await tester.tap(await tester.find_by_text("播放"))
    await _settle_network(tester, 2.0)

    assert (await tester.find_by_text("播放中")).count >= 1
    assert (await tester.find_by_text(SONG_NAME)).count >= 1


async def test_nextcloud_wrong_password_shows_error_then_recovers(
    flet_app: ftt.FletTestApp, mock_nextcloud_server
):
    """密码错误：SnackBar 提示且不进入同步界面；改对凭据后可立即重连成功。"""
    tester = flet_app.tester
    await tester.pump_and_settle()

    await _open_nextcloud_form(tester)
    await _fill_credentials(
        tester, mock_nextcloud_server.url, USERNAME, "not-the-password"
    )

    await tester.tap(await tester.find_by_text("建立连接"))
    await _settle_network(tester, 1.0)

    assert (
        await tester.find_by_text_containing("连接失败")
    ).count >= 1, "凭据错误应出现错误提示"
    assert (await tester.find_by_text("同步")).count == 0, "失败后不应进入已连接状态"

    # 错误后 UI 仍可用：修正密码重连即成功
    password_field = await tester.find_by_key("nextcloud_password")
    await tester.enter_text(password_field, PASSWORD)
    await tester.tap(await tester.find_by_text("建立连接"))
    await _settle_network(tester, 1.0)
    assert (await tester.find_by_text("同步")).count == 1


async def test_nextcloud_unreachable_server_shows_error(flet_app: ftt.FletTestApp):
    """服务器不可达（端口关闭）：立即反馈连接错误，而不是无响应或崩溃。"""
    tester = flet_app.tester
    await tester.pump_and_settle()

    await _open_nextcloud_form(tester)
    await _fill_credentials(tester, "http://127.0.0.1:1", USERNAME, PASSWORD)

    await tester.tap(await tester.find_by_text("建立连接"))
    await _settle_network(tester, 2.0)

    assert (
        await tester.find_by_text_containing("连接失败")
    ).count >= 1, "不可达服务器应出现连接失败提示"
    assert (await tester.find_by_text("同步")).count == 0
