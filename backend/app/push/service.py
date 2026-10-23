"""AURON's own notifications -- on the laptop's screen and on the iPhone, from the AURON app itself, not
from Telegram (Brano, 2026-10-23).

Web Push: each device that switched them on (Einstellungen > Benachrichtigungen) leaves a subscription
here; a message is encrypted for it and handed to its push service (Microsoft's for Edge, Apple's for the
iPhone home-screen app), which shows it even when the page is not in front. The VAPID key pair that signs
them is made once and kept in the database, like the Spotify sign-in.

Which way a kind of message goes -- app, Telegram or both -- is set per category (the same categories as
the Telegram mute, notification_hub/mute.py). Muted stays muted on every way.
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

log = logging.getLogger("push")
KEYS = "push.vapid"
SUBS = "push.subscriptions"
ROUTES = "push.routes"
WAYS = ("app", "telegram", "both")
DEFAULT_WAY = "both"
CONTACT = "mailto:auron@localhost"


class PushError(ValueError):
    pass


def _get(key: str, default):
    try:
        with SessionLocal() as s:
            row = s.get(AppSettingRow, key)
        return json.loads(row.value) if row else default
    except Exception:  # noqa: BLE001 -- no database: no app notifications, Telegram still works
        return default


def _put(key: str, value) -> None:
    with SessionLocal() as s:
        row = s.get(AppSettingRow, key) or AppSettingRow(key=key)
        row.value = json.dumps(value)
        row.updated_at = datetime.now(timezone.utc)
        s.merge(row)
        s.commit()


# ---- the key pair -----------------------------------------------------------------------------------
def keys() -> dict:
    k = _get(KEYS, None)
    if k:
        return k
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    priv = ec.generate_private_key(ec.SECP256R1())
    pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    raw = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    k = {"private_pem": pem, "public": base64.urlsafe_b64encode(raw).rstrip(b"=").decode()}
    _put(KEYS, k)
    return k


def public_key() -> str:
    return keys()["public"]


# ---- devices ----------------------------------------------------------------------------------------
def devices() -> list[dict]:
    return _get(SUBS, [])


def subscribe(sub: dict, device: str = "") -> dict:
    if not str(sub.get("endpoint", "")).startswith("https://") or not (sub.get("keys") or {}).get("p256dh"):
        raise PushError("keine gültige Push-Anmeldung")
    cur = [d for d in devices() if d["sub"]["endpoint"] != sub["endpoint"]]
    d = {"sub": {"endpoint": sub["endpoint"], "keys": sub["keys"]}, "device": (device or "Gerät")[:60], "added": time.time()}
    _put(SUBS, [*cur, d])
    return {"device": d["device"], "devices": len(cur) + 1}


def unsubscribe(endpoint: str) -> bool:
    cur = devices()
    _put(SUBS, [d for d in cur if d["sub"]["endpoint"] != endpoint])
    return len(cur) != len(devices())


# ---- which way ------------------------------------------------------------------------------------
def routes() -> dict[str, str]:
    from app.notification_hub.mute import CATEGORIES
    stored = _get(ROUTES, {})
    return {c: stored.get(c, DEFAULT_WAY) for c in CATEGORIES}


def set_route(category: str, way: str) -> dict[str, str]:
    from app.notification_hub.mute import CATEGORIES
    if way not in WAYS:
        raise PushError(f"Weg {way!r}; es gibt {list(WAYS)}")
    cur = routes()
    for c in (CATEGORIES if category == "all" else [category]):
        if c not in cur:
            raise PushError(f"Kategorie {category!r}; es gibt {list(CATEGORIES)}")
        cur[c] = way
    _put(ROUTES, cur)
    return cur


def wants(category: str, way: str) -> bool:
    r = routes().get(category, DEFAULT_WAY)
    return r == "both" or r == way


# ---- sending --------------------------------------------------------------------------------------
def send(title: str, body: str, category: str = "other", url: str = "/", tag: str | None = None) -> int:
    """To every device; a device the push service no longer knows (404/410) is dropped. Returns how many got it."""
    from pywebpush import WebPushException, webpush
    k = keys()
    payload = json.dumps({"title": title or "AURON", "body": (body or "")[:900], "url": url, "tag": tag or category})
    ok, gone = 0, []
    for d in devices():
        try:
            webpush(d["sub"], payload, vapid_private_key=k["private_pem"], vapid_claims={"sub": CONTACT}, ttl=3600, timeout=10)
            ok += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                gone.append(d["sub"]["endpoint"])
            log.warning("push to %s failed: %s", d["device"], exc)
        except Exception as exc:  # noqa: BLE001 -- one device failing never stops the others
            log.warning("push to %s failed: %s", d["device"], exc)
    for e in gone:
        unsubscribe(e)
    return ok


def send_later(title: str, body: str, category: str = "other", url: str = "/") -> None:
    """From the Telegram path: never let a slow push service hold up a message."""
    if devices():
        threading.Thread(target=send, args=(title, body, category, url), daemon=True).start()
