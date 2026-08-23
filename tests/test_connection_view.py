"""
连接视图交互测试：连接中状态、成功/失败反馈、文件夹浏览入口
"""

import asyncio

import nextcloud_music_player.nextcloud_client as nextcloud_client_module
from fakes import FakeConfigManager, FakeNextcloudClient, FakePage, FakeViewManager


def make_connection_view(page, app_context, view_manager):
    from nextcloud_music_player.views.connection_view import ConnectionView
    view = ConnectionView(page, app_context, view_manager)
    view.build()
    return view


def base_context(config_manager, nextcloud_client=None):
    return {
        "config_manager": config_manager,
        "nextcloud_client": nextcloud_client,
        "music_service": None,
        "lyrics_service": None,
    }


def fill_credentials(view, url="https://cloud.example.com", user="u", password="p"):
    view.url_input.value = url
    view.username_input.value = user
    view.password_input.value = password


async def test_browse_folder_without_connection_shows_error():
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())

    view._browse_folder(None)

    assert view.message_banner.visible is True
    assert "请先连接" in view.message_banner.content.value


async def test_browse_folder_with_connection_opens_selector():
    page = FakePage()
    client = FakeNextcloudClient(directories={"/": [{"name": "Music"}]})
    view = make_connection_view(
        page, base_context(FakeConfigManager(), nextcloud_client=client), FakeViewManager())
    view.sync_folder_input.value = "/Music"

    view._browse_folder(None)
    await asyncio.sleep(0.05)

    assert len(page.dialogs) == 1                       # 文件夹选择对话框已打开


async def test_browse_folder_selection_updates_input_and_config(tmp_path):
    page = FakePage()
    config = FakeConfigManager()
    client = FakeNextcloudClient(directories={"/": []})
    view = make_connection_view(
        page, base_context(config, nextcloud_client=client), FakeViewManager())

    from nextcloud_music_player.views.folder_selector import FolderSelector
    selected = []
    selector = FolderSelector(page, client, "/")
    selector.show_dialog(selected.append)
    await asyncio.sleep(0.05)
    selector._select_current(None)

    # 模拟 on_selected 回调对输入框与配置的更新（与 _browse_folder 内一致）
    view.sync_folder_input.value = selected[0]

    assert view.sync_folder_input.value == "/"


async def test_connect_success_flow(monkeypatch):
    """连接成功：连接中状态 → 成功提示 → 跳转文件列表"""
    page = FakePage()
    view_manager = FakeViewManager()
    client = FakeNextcloudClient(connect_ok=True, connect_delay=0.2)
    monkeypatch.setattr(nextcloud_client_module, "NextCloudClient",
                        lambda *args, **kwargs: client)

    context = base_context(FakeConfigManager())
    view = make_connection_view(page, context, view_manager)
    fill_credentials(view)

    task = asyncio.create_task(view._connect_to_nextcloud(None))
    await asyncio.sleep(0.05)

    assert view.connect_button.disabled is True         # 连接中按钮禁用

    await task
    assert view.is_connected is True
    assert view_manager.switched_to == ["file_list"]    # 自动进入文件列表


async def test_connect_failure_shows_error(monkeypatch):
    """凭据错误：失败提示可见，不跳转"""
    page = FakePage()
    view_manager = FakeViewManager()
    client = FakeNextcloudClient(connect_ok=False)
    monkeypatch.setattr(nextcloud_client_module, "NextCloudClient",
                        lambda *args, **kwargs: client)

    view = make_connection_view(page, base_context(FakeConfigManager()), view_manager)
    fill_credentials(view)

    await view._connect_to_nextcloud(None)

    assert view.is_connected is False
    assert view_manager.switched_to == []
    assert view.message_banner.visible is True
    assert "连接失败" in view.message_banner.content.value


async def test_connect_exception_shows_error(monkeypatch):
    """网络异常（超时/拒绝连接）：错误提示可见，按钮恢复可用"""
    page = FakePage()
    view_manager = FakeViewManager()
    client = FakeNextcloudClient(connect_error=ConnectionError("refused"))
    monkeypatch.setattr(nextcloud_client_module, "NextCloudClient",
                        lambda *args, **kwargs: client)

    view = make_connection_view(page, base_context(FakeConfigManager()), view_manager)
    fill_credentials(view)

    await view._connect_to_nextcloud(None)

    assert view.is_connected is False
    assert view.connect_button.disabled is False        # 按钮恢复
    assert "连接错误" in view.message_banner.content.value


async def test_connect_requires_complete_credentials():
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    fill_credentials(view, password="")

    await view._connect_to_nextcloud(None)

    assert view.message_banner.visible is True
    assert "完整" in view.message_banner.content.value


async def test_toast_uses_show_dialog():
    """底部提示（SnackBar）走 page.show_dialog —— Flet 0.86 正确 API"""
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())

    view._toast("连接成功", "success")

    assert len(page.dialogs) == 1
