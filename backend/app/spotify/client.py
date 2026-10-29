"""Spotify for AURON: play, pause, skip, volume, "spiel X", what is playing -- on whatever device
Brano has Spotify open (PC, phone, speaker). Needs Spotify Premium (remote control is Premium only).

Set up once: an app at developer.spotify.com (Client ID and Secret into .env as SPOTIFY_CLIENT_ID /
SPOTIFY_CLIENT_SECRET, redirect URI http://127.0.0.1:8080/api/v1/spotify/callback), then one sign-in at
/api/v1/spotify/login. The refresh token Spotify hands back is kept in AURON's database, never in chat.
"""
from __future__ import annotations

import base64
import os
import time
import urllib.parse
from datetime import datetime, timezone

import httpx

from app.db import SessionLocal
from app.db_models import AppSettingRow

API = "https://api.spotify.com/v1"
AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
REDIRECT = "http://127.0.0.1:8080/api/v1/spotify/callback"
SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private"
KEY = "spotify.refresh_token"


class SpotifyError(RuntimeError):
    pass


def _ids() -> tuple[str, str]:
    cid, sec = os.getenv("SPOTIFY_CLIENT_ID", ""), os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not cid or not sec:
        raise SpotifyError("Spotify ist nicht eingerichtet: SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET fehlen in der .env")
    return cid, sec


def login_url(state: str = "auron") -> str:
    cid, _ = _ids()
    return AUTH + "?" + urllib.parse.urlencode({"client_id": cid, "response_type": "code", "redirect_uri": REDIRECT,
                                                "scope": SCOPES, "state": state})


def _refresh_token() -> str | None:
    with SessionLocal() as s:
        row = s.get(AppSettingRow, KEY)
    return row.value if row else None


def _store(token: str) -> None:
    with SessionLocal() as s:
        s.merge(AppSettingRow(key=KEY, value=token, updated_at=datetime.now(timezone.utc)))
        s.commit()


def connected() -> bool:
    return bool(_refresh_token())


