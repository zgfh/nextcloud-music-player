"""
连接视图 Google Drive 来源交互测试：来源切换、凭据校验、授权流程、配置持久化
"""

import asyncio

from fakes import (
    FakeConfigManager,
    FakeNextcloudClient,
    FakePage,
    FakeViewManager,
    last_notification_text,
)

import nextcloud_music_player.gdrive_client as gdrive_module


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


def make_view(config=None, client=None):
    page = FakePage()
    view = make_connection_view(
        page,
        base_context(FakeConfigManager(config), nextcloud_client=client),
        FakeViewManager(),
    )
    return page, view


def switch_to_gdrive(view):
    """模拟把来源切换器切到 Google 云盘（Flet 0.86 的 selected 是 list）"""
    view.source_selector.selected = ["gdrive"]
    view._on_source_type_changed(None)


def fill_gdrive_credentials(
    view,
    client_id="cid.apps.googleusercontent.com",
    client_secret="GOCSPX-xxx",
    refresh_token="rt-ok",
):
    view.gdrive_client_id_input.value = client_id
    view.gdrive_client_secret_input.value = client_secret
    if refresh_token:
        view._gdrive_settings["refresh_token"] = refresh_token


class FakeReceiver:
    """LoopbackOAuthReceiver 替身：立即返回预设授权码"""

    redirect_uri = "http://127.0.0.1:54321"

    def start(self):
        pass

    def close(self):
        pass

    def wait_for_code(self, timeout=None):
        return "auth-code-123"


# === 来源切换 ===


async def test_source_switch_to_gdrive_toggles_forms_and_saves_choice():
    page, view = make_view()
    config = view.app_context["config_manager"]

    assert view.gdrive_form_card.visible is False
    assert view.nextcloud_form_card.visible is True

    switch_to_gdrive(view)

    assert view.gdrive_form_card.visible is True
    assert view.nextcloud_form_card.visible is False
    assert view.smb_form_card.visible is False
    assert view.title_text.value == "GOOGLE DRIVE"
    assert config.get("connection.source_type") == "gdrive"


async def test_build_with_gdrive_source_shows_authorized_state():
    page, view = make_view(
        {
            "connection": {
                "source_type": "gdrive",
                "gdrive": {
                    "client_id": "cid",
                    "client_secret": "sec",
                    "refresh_token": "kept-rt",
                    "default_sync_folder": "FOLDER1",
                },
            }
        }
    )

    assert view.gdrive_form_card.visible is True
    assert view.gdrive_auth_status.value == "已授权 ✓"
    assert view.gdrive_sync_folder_input.value == "FOLDER1"


# === 连接前校验 ===


async def test_connect_gdrive_requires_credentials():
    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view, client_id="", client_secret="")

    await view._connect_to_server(None)

    assert view.is_connected is False
    assert "Client ID" in last_notification_text(page)


async def test_connect_gdrive_requires_authorization():
    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view, refresh_token="")  # 填了 ID/Secret 但未授权

    await view._connect_to_server(None)

    assert view.is_connected is False
    assert "授权" in last_notification_text(page)


# === 连接流程 ===


async def test_connect_gdrive_success_flow(monkeypatch):
    page, view = make_view()
    view_manager = view.view_manager
    client = FakeNextcloudClient(connect_ok=True)
    monkeypatch.setattr(gdrive_module, "GoogleDriveClient", lambda **kwargs: client)
    switch_to_gdrive(view)
    fill_gdrive_credentials(view)

    await view._connect_to_server(None)

    assert view.is_connected is True
    assert view.app_context["nextcloud_client"] is client
    assert view_manager.switched_to == ["file_list"]


def test_build_client_passes_tokens_and_callback(monkeypatch):
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return FakeNextcloudClient(connect_ok=True)

    monkeypatch.setattr(gdrive_module, "GoogleDriveClient", fake_client)
    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view)
    view._gdrive_settings["access_token"] = "at-1"
    view._gdrive_settings["token_expiry"] = 123.5

    view._build_client_from_form()

    assert captured["client_id"] == "cid.apps.googleusercontent.com"
    assert captured["client_secret"] == "GOCSPX-xxx"
    assert captured["refresh_token"] == "rt-ok"
    assert captured["access_token"] == "at-1"
    assert captured["token_expiry"] == 123.5
    assert captured["on_tokens_updated"] == view._persist_gdrive_tokens


# === 授权流程 ===


