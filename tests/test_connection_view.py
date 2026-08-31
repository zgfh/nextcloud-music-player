"""
连接视图交互测试：连接中状态、成功/失败反馈、文件夹浏览入口
"""

import asyncio

import nextcloud_music_player.nextcloud_client as nextcloud_client_module
from fakes import (
    FakeConfigManager,
    FakeNextcloudClient,
    FakePage,
    FakeViewManager,
    last_notification_text,
)


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


def last_message_text(page) -> str:
    """show_message 现以顶部浮层呈现，取最近一条的文本。"""
    return last_notification_text(page)


async def test_browse_folder_without_connection_shows_error():
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())

    view._browse_folder(None)

    assert "请先连接" in last_message_text(page)


async def test_browse_folder_with_connection_opens_selector():
    page = FakePage()
    client = FakeNextcloudClient(directories={"/": [{"name": "Music"}]})
    view = make_connection_view(
        page, base_context(FakeConfigManager(), nextcloud_client=client), FakeViewManager())
    view.sync_folder_input.value = "/Music"

    view._browse_folder(None)
    await asyncio.sleep(0.05)

    assert len(page.dialogs) == 1                       # 文件夹选择对话框已打开


async def test_gdrive_browse_after_authorization_connects_and_opens_selector(monkeypatch):
    """Google 授权后可直接浏览，无需额外点击“建立连接”。"""
    import nextcloud_music_player.gdrive_client as gdrive_client_module

    page = FakePage()
    client = FakeNextcloudClient(
        connect_ok=True, directories={"/": [{"name": "Music", "path": "folder-id"}]}
    )
    monkeypatch.setattr(
        gdrive_client_module, "GoogleDriveClient", lambda *args, **kwargs: client
    )
    config = FakeConfigManager(
        {
            "connection": {
                "source_type": "gdrive",
                "gdrive": {"refresh_token": "refresh-token"},
            }
        }
    )
    context = base_context(config)
    view = make_connection_view(page, context, FakeViewManager())
    view.gdrive_client_id_input.value = "client-id"
    view.gdrive_client_secret_input.value = "client-secret"

    view._browse_folder(None)
    await asyncio.sleep(0.05)

    assert context["nextcloud_client"] is client
    assert len(page.dialogs) == 1


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


def test_auto_connect_switch_is_saved_per_source():
    page = FakePage()
    config = FakeConfigManager()
    view = make_connection_view(page, base_context(config), FakeViewManager())

    view.auto_connect_switch.value = True
    view._on_auto_connect_changed(type("Event", (), {"control": view.auto_connect_switch})())

    assert config.get("connection.nextcloud.auto_connect") is True
    assert config.get("connection.auto_connect") is True


async def test_auto_connect_sources_are_independent(monkeypatch):
    import nextcloud_music_player.gdrive_client as gdrive_module
    import nextcloud_music_player.smb_client as smb_module

    page = FakePage()
    nextcloud = FakeNextcloudClient(connect_ok=True)
    smb = FakeNextcloudClient(connect_ok=False)
    gdrive = FakeNextcloudClient(connect_ok=True)
    monkeypatch.setattr(nextcloud_client_module, "NextCloudClient", lambda *a, **k: nextcloud)
    monkeypatch.setattr(smb_module, "SMBClient", lambda *a, **k: smb)
    monkeypatch.setattr(gdrive_module, "GoogleDriveClient", lambda *a, **k: gdrive)
    config = FakeConfigManager({
        "connection": {
            "source_type": "nextcloud",
            "server_url": "https://cloud.example.com",
            "username": "u",
            "password": "p",
            "smb": {"host": "nas", "share": "music", "username": "u", "password": "p"},
            "gdrive": {
                "client_id": "client-id", "client_secret": "secret",
                "refresh_token": "refresh-token",
            },
        }
    })
    context = base_context(config)
    view = make_connection_view(page, context, FakeViewManager())

    results = await asyncio.gather(
        view._auto_connect_source("nextcloud"),
        view._auto_connect_source("smb"),
        view._auto_connect_source("gdrive"),
        return_exceptions=True,
    )

    assert not isinstance(results[0], Exception)
    assert isinstance(results[1], Exception)
    assert not isinstance(results[2], Exception)
    assert set(context["source_clients"]) == {"nextcloud", "gdrive"}


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
    assert "连接失败" in last_message_text(page)


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
    assert "连接错误" in last_message_text(page)


async def test_connect_requires_complete_credentials():
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    fill_credentials(view, password="")

    await view._connect_to_server(None)

    assert "完整" in last_message_text(page)


# === SMB 来源交互测试 ===

import nextcloud_music_player.smb_client as smb_client_module


def switch_to_smb(view):
    """模拟把来源切换器切到 SMB（Flet 0.86 的 selected 是 list 而非 set）"""
    view.source_selector.selected = ["smb"]
    view._on_source_type_changed(None)


def fill_smb_settings(view, host="192.168.1.100", share="music",
                      user="u", password="p", port=445, domain=""):
    """模拟向导完成后连接页持有的 SMB 设置（地址框 + _smb_settings）"""
    view.smb_host_input.value = host
    view._smb_settings.update(
        host=host, share=share, username=user,
        password=password, port=port, domain=domain,
        sync_folder="/",
    )


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