class Spotify:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.http = client or httpx.Client(timeout=15)
        self._access, self._until = "", 0.0

    def _token_call(self, data: dict) -> dict:
        cid, sec = _ids()
        auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
        r = self.http.post(TOKEN, data=data, headers={"Authorization": f"Basic {auth}"})
        if r.status_code >= 400:
            raise SpotifyError(f"Spotify-Anmeldung: {r.status_code} {r.text[:200]}")
        return r.json()

    def finish_login(self, code: str) -> None:
        d = self._token_call({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT})
        _store(d["refresh_token"])

    def _bearer(self) -> str:
        if self._access and time.time() < self._until - 60:
            return self._access
        rt = _refresh_token()
        if not rt:
            raise SpotifyError("Spotify ist noch nicht verbunden: einmal http://127.0.0.1:8080/api/v1/spotify/login öffnen")
        d = self._token_call({"grant_type": "refresh_token", "refresh_token": rt})
        if d.get("refresh_token"):
            _store(d["refresh_token"])
        self._access, self._until = d["access_token"], time.time() + d.get("expires_in", 3600)
        return self._access

    def _call(self, method: str, path: str, **kw) -> dict | None:
        r = self.http.request(method, API + path, headers={"Authorization": f"Bearer {self._bearer()}"}, **kw)
        if r.status_code == 404 and "NO_ACTIVE_DEVICE" in r.text:
            raise SpotifyError("Kein aktives Spotify-Gerät: Spotify auf PC oder Handy einmal öffnen")
        if r.status_code == 403 and "PREMIUM" in r.text.upper():
            raise SpotifyError("Spotify erlaubt die Steuerung nur mit Premium")
        if r.status_code >= 400:
            raise SpotifyError(f"Spotify {r.status_code}: {r.text[:200]}")
        if r.content and r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return None

    # ---- what AURON can do ---------------------------------------------------------------------
    def now(self) -> dict:
        d = self._call("GET", "/me/player")
        if not d or not d.get("item"):
            return {"playing": False, "note": "gerade läuft nichts"}
        it, dev = d["item"], d.get("device") or {}
        return {"playing": d.get("is_playing"), "title": it.get("name"),
                "artist": ", ".join(a["name"] for a in it.get("artists", [])),
                "device": dev.get("name"), "volume": dev.get("volume_percent")}

    def devices(self) -> list[dict]:
        return [{"name": x["name"], "type": x["type"], "active": x["is_active"], "id": x["id"]}
                for x in (self._call("GET", "/me/player/devices") or {}).get("devices", [])]

    def _device(self, name: str | None) -> str | None:
        if not name:
            return None
        hit = [d for d in self.devices() if name.lower() in d["name"].lower()]
        if not hit:
            raise SpotifyError(f"kein Spotify-Gerät namens {name!r}")
        return hit[0]["id"]

    def play(self, query: str | None = None, kind: str = "track", device: str | None = None) -> dict:
        """Without a query: resume. kind: track, artist, album, playlist (his own playlists first)."""
        params = {"device_id": self._device(device)} if device else {}
        if not query:
            self._call("PUT", "/me/player/play", params=params)
            return {"ok": True, "did": "weiter abgespielt"}
        uri, label = self._find(query, kind)
        body = {"uris": [uri]} if uri.startswith("spotify:track:") else {"context_uri": uri}
        self._call("PUT", "/me/player/play", params=params, json=body)
        return {"ok": True, "did": f"spielt {label}"}

    def _find(self, query: str, kind: str) -> tuple[str, str]:
        if kind == "playlist":   # his own first: "spiel meine Gym-Playlist"
            mine = (self._call("GET", "/me/playlists", params={"limit": 50}) or {}).get("items", [])
            hit = next((p for p in mine if p and query.lower() in (p.get("name") or "").lower()), None)
            if hit:
                return hit["uri"], f"deine Playlist {hit['name']}"
        d = self._call("GET", "/search", params={"q": query, "type": kind, "limit": 1}) or {}
        items = [x for x in ((d.get(kind + "s") or {}).get("items") or []) if x]
        if not items:
            raise SpotifyError(f"nichts gefunden für {query!r}")
        it = items[0]
        who = ", ".join(a["name"] for a in it.get("artists", [])) if it.get("artists") else ""
        return it["uri"], it["name"] + (f" von {who}" if who else "")

    def pause(self) -> dict:
        self._call("PUT", "/me/player/pause")
        return {"ok": True, "did": "pausiert"}

    def next(self) -> dict:
        self._call("POST", "/me/player/next")
        return {"ok": True, "did": "nächster Titel"}

    def previous(self) -> dict:
        self._call("POST", "/me/player/previous")
        return {"ok": True, "did": "voriger Titel"}

    def volume(self, percent: int) -> dict:
        p = max(0, min(100, int(percent)))
        self._call("PUT", "/me/player/volume", params={"volume_percent": p})
        return {"ok": True, "did": f"Lautstärke {p} %"}

    # ---- the dashboard's Spotify panel (frontend/media.js) -------------------------------------
    def player(self) -> dict:
        """What the panel shows: the song with its cover and progress, the device and its volume."""
        d = self._call("GET", "/me/player")
        if not d or not d.get("item"):
            return {"playing": False}
        it, dev = d["item"], d.get("device") or {}
        images = (it.get("album") or {}).get("images") or []
        return {"playing": bool(d.get("is_playing")), "title": it.get("name"), "uri": it.get("uri"),
                "context": (d.get("context") or {}).get("uri"),
                "artist": ", ".join(a["name"] for a in it.get("artists", [])),
                "album": (it.get("album") or {}).get("name"), "cover": images[0]["url"] if images else None,
                "progress_ms": d.get("progress_ms") or 0, "duration_ms": it.get("duration_ms") or 0,
                "device": dev.get("name"), "device_id": dev.get("id"), "volume": dev.get("volume_percent")}

    def playlists(self) -> list[dict]:
        items = (self._call("GET", "/me/playlists", params={"limit": 50}) or {}).get("items", [])
        return [{"name": p.get("name"), "uri": p.get("uri"), "cover": ((p.get("images") or [{}])[0] or {}).get("url")}
                for p in items if p]

    def playlist_tracks(self, playlist_id: str) -> dict:
        """A playlist opened in the panel: its songs, in order (up to 300).

        Spotify (checked 2026-10-29) gives an app registered now /playlists/{id}/items, not the old
        /tracks (403), and only for playlists he owns: one he merely follows answers 403 there too.
        Such a playlist comes back with locked=True -- it can still be played as a whole."""
        if not playlist_id.replace("_", "").isalnum():
            raise SpotifyError(f"keine Playlist-ID: {playlist_id!r}")
        info = self._call("GET", f"/playlists/{playlist_id}", params={"fields": "name,uri,images"}) or {}
        imgs = info.get("images") or []
        head = {"name": info.get("name"), "uri": info.get("uri"), "cover": imgs[0]["url"] if imgs else None}
        tracks, offset = [], 0
        while offset < 300:
            try:
                page = self._call("GET", f"/playlists/{playlist_id}/items", params={
                    "limit": 100, "offset": offset,
                    "fields": "next,items(item(name,uri,duration_ms,artists(name),album(images)))"}) or {}
            except SpotifyError as exc:
                if offset == 0 and "403" in str(exc):
                    return {**head, "tracks": [], "locked": True}
                raise
            for row in page.get("items") or []:
                t = (row or {}).get("item") or (row or {}).get("track")
                if not t or not t.get("uri"):
                    continue   # a deleted or local song
                imgs = (t.get("album") or {}).get("images") or []
                tracks.append({"name": t.get("name"), "uri": t["uri"], "duration_ms": t.get("duration_ms") or 0,
                               "artist": ", ".join(a["name"] for a in t.get("artists") or []),
                               "cover": imgs[-1]["url"] if imgs else None})   # the smallest picture
            if not page.get("next"):
                break
            offset += 100
        return {**head, "tracks": tracks, "locked": False}

    def play_uri(self, uri: str, device_id: str | None = None, offset_uri: str | None = None) -> dict:
        """A playlist, album or song the panel already knows by its uri -- with offset_uri, that song of
        the playlist, and the playlist plays on after it (as in Spotify itself)."""
        if not uri.startswith("spotify:") or (offset_uri and not offset_uri.startswith("spotify:track:")):
            raise SpotifyError(f"keine Spotify-Adresse: {uri!r}")
        body = {"uris": [uri]} if uri.startswith("spotify:track:") else {"context_uri": uri}
        if offset_uri and "context_uri" in body:
            body["offset"] = {"uri": offset_uri}
        self._call("PUT", "/me/player/play", params={"device_id": device_id} if device_id else {}, json=body)
        return {"ok": True, "did": "spielt"}

    def transfer(self, device_id: str) -> dict:
        """Moves the music to another device (laptop, phone, TV) and keeps it playing."""
        self._call("PUT", "/me/player", json={"device_ids": [device_id], "play": True})
        return {"ok": True, "did": "Gerät gewechselt"}
