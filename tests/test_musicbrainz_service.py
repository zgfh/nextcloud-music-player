"""MusicBrainz 文字查询解析与评分测试，不访问真实网络。"""


def test_search_builds_identified_request_and_parses_candidates(monkeypatch):
    from nextcloud_music_player.services import musicbrainz_service as module

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "recordings": [{
                    "id": "mbid-1", "score": 98, "title": "晴天",
                    "first-release-date": "2003-07-31",
                    "artist-credit": [{"name": "周杰伦"}],
                    "releases": [{"title": "叶惠美", "date": "2003-07-31"}],
                }]
            }

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", get)
    monkeypatch.setattr(
        module.MusicBrainzService, "_wait_for_rate_limit", staticmethod(lambda: None)
    )
    service = module.MusicBrainzService()

    results = service._search_sync("周杰伦", "晴天")

    assert results[0]["title"] == "晴天"
    assert results[0]["artist"] == "周杰伦"
    assert results[0]["album"] == "叶惠美"
    assert results[0]["year"] == "2003"
    assert results[0]["mbid"] == "mbid-1"
    assert calls[0][1]["headers"]["User-Agent"].startswith("NextCloudMusicPlayer/")
    assert calls[0][1]["params"]["fmt"] == "json"


def test_empty_query_does_not_call_network(monkeypatch):
    from nextcloud_music_player.services import musicbrainz_service as module

    monkeypatch.setattr(
        module.requests, "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")),
    )
    assert module.MusicBrainzService()._search_sync("", "") == []
