"""
SMBClient 单元测试 - 不发起真实网络请求
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from nextcloud_music_player.smb_client import (
        SMBClient,
        is_music_file,
        to_smb_path,
        format_smb_time,
        _is_not_found_error,
    )
    PYSMB_AVAILABLE = True
except ImportError:
    PYSMB_AVAILABLE = False


class FakeSMBError(Exception):
    """模拟 pysmb 的 SMBError（带 status 属性）"""

    def __init__(self, status=""):
        super().__init__(status)
        self.status = status


@unittest.skipUnless(PYSMB_AVAILABLE, "pysmb 未安装")
class TestSmbPathHelpers(unittest.TestCase):
    """路径规范与格式化辅助函数"""

    def test_to_smb_path_root(self):
        self.assertEqual(to_smb_path(""), "/")
        self.assertEqual(to_smb_path("/"), "/")
        self.assertEqual(to_smb_path(None), "/")

    def test_to_smb_path_subfolder(self):
        self.assertEqual(to_smb_path("music"), "/music")
        self.assertEqual(to_smb_path("/music/"), "/music")
        self.assertEqual(to_smb_path("/music/流行"), "/music/流行")
        self.assertEqual(to_smb_path(" /a/b/ "), "/a/b")

    def test_is_music_file(self):
        self.assertTrue(is_music_file("song.mp3"))
        self.assertTrue(is_music_file("Song.MP3"))
        self.assertTrue(is_music_file("track.flac"))
        self.assertTrue(is_music_file("a.b.m4a"))
        self.assertFalse(is_music_file("cover.jpg"))
        self.assertFalse(is_music_file("noext"))
        self.assertFalse(is_music_file(""))

    def test_format_smb_time(self):
        dt = datetime(2026, 8, 22, 10, 30, 0)
        self.assertEqual(format_smb_time(dt), "2026-08-22T10:30:00")
        # epoch 秒也能转换
        self.assertTrue(format_smb_time(1700000000).startswith("20"))
        self.assertEqual(format_smb_time(None), "")
        self.assertEqual(format_smb_time("not-a-time"), "")

    def test_is_not_found_error(self):
        self.assertTrue(_is_not_found_error(FakeSMBError("STATUS_NO_SUCH_FILE")))
        self.assertTrue(_is_not_found_error(FakeSMBError("STATUS_OBJECT_PATH_NOT_FOUND")))
        self.assertFalse(_is_not_found_error(FakeSMBError("STATUS_LOGON_FAILURE")))
        self.assertFalse(_is_not_found_error(ConnectionError("boom")))


@unittest.skipUnless(PYSMB_AVAILABLE, "pysmb 未安装")
class TestSMBClientConstruction(unittest.TestCase):
    """构造参数清理（不发起网络连接）"""

    def _make_client(self, **kwargs):
        defaults = dict(host="192.168.1.100", username="user", password="pass",
                        share="music")
        defaults.update(kwargs)
        return SMBClient(**defaults)

    def test_share_name_cleaned(self):
        client = self._make_client(share="/music/")
        self.assertEqual(client.share, "music")
        client = self._make_client(share="\\\\music\\")
        self.assertEqual(client.share, "music")

    def test_port_fallback(self):
        self.assertEqual(self._make_client(port=None).port, 445)
        self.assertEqual(self._make_client(port="abc").port, 445)
        self.assertEqual(self._make_client(port="139").port, 139)

    def test_domain_default(self):
        self.assertEqual(self._make_client(domain="").domain, "WORKGROUP")
        self.assertEqual(self._make_client(domain="HOME").domain, "HOME")

    def test_guest_credentials_allowed(self):
        client = self._make_client(username="", password="")
        self.assertEqual(client.username, "")
        self.assertEqual(client.password, "")

    def test_friendly_error_classification(self):
        client = self._make_client()
        msg = client._friendly_error(ConnectionResetError("reset by peer"))
        self.assertIn("SMB3", msg)

        msg = client._friendly_error(FakeSMBError("STATUS_LOGON_FAILURE"))
        self.assertIn("认证失败", msg)

        class FakeTimeout(Exception):
            pass

        FakeTimeout.__name__ = "SMBTimeout"
        msg = client._friendly_error(FakeTimeout("timed out"))
        self.assertIn("超时", msg)


@unittest.skipUnless(PYSMB_AVAILABLE, "pysmb 未安装")
class TestSmbDefaultConfig(unittest.TestCase):
    """配置默认值包含 SMB 节"""

    def test_default_config_contains_smb(self):
        from nextcloud_music_player.config_manager import ConfigManager
        cm = ConfigManager()
        conn = cm.default_config.get("connection", {})
        self.assertEqual(conn.get("source_type"), "nextcloud")
        smb = conn.get("smb", {})
        self.assertIn("host", smb)
        self.assertIn("port", smb)
        self.assertIn("share", smb)
        self.assertIn("default_sync_folder", smb)
        self.assertEqual(smb.get("port"), 445)


if __name__ == "__main__":
    unittest.main()