async def test_connect_smb_requires_address():
    """未填地址直接连接：提示输入地址"""
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    switch_to_smb(view)
    view.smb_host_input.value = ""

    await view._connect_to_server(None)

    assert view.is_connected is False
    assert "请先输入 SMB 服务器地址" in last_message_text(page)


async def test_connect_smb_requires_share_from_wizard():
    """填了地址但未走过向导选共享：提示通过向导选择"""
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    switch_to_smb(view)
    fill_smb_settings(view, share="")  # 只填地址，未选共享

    await view._connect_to_server(None)

    assert view.is_connected is False
    assert "向导" in last_message_text(page)


async def test_smb_connect_reuses_saved_settings_without_wizard(monkeypatch):
    """已有主机和共享时，建立连接直接复用配置。"""
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    switch_to_smb(view)
    fill_smb_settings(view, host="nas.local", share="music")
    calls = []

    async def connect(event):
        calls.append("connect")

    monkeypatch.setattr(view, "_connect_to_server", connect)
    monkeypatch.setattr(view, "_open_smb_wizard", lambda: calls.append("wizard"))

    view._on_connect_clicked(None)
    await asyncio.sleep(0)

    assert calls == ["connect"]


def test_smb_changed_host_opens_wizard(monkeypatch):
    """地址改变后旧共享不可直接复用，应重新进入修改向导。"""
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    switch_to_smb(view)
    fill_smb_settings(view, host="old-nas", share="music")
    view.smb_host_input.value = "new-nas"
    calls = []
    monkeypatch.setattr(view, "_open_smb_wizard", lambda: calls.append("wizard"))

    view._on_connect_clicked(None)

    assert calls == ["wizard"]


def test_smb_edit_button_opens_wizard(monkeypatch):
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    switch_to_smb(view)
    fill_smb_settings(view)
    calls = []
    monkeypatch.setattr(view, "_open_smb_wizard", lambda: calls.append("wizard"))

    view.smb_edit_button.on_click(None)

    assert calls == ["wizard"]


def test_parse_smb_address_with_port():
    """地址框支持 host:port 形式，端口解析进设置"""
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    view.smb_host_input.value = "nas.local:139"

    host = view._parse_smb_address()

    assert host == "nas.local"
    assert view._smb_settings["port"] == 139


def test_parse_smb_address_rejects_bad_port():
    page = FakePage()
    view = make_connection_view(page, base_context(FakeConfigManager()), FakeViewManager())
    view.smb_host_input.value = "nas.local:abc"

    try:
        view._parse_smb_address()
        assert False, "应抛出 ValueError"
    except ValueError as ex:
        assert "主机名" in str(ex)


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
    fill_smb_settings(view)

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
    fill_smb_settings(view, host="nas.local", share="music")

    await view._connect_to_server(None)

    assert config.get("connection.source_type") == "smb"
    assert config.get("connection.smb.host") == "nas.local"
    assert config.get("connection.smb.share") == "music"
    assert config.get("connection.smb.port") == 445
    assert config.get("connection.smb.username") == "u"
    assert config.get("connection.smb.password") == "p"


def test_smb_wizard_complete_applies_config_and_connects():
    """向导完成：配置写入、客户端接管、跳转文件列表"""
    from nextcloud_music_player.views.components.smb_connect_wizard import (
        SMBConnectResult,
    )

    page = FakePage()
    view_manager = FakeViewManager()
    config = FakeConfigManager({"connection": {"remember_credentials": True}})
    client = FakeNextcloudClient(connect_ok=True)
    context = base_context(config)
    view = make_connection_view(page, context, view_manager)
    switch_to_smb(view)

    result = SMBConnectResult(
        host="nfs.home.daozzg.com", port=445, domain="WORKGROUP",
        username="u", password="p", share="music",
        sync_folder="/音乐", client=client,
    )
    view._on_smb_wizard_complete(result)

    assert context["nextcloud_client"] is client
    assert view.is_connected is True
    assert view_manager.switched_to == ["file_list"]
    assert config.get("connection.smb.host") == "nfs.home.daozzg.com"
    assert config.get("connection.smb.share") == "music"
    assert config.get("connection.smb.default_sync_folder") == "/音乐"
    assert view.smb_host_input.value == "nfs.home.daozzg.com"


def test_smb_wizard_complete_respects_no_remember():
    """未勾选记住密码：向导完成后不落盘明文凭据"""
    from nextcloud_music_player.views.components.smb_connect_wizard import (
        SMBConnectResult,
    )

    page = FakePage()
    config = FakeConfigManager({"connection": {"remember_credentials": True}})
    view = make_connection_view(page, base_context(config), FakeViewManager())
    switch_to_smb(view)
    view.remember_password_switch.value = False

    result = SMBConnectResult(
        host="nas", port=445, domain="", username="u", password="secret",
        share="music", sync_folder="/", client=object(),
    )
    view._on_smb_wizard_complete(result)

    assert config.get("connection.smb.username") == ""
    assert config.get("connection.smb.password") == ""
    assert config.get("connection.remember_credentials") is False
