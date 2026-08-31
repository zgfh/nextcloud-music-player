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
