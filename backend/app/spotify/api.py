from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from . import client

router = APIRouter(prefix="/v1/spotify", tags=["spotify"])

PAGE = "<p style='font-family:sans-serif;font-size:18px;max-width:640px;margin:40px auto'>{}</p>"


@router.get("/login")
def login():
    """Opened once in the browser: on to Spotify's sign-in, back to /callback."""
    try:
        return RedirectResponse(client.login_url())
    except client.SpotifyError as exc:
        return HTMLResponse(PAGE.format(exc), status_code=503)


@router.get("/callback")
def callback(code: str | None = None, error: str | None = None) -> HTMLResponse:
    if error or not code:
        return HTMLResponse(PAGE.format(f"Spotify hat abgelehnt: {error or 'kein Code'}"), status_code=400)
    try:
        client.Spotify().finish_login(code)
    except client.SpotifyError as exc:
        return HTMLResponse(PAGE.format(exc), status_code=502)
    return HTMLResponse(PAGE.format("✅ Spotify ist mit AURON verbunden. Du kannst dieses Fenster schließen und AURON "
                                    "sagen: „Spiel etwas zum Konzentrieren“."))


@router.get("/status")
def status() -> dict:
    return {"connected": client.connected()}


# ---- the dashboard's Spotify panel (frontend/media.js) -------------------------------------------
# One client for all of them: each new one fetches a fresh access token, and the panel asks every few
# seconds while it is open.
_sp: client.Spotify | None = None


def _spotify() -> client.Spotify:
    global _sp
    if _sp is None:
        _sp = client.Spotify()
    return _sp


def _guard(fn):
    try:
        return fn()
    except client.SpotifyError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/player")
def player() -> dict:
    return _guard(lambda: _spotify().player())


@router.get("/devices")
def devices() -> dict:
    return {"devices": _guard(lambda: _spotify().devices())}


@router.get("/playlists")
def playlists() -> dict:
    return {"playlists": _guard(lambda: _spotify().playlists())}


@router.get("/playlists/{playlist_id}")
def playlist(playlist_id: str) -> dict:
    return _guard(lambda: _spotify().playlist_tracks(playlist_id))


class Control(BaseModel):
    action: Literal["play", "pause", "next", "previous", "volume", "transfer", "play_uri", "search"]
    value: int | None = None        # volume in %
    uri: str | None = None          # play_uri
    device_id: str | None = None    # transfer, play_uri
    offset_uri: str | None = None   # play_uri: start the playlist at this song
    query: str | None = None        # search: a song, artist, album or playlist by name
    kind: Literal["track", "artist", "album", "playlist"] = "track"


@router.post("/control")
def control(c: Control) -> dict:
    sp = _spotify()
    actions = {
        "play": lambda: sp.play(),
        "pause": sp.pause, "next": sp.next, "previous": sp.previous,
        "volume": lambda: sp.volume(c.value if c.value is not None else 50),
        "transfer": lambda: sp.transfer(c.device_id or ""),
        "play_uri": lambda: sp.play_uri(c.uri or "", c.device_id, c.offset_uri),
        "search": lambda: sp.play(c.query, c.kind),
    }
    return _guard(actions[c.action])
