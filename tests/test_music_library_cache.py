from nextcloud_music_player.music_library import MusicLibrary


def test_remove_cached_songs_deletes_only_selected_and_keeps_metadata(tmp_path):
    library = MusicLibrary.__new__(MusicLibrary)
    library.music_dir = tmp_path / "music"
    library.music_dir.mkdir()
    library.music_list_file = tmp_path / "music_list.json"
    selected = library.music_dir / "selected.mp3"
    retained = library.music_dir / "retained.mp3"
    selected.write_bytes(b"a" * 10)
    retained.write_bytes(b"b" * 20)
    library.songs = {
        "selected.mp3": {
            "remote_path": "/selected.mp3",
            "is_downloaded": True,
            "filepath": str(selected),
            "download_time": "now",
        },
        "retained.mp3": {
            "remote_path": "/retained.mp3",
            "is_downloaded": True,
            "filepath": str(retained),
        },
    }

    deleted, freed = library.remove_cached_songs(["selected.mp3"])

    assert (deleted, freed) == (1, 10)
    assert not selected.exists()
    assert retained.exists()
    assert library.songs["selected.mp3"]["remote_path"] == "/selected.mp3"
    assert library.songs["selected.mp3"]["is_downloaded"] is False
    assert library.songs["selected.mp3"]["filepath"] is None


def test_remove_cached_songs_refuses_path_outside_music_directory(tmp_path):
    library = MusicLibrary.__new__(MusicLibrary)
    library.music_dir = tmp_path / "music"
    library.music_dir.mkdir()
    library.music_list_file = tmp_path / "music_list.json"
    outside = tmp_path / "outside.mp3"
    outside.write_bytes(b"keep")
    library.songs = {
        "outside.mp3": {"is_downloaded": True, "filepath": str(outside)}
    }

    assert library.remove_cached_songs(["outside.mp3"]) == (0, 0)
    assert outside.exists()


def test_cached_songs_count_uses_real_audio_files_on_disk(tmp_path):
    library = MusicLibrary.__new__(MusicLibrary)
    library.music_dir = tmp_path / "music"
    library.music_dir.mkdir()
    library.music_list_file = tmp_path / "music_list.json"
    indexed = library.music_dir / "indexed.mp3"
    orphan = library.music_dir / "orphan.flac"
    stale = library.music_dir / "missing.mp3"
    indexed.write_bytes(b"a" * 10)
    orphan.write_bytes(b"b" * 20)
    library.songs = {
        "indexed.mp3": {"is_downloaded": True, "filepath": str(indexed)},
        "missing.mp3": {"is_downloaded": True, "filepath": str(stale)},
    }

    cached = library.get_cached_songs()

    assert [item["name"] for item in cached] == ["indexed.mp3", "orphan.flac"]
    assert sum(item["size"] for item in cached) == 30


def test_remove_orphaned_cached_song(tmp_path):
    library = MusicLibrary.__new__(MusicLibrary)
    library.music_dir = tmp_path / "music"
    library.music_dir.mkdir()
    library.music_list_file = tmp_path / "music_list.json"
    orphan = library.music_dir / "orphan.mp3"
    orphan.write_bytes(b"x" * 12)
    library.songs = {}

    assert library.remove_cached_songs(["orphan.mp3"]) == (1, 12)
    assert not orphan.exists()


def test_same_filename_keeps_multiple_origins_and_stable_primary(tmp_path):
    library = MusicLibrary.__new__(MusicLibrary)
    library.music_dir = tmp_path / "music"
    library.music_dir.mkdir()
    library.music_list_file = tmp_path / "music_list.json"
    library.songs = {}

    library.add_remote_song(
        "same.mp3", "/next/same.mp3", source_type="nextcloud",
        sync_folder="/Music",
    )
    library.add_remote_song(
        "same.mp3", "drive-file-id", source_type="gdrive",
        sync_folder="drive-folder-id",
    )

    song = library.songs["same.mp3"]
    assert song["source_type"] == "nextcloud"
    assert song["remote_path"] == "/next/same.mp3"
    assert [(o["source_type"], o["remote_path"]) for o in song["origins"]] == [
        ("nextcloud", "/next/same.mp3"),
        ("gdrive", "drive-file-id"),
    ]

    # 重复同步同一来源只更新候选，不追加重复项。
    library.add_remote_song(
        "same.mp3", "drive-file-id", size=123, source_type="gdrive",
        sync_folder="drive-folder-id",
    )
    assert len(song["origins"]) == 2
    assert song["origins"][1]["size"] == 123


def test_custom_song_title_is_saved_without_renaming_file(tmp_path):
    library = MusicLibrary.__new__(MusicLibrary)
    library.music_dir = tmp_path / "music"
    library.music_dir.mkdir()
    library.music_list_file = tmp_path / "music_list.json"
    library.songs = {}
    library.add_remote_song("original.mp3", "/remote/original.mp3")

    assert library.update_song_metadata("original.mp3", {
        "custom_title": "自定义歌名", "artist": "歌手", "album": "专辑",
        "year": "2026", "musicbrainz_mbid": "mbid-1",
    }) is True

    assert "original.mp3" in library.songs
    assert library.songs["original.mp3"]["custom_title"] == "自定义歌名"
    assert library.songs["original.mp3"]["remote_path"] == "/remote/original.mp3"
def test_filename_metadata_parser_handles_track_number_and_compact_separator(
    tmp_path, monkeypatch
):
    from nextcloud_music_player.music_library import MusicLibrary

    library = MusicLibrary.__new__(MusicLibrary)
    assert library.extract_song_info_from_filename("0172.五月天-倔强.mp3") == {
        "title": "倔强",
        "artist": "五月天",
        "album": "未知专辑",
    }

