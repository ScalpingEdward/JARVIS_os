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