async def test_authorize_gdrive_completes_and_persists(monkeypatch):
    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view, refresh_token="")  # 尚未授权
    view.gdrive_sync_folder_input.value = "FOLDER9"

    monkeypatch.setattr(gdrive_module, "LoopbackOAuthReceiver", lambda: FakeReceiver())
    monkeypatch.setattr(
        gdrive_module,
        "build_authorization_url",
        lambda client_id, redirect_uri: "https://auth.example/consent",
    )
    monkeypatch.setattr(
        gdrive_module,
        "exchange_authorization_code",
        lambda *args, **kwargs: {
            "access_token": "at-new",
            "refresh_token": "rt-new",
            "expires_in": 3600,
        },
    )

    await view._authorize_gdrive()

    assert page.launched_urls == ["https://auth.example/consent"]
    assert view._gdrive_settings["refresh_token"] == "rt-new"
    assert view._gdrive_settings["access_token"] == "at-new"
    assert view.gdrive_auth_status.value == "已授权 ✓"
    assert view.gdrive_authorize_button.disabled is False

    config = view.app_context["config_manager"]
    assert config.get("connection.gdrive.client_id") == "cid.apps.googleusercontent.com"
    assert config.get("connection.gdrive.client_secret") == "GOCSPX-xxx"
    assert config.get("connection.gdrive.refresh_token") == "rt-new"
    assert config.get("connection.gdrive.default_sync_folder") == "FOLDER9"
    assert "授权成功" in last_notification_text(page)


async def test_authorize_gdrive_requires_credentials_first():
    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view, client_id="", client_secret="")

    await view._authorize_gdrive()

    assert page.launched_urls == []
    assert "Client ID" in last_notification_text(page)


async def test_authorize_gdrive_cancelled_shows_error(monkeypatch):
    class CancellingReceiver(FakeReceiver):
        def wait_for_code(self, timeout=None):
            raise TimeoutError("等待浏览器完成授权超时")

    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view, refresh_token="")

    monkeypatch.setattr(
        gdrive_module, "LoopbackOAuthReceiver", lambda: CancellingReceiver()
    )
    monkeypatch.setattr(
        gdrive_module,
        "build_authorization_url",
        lambda client_id, redirect_uri: "https://auth.example/consent",
    )

    await view._authorize_gdrive()

    assert view._gdrive_settings.get("refresh_token", "") == ""
    assert view.gdrive_auth_status.value == "未授权"
    assert "授权失败" in last_notification_text(page)


def test_persist_gdrive_tokens_respects_no_remember():
    page, view = make_view()
    view.remember_password_switch.value = False
    config = view.app_context["config_manager"]

    view._persist_gdrive_tokens(
        {"access_token": "at", "refresh_token": "rt", "token_expiry": 1.5}
    )

    assert view._gdrive_settings["refresh_token"] == "rt"  # 内存中保留
    assert config.get("connection.gdrive.refresh_token", "") == ""  # 不落盘
    assert config.get("connection.gdrive.access_token", "") == ""


def test_persist_gdrive_tokens_saves_when_remembering():
    page, view = make_view()
    view.remember_password_switch.value = True
    config = view.app_context["config_manager"]

    view._persist_gdrive_tokens(
        {"access_token": "at", "refresh_token": "rt", "token_expiry": 1.5}
    )

    assert config.get("connection.gdrive.refresh_token") == "rt"
    assert config.get("connection.gdrive.access_token") == "at"
    assert config.get("connection.gdrive.token_expiry") == 1.5


# === 配置保存 ===


def test_save_config_persists_gdrive_fields():
    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view)
    view._gdrive_settings["access_token"] = "at-1"
    view._gdrive_settings["token_expiry"] = 99.0
    view.gdrive_sync_folder_input.value = "FOLDER7"

    view._save_config()

    config = view.app_context["config_manager"]
    assert config.get("connection.source_type") == "gdrive"
    assert config.get("connection.gdrive.client_id") == "cid.apps.googleusercontent.com"
    assert config.get("connection.gdrive.client_secret") == "GOCSPX-xxx"
    assert config.get("connection.gdrive.refresh_token") == "rt-ok"
    assert config.get("connection.gdrive.access_token") == "at-1"
    assert config.get("connection.gdrive.token_expiry") == 99.0
    assert config.get("connection.gdrive.default_sync_folder") == "FOLDER7"


def test_save_config_without_remember_blanks_gdrive_secrets():
    page, view = make_view()
    switch_to_gdrive(view)
    fill_gdrive_credentials(view, client_secret="super-secret")
    view.remember_password_switch.value = False

    view._save_config()

    config = view.app_context["config_manager"]
    assert config.get("connection.gdrive.client_id") == "cid.apps.googleusercontent.com"
    assert config.get("connection.gdrive.client_secret") == ""
    assert config.get("connection.gdrive.refresh_token") == ""


# === 文件夹浏览 ===


async def test_browse_folder_gdrive_opens_selector():
    page, view = make_view(client=FakeNextcloudClient(directories={"/": []}))
    switch_to_gdrive(view)
    view.gdrive_sync_folder_input.value = ""

    view._browse_folder(None)
    await asyncio.sleep(0.05)

    assert len(page.dialogs) == 1
