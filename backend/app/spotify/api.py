from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

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
