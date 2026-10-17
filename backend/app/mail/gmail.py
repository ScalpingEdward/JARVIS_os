"""The Gmail API, the few calls AURON needs: list, read, send a reply.

Access comes from the refresh token tools/gmail_auth.py put into .env. Scopes are
gmail.readonly and gmail.send -- nothing here can delete, archive or relabel.
The app is in Google's test mode, so the token runs out after 7 days: that shows
up as GmailAuthExpired, and the service reminds Brano on Telegram.
"""
from __future__ import annotations

import base64
import os
import time
from email.message import EmailMessage
from email.utils import parseaddr

import httpx

API = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# What AURON looks at: the inbox, without what Gmail itself files as advertising,
# social networks or forums. "Updates" stays -- bills and bank notices land there.
INBOX_QUERY = "in:inbox -category:promotions -category:social -category:forums"


class GmailError(RuntimeError):
    pass


class GmailAuthExpired(GmailError):
    pass


class Gmail:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30)
        self._token = ""
        self._token_until = 0.0

    @staticmethod
    def configured() -> bool:
        return all(os.getenv(k) for k in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"))

    def _access(self) -> str:
        if self._token and time.time() < self._token_until - 60:
            return self._token
        if not self.configured():
            raise GmailError("Gmail is not connected (run tools/gmail_auth.py)")
        r = self._client.post(TOKEN_URL, data={
            "client_id": os.getenv("GMAIL_CLIENT_ID"), "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
            "refresh_token": os.getenv("GMAIL_REFRESH_TOKEN"), "grant_type": "refresh_token"})
        if r.status_code == 400 and "invalid_grant" in r.text:
            raise GmailAuthExpired("the Gmail sign-in has run out (test mode: 7 days) -- run tools/gmail_auth.py")
        if r.status_code >= 400:
            raise GmailError(f"token refresh failed: {r.status_code} {r.text[:200]}")
        body = r.json()
        self._token, self._token_until = body["access_token"], time.time() + body.get("expires_in", 3600)
        return self._token

    def _get(self, path: str, **params) -> dict:
        r = self._client.get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {self._access()}"})
        if r.status_code >= 400:
            raise GmailError(f"GET {path}: {r.status_code} {r.text[:200]}")
        return r.json()

    def list_ids(self, query: str = INBOX_QUERY, newer_than_days: int = 2, limit: int = 50) -> list[str]:
        d = self._get("/messages", q=f"{query} newer_than:{newer_than_days}d", maxResults=limit)
        return [m["id"] for m in d.get("messages", [])]

    def message(self, mid: str, full: bool = False) -> dict:
        """Headers, snippet and labels; full=True adds the plain-text body."""
        d = self._get(f"/messages/{mid}", format="full" if full else "metadata",
                      **({} if full else {"metadataHeaders": ["From", "Subject", "Date", "Message-ID", "Reply-To"]}))
        h = {x["name"].lower(): x["value"] for x in d.get("payload", {}).get("headers", [])}
        out = {"id": d["id"], "thread_id": d["threadId"], "labels": d.get("labelIds", []),
               "from": h.get("from", ""), "reply_to": h.get("reply-to", ""), "subject": h.get("subject", ""),
               "message_id": h.get("message-id", ""), "snippet": d.get("snippet", ""),
               "received": int(d.get("internalDate", "0")) / 1000}
        if full:
            out["body"] = _plain(d.get("payload", {}))[:20000]
        return out

    def send_reply(self, to: str, subject: str, body: str, thread_id: str, in_reply_to: str) -> str:
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        r = self._client.post(f"{API}/messages/send", headers={"Authorization": f"Bearer {self._access()}"},
                              json={"raw": raw, "threadId": thread_id})
        if r.status_code >= 400:
            raise GmailError(f"send failed: {r.status_code} {r.text[:200]}")
        return r.json()["id"]


def _plain(part: dict) -> str:
    """The text/plain parts of a message; HTML-only mail falls back to tag-stripped HTML."""
    plain, html = [], []

    def walk(p: dict) -> None:
        mime, data = p.get("mimeType", ""), (p.get("body") or {}).get("data")
        if data and mime == "text/plain":
            plain.append(base64.urlsafe_b64decode(data + "==").decode("utf-8", "replace"))
        elif data and mime == "text/html":
            html.append(base64.urlsafe_b64decode(data + "==").decode("utf-8", "replace"))
        for sub in p.get("parts", []) or []:
            walk(sub)
    walk(part)
    if plain:
        return "\n".join(plain)
    import re
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", "\n".join(html), flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def address(sender: str) -> str:
    return parseaddr(sender)[1] or sender
