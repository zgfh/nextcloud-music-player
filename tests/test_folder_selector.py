"""
文件夹选择器交互测试：对话框打开、目录导航、404 回退、选择/取消
（覆盖 iOS 上崩溃过的 show_dialog/pop_dialog 路径）
"""

import asyncio

from fakes import FakeNextcloudClient, FakePage


def make_selector(page, client, initial_path="/"):
    from nextcloud_music_player.views.folder_selector import FolderSelector
    return FolderSelector(page, client, initial_path)


async def test_show_dialog_opens_and_lists_folders():
    page = FakePage()
    client = FakeNextcloudClient(directories={"/": [{"name": "Music"}, {"name": "mp3"}]})
    selector = make_selector(page, client)

    selector.show_dialog(lambda path: None)
    await asyncio.sleep(0.05)  # 等待 _load_folders 任务

    assert len(page.dialogs) == 1                      # page.show_dialog 被调用
    assert [c.title.value for c in selector.folder_list.controls] == ["Music", "mp3"]


async def test_enter_folder_and_go_back_navigation():
    page = FakePage()
    client = FakeNextcloudClient(directories={
        "/": [{"name": "Music"}],
        "/Music": [{"name": "Jazz"}],
    })
    selector = make_selector(page, client)
    selector.show_dialog(lambda path: None)
    await asyncio.sleep(0.05)

    selector._enter_folder("Music")
    await asyncio.sleep(0.05)
    assert selector.current_path == "/Music"
    assert selector.path_display.value == "/Music"
    assert [c.title.value for c in selector.folder_list.controls] == ["Jazz"]

    selector._go_back(None)
    await asyncio.sleep(0.05)
    assert selector.current_path == "/"


async def test_missing_directory_falls_back_to_root():
    """起始目录 404 时自动回退根目录，而不是显示加载失败"""
    page = FakePage()
    client = FakeNextcloudClient(
        directories={"/": [{"name": "Music"}]},
        dir_errors={"/gone": RuntimeError("404")},
    )
    selector = make_selector(page, client, initial_path="/gone")

    selector.show_dialog(lambda path: None)
    await asyncio.sleep(0.05)

    assert selector.current_path == "/"
    assert selector.path_display.value == "/"
    assert [c.title.value for c in selector.folder_list.controls] == ["Music"]


async def test_select_current_closes_dialog_and_returns_path():
    page = FakePage()
    client = FakeNextcloudClient(directories={"/": []})
    selector = make_selector(page, client)
    selected = []
    selector.show_dialog(selected.append)
    await asyncio.sleep(0.05)

    selector._enter_folder("Music")
    selector._select_current(None)

    assert page.popped_dialogs == 1                     # page.pop_dialog 被调用
    assert selected == ["/Music"]


async def test_cancel_closes_dialog_without_callback():
    page = FakePage()
    client = FakeNextcloudClient(directories={"/": []})
    selector = make_selector(page, client)
    selected = []
    selector.show_dialog(selected.append)
    await asyncio.sleep(0.05)

    selector._cancel(None)

    assert page.popped_dialogs == 1
    assert selected == []
