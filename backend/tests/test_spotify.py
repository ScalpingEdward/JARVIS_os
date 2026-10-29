import httpx
import pytest

from app.assistant import tools
from app.spotify import client as sp


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "sec")
    sp._store("refresh-1")
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, dict(req.url.params), req.content))
        if req.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if req.url.path == "/v1/me/playlists":
            return httpx.Response(200, json={"items": [{"name": "Gym Hard", "uri": "spotify:playlist:gym"}]})
        if req.url.path == "/v1/search":
            return httpx.Response(200, json={"tracks": {"items": [{"name": "One Dance", "uri": "spotify:track:1",
                                                                   "artists": [{"name": "Drake"}]}]}})
        if req.url.path == "/v1/me/player" and req.method == "GET":
            return httpx.Response(200, json={"is_playing": True, "item": {"name": "One Dance", "artists": [{"name": "Drake"}]},
                                             "device": {"name": "DESKTOP", "volume_percent": 40}})
        return httpx.Response(204)

    monkeypatch.setattr(sp.Spotify, "__init__", lambda self, client=None: (
        setattr(self, "http", httpx.Client(transport=httpx.MockTransport(handler))), setattr(self, "_access", ""), setattr(self, "_until", 0.0))[0])
    return calls


def test_auron_plays_a_song_his_playlist_and_says_what_plays(fake):
    out, failed = tools.run("spotify", {"action": "play", "query": "drake one dance"})
    assert not failed and "One Dance von Drake" in out
    assert any(c[1] == "/v1/me/player/play" and b'"uris"' in c[3] for c in fake)
    out, _ = tools.run("spotify", {"action": "play", "query": "gym", "kind": "playlist"})
    assert "deine Playlist Gym Hard" in out and any(b"spotify:playlist:gym" in c[3] for c in fake)
    out, _ = tools.run("spotify", {"action": "now"})
    assert '"title": "One Dance"' in out and '"device": "DESKTOP"' in out
    out, _ = tools.run("spotify", {"action": "volume", "volume": 150})
    assert any(c[2].get("volume_percent") == "100" for c in fake)


def test_without_setup_it_says_what_is_missing(monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    out, failed = tools.run("spotify", {"action": "pause"})
    assert not failed and "nicht eingerichtet" in out


def test_the_dashboard_panel_shows_the_song_and_steers_it(fake, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.spotify import api
    monkeypatch.setattr(api, "_sp", None)   # the shared client, made fresh on the fake
    app = FastAPI()
    app.include_router(api.router)
    web = TestClient(app)

    now = web.get("/v1/spotify/player").json()
    assert now["playing"] and now["title"] == "One Dance" and now["artist"] == "Drake" and now["volume"] == 40
    assert web.get("/v1/spotify/playlists").json()["playlists"][0] == {"name": "Gym Hard", "uri": "spotify:playlist:gym", "cover": None}

    assert web.post("/v1/spotify/control", json={"action": "pause"}).json()["ok"]
    web.post("/v1/spotify/control", json={"action": "play_uri", "uri": "spotify:playlist:gym", "device_id": "tv"})
    assert any(c[1] == "/v1/me/player/play" and c[2].get("device_id") == "tv" and b"spotify:playlist:gym" in c[3] for c in fake)
    web.post("/v1/spotify/control", json={"action": "transfer", "device_id": "phone"})
    assert any(c[0] == "PUT" and c[1] == "/v1/me/player" and b'"phone"' in c[3] for c in fake)
    # one token for the whole panel, not one per click
    assert sum(1 for c in fake if c[1] == "/api/token") == 1
    # a made-up address is refused before it reaches Spotify
    assert web.post("/v1/spotify/control", json={"action": "play_uri", "uri": "https://evil"}).status_code == 502


def test_a_playlist_opens_with_its_songs_and_one_of_them_plays_with_the_playlist_after_it(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.spotify import api
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "sec")
    sp._store("refresh-1")
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, dict(req.url.params), req.content))
        if req.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if req.url.path == "/v1/playlists/gym":
            return httpx.Response(200, json={"name": "Gym Hard", "uri": "spotify:playlist:gym", "images": [{"url": "big.jpg"}]})
        if req.url.path == "/v1/playlists/gym/tracks":     # the old path: closed for new apps
            return httpx.Response(403, json={"error": {"status": 403, "message": "Forbidden"}})
        if req.url.path == "/v1/playlists/followed":
            return httpx.Response(200, json={"name": "Boxing", "uri": "spotify:playlist:followed", "images": []})
        if req.url.path == "/v1/playlists/followed/items":  # someone else's playlist
            return httpx.Response(403, json={"error": {"status": 403, "message": "Forbidden"}})
        if req.url.path == "/v1/playlists/gym/items":
            return httpx.Response(200, json={"next": None, "items": [
                {"item": {"name": "Till I Collapse", "uri": "spotify:track:a", "duration_ms": 297000,
                           "artists": [{"name": "Eminem"}], "album": {"images": [{"url": "640.jpg"}, {"url": "64.jpg"}]}}},
                {"track": None},                                   # a song deleted from Spotify
                {"item": {"name": "Lose Yourself", "uri": "spotify:track:b", "duration_ms": 326000, "artists": [{"name": "Eminem"}]}}]})
        return httpx.Response(204)

    monkeypatch.setattr(sp.Spotify, "__init__", lambda self, client=None: (
        setattr(self, "http", httpx.Client(transport=httpx.MockTransport(handler))), setattr(self, "_access", ""), setattr(self, "_until", 0.0))[0])
    monkeypatch.setattr(api, "_sp", None)
    app = FastAPI()
    app.include_router(api.router)
    web = TestClient(app)

    p = web.get("/v1/spotify/playlists/gym").json()
    assert p["name"] == "Gym Hard" and [t["name"] for t in p["tracks"]] == ["Till I Collapse", "Lose Yourself"]
    assert p["tracks"][0]["cover"] == "64.jpg" and p["tracks"][1]["cover"] is None and not p["locked"]
    # one he only follows: Spotify keeps its songs from new apps -- it opens locked, playable as a whole
    f = web.get("/v1/spotify/playlists/followed").json()
    assert f["locked"] and f["tracks"] == [] and f["name"] == "Boxing"

    web.post("/v1/spotify/control", json={"action": "play_uri", "uri": "spotify:playlist:gym", "offset_uri": "spotify:track:b"})
    assert any(c[1] == "/v1/me/player/play" and b'"offset"' in c[3] and b"spotify:track:b" in c[3] and b"spotify:playlist:gym" in c[3] for c in calls)
    # a made-up id never becomes part of a Spotify address
    assert web.get("/v1/spotify/playlists/..%2Fme").status_code in (404, 502)
