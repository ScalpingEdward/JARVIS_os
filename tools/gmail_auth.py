"""One-time Gmail sign-in for AURON -- run on the laptop, not in Docker.

    python tools/gmail_auth.py

Opens Google's sign-in page in the browser; Brano signs in himself and allows
AURON to read and send mail. The answer comes back to a short-lived local
server on 127.0.0.1, the code is exchanged for a refresh token, and client id,
secret and refresh token are written into .env (GMAIL_*). Nothing is printed.

The app is in Google's test mode, so the refresh token lives 7 days; AURON
reminds on Telegram when it has run out, and this script is run again.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import socket
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "secrets" / "gmail_client.json"
ENV = ROOT / ".env"
SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _set_env(values: dict[str, str]) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values:
            lines[i] = f"{key}={values[key]}"
            done.add(key)
    missing = [k for k in values if k not in done]
    if missing:
        lines += ["", "# Gmail (tools/gmail_auth.py schreibt das -- nicht von Hand aendern)"]
        lines += [f"{k}={values[k]}" for k in missing]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = json.loads(CLIENT.read_text(encoding="utf-8"))
    c = cfg.get("installed") or cfg.get("web")
    port = _free_port()
    redirect = f"http://127.0.0.1:{port}"
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = c["auth_uri"] + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256"})
    got: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if q.get("state") == state:
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ok = "code" in got
            self.wfile.write(("<h2 style='font-family:sans-serif'>" + ("AURON hat Zugriff auf Gmail. Du kannst dieses Fenster schliessen."
                              if ok else "Abgebrochen oder abgelehnt.") + "</h2>").encode())

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    print("Browser oeffnet sich -- dort mit deinem Google-Konto anmelden und 'Zulassen' klicken.")
    webbrowser.open(url)
    server.timeout = 300
    while not got:
        server.handle_request()
    if "code" not in got:
        print("Keine Freigabe erhalten:", got.get("error", "unbekannt"))
        return 1
    body = urllib.parse.urlencode({
        "code": got["code"], "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier}).encode()
    with urllib.request.urlopen(urllib.request.Request(c["token_uri"], data=body)) as r:
        tok = json.loads(r.read())
    if "refresh_token" not in tok:
        print("Google hat keinen Refresh-Token geschickt -- Skript bitte noch einmal starten.")
        return 1
    _set_env({"GMAIL_CLIENT_ID": c["client_id"], "GMAIL_CLIENT_SECRET": c["client_secret"],
              "GMAIL_REFRESH_TOKEN": tok["refresh_token"]})
    print("Fertig: Gmail-Zugang in .env gespeichert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
