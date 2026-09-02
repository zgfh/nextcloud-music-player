"""MusicBrainz 文字查询解析与评分测试，不访问真实网络。"""

import requests


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


def test_503_is_retried_then_succeeds(monkeypatch):
    from nextcloud_music_player.services import musicbrainz_service as module

    attempts = 0

    class Response:
        status_code = 503
        headers = {}

        def raise_for_status(self):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                error = requests.HTTPError("503")
                error.response = self
                raise error

        def json(self):
            return {"recordings": []}

    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(module.MusicBrainzService, "_wait_for_rate_limit", staticmethod(lambda: None))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    assert module.MusicBrainzService()._search_sync("五月天", "倔强") == []
    assert attempts == 3


def test_repeated_503_raises_friendly_unavailable_error(monkeypatch):
    from nextcloud_music_player.services import musicbrainz_service as module

    def get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 503
        raise requests.HTTPError("503", response=response)

    monkeypatch.setattr(module.requests, "get", get)
    monkeypatch.setattr(module.MusicBrainzService, "_wait_for_rate_limit", staticmethod(lambda: None))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    try:
        module.MusicBrainzService()._search_sync("五月天", "倔强")
        assert False, "expected MusicBrainzUnavailableError"
    except module.MusicBrainzUnavailableError as exc:
        assert "暂不可用" in str(exc)
