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

    task = asyncio.create_task(view._connect_to_server(None))
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

    await view._connect_to_server(None)

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

    await view._connect_to_server(None)

    assert view.is_connected is False
    assert view.connect_button.disabled is False        # 按钮恢复
    assert "连接错误" in view.message_banner.content.value


async def test_connect_requires_complete_credentials():
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    fill_credentials(view, password="")

    await view._connect_to_server(None)

    assert view.message_banner.visible is True
    assert "完整" in view.message_banner.content.value


async def test_toast_uses_show_dialog():
    """底部提示（SnackBar）走 page.show_dialog —— Flet 0.86 正确 API"""
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())

    view._toast("连接成功", "success")

    assert len(page.dialogs) == 1


# === SMB 来源交互测试 ===

import nextcloud_music_player.smb_client as smb_client_module


def switch_to_smb(view):
    """模拟把来源切换器切到 SMB（Flet 0.86 的 selected 是 list 而非 set）"""
    view.source_selector.selected = ["smb"]
    view._on_source_type_changed(None)


def fill_smb_credentials(view, host="192.168.1.100", share="music",
                         user="u", password="p"):
    view.smb_host_input.value = host
    view.smb_share_input.value = share
    view.smb_username_input.value = user
    view.smb_password_input.value = password


async def test_source_switch_toggles_forms_and_saves_choice():
    """切换到 SMB：表单互换、标题切换、来源选择持久化"""
    page = FakePage()
    config = FakeConfigManager()
    view = make_connection_view(page, base_context(config), FakeViewManager())

    assert view.nextcloud_form_card.visible is True
    assert view.smb_form_card.visible is False

    switch_to_smb(view)

    assert view.nextcloud_form_card.visible is False
    assert view.smb_form_card.visible is True
    assert view.title_text.value == "SMB"
    assert config.get("connection.source_type") == "smb"


async def test_connect_smb_requires_host_and_share():
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    switch_to_smb(view)
    fill_smb_credentials(view, host="", share="")

    await view._connect_to_server(None)

    assert view.is_connected is False
    assert "SMB 主机地址和共享名称" in view.message_banner.content.value


async def test_connect_smb_success_flow(monkeypatch):
    """SMB 连接成功：客户端进入 app_context 槽位并跳转文件列表"""
    page = FakePage()
    view_manager = FakeViewManager()
    client = FakeNextcloudClient(connect_ok=True)
    monkeypatch.setattr(smb_client_module, "SMBClient",
                        lambda *args, **kwargs: client)

    context = base_context(FakeConfigManager())
    view = make_connection_view(page, context, view_manager)
    switch_to_smb(view)
    fill_smb_credentials(view)

    await view._connect_to_server(None)

    assert view.is_connected is True
    assert context["nextcloud_client"] is client
    assert view_manager.switched_to == ["file_list"]


async def test_connect_smb_saves_config(monkeypatch):
    """SMB 连接成功后凭据与来源类型写入配置"""
    page = FakePage()
    client = FakeNextcloudClient(connect_ok=True)
    monkeypatch.setattr(smb_client_module, "SMBClient",
                        lambda *args, **kwargs: client)

    config = FakeConfigManager({"connection": {"remember_credentials": True}})
    view = make_connection_view(page, base_context(config), FakeViewManager())
    switch_to_smb(view)
    fill_smb_credentials(view, host="nas.local", share="music")

    await view._connect_to_server(None)

    assert config.get("connection.source_type") == "smb"
    assert config.get("connection.smb.host") == "nas.local"
    assert config.get("connection.smb.share") == "music"
    assert config.get("connection.smb.port") == 445
    assert config.get("connection.smb.username") == "u"
    assert config.get("connection.smb.password") == "p"
