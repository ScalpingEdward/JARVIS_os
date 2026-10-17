"""Commands for the copiers: pause, resume, close all.

The copier runs on the laptop and pushes its status every 15 s; the answer to that push
carries its pending commands, and it acks each one when done. So a command takes effect
within about 20 seconds, and nothing needs a port opened toward the laptop.

close_all is never run on one click from AURON: it waits as 'awaiting_confirmation' until
Brano confirms -- the button in Telegram or the dashboard's own dialog. AURON's tool cannot confirm.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.db_models import CopierCommandRow

ACTIONS = {"pause": "pausieren", "resume": "fortsetzen", "close_all": "alle Trades schließen"}
NEEDS_CONFIRMATION = {"close_all"}
EXPIRE = timedelta(minutes=10)   # an unconfirmed or unpicked command goes stale


class CommandError(ValueError):
    pass


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _dict(r: CopierCommandRow) -> dict:
    return {"id": r.id, "profile": r.profile, "action": r.action, "status": r.status, "source": r.source,
            "created_at": _aware(r.created_at).isoformat(), "result": r.result}


def _telegram(text: str, keyboard: list | None = None) -> None:
    from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
    try:
        c = TelegramDeliveryClient()
        if keyboard:
            c.send_with_keyboard(text, keyboard)
        else:
            c.send("Kopierer", text)
    except TelegramDeliveryError:
        pass


def create(profile: str, action: str, source: str, confirmed: bool = False, label: str = "") -> dict:
    if action not in ACTIONS:
        raise CommandError(f"unknown action {action}")
    needs = action in NEEDS_CONFIRMATION and not confirmed
    r = CopierCommandRow(id=str(uuid.uuid4()), profile=profile, action=action, source=source,
                         status="awaiting_confirmation" if needs else "pending", created_at=datetime.now(timezone.utc))
    with SessionLocal() as s:
        s.add(r)
        s.commit()
        out = _dict(r)
    if needs:
        _telegram(f"Bestätigen: {label or profile} -- {ACTIONS[action]}?\n(läuft in 10 Minuten ab)",
                  [[{"text": "✅ Ja, ausführen", "callback_data": f"cmd:z:{out['id']}"},
                    {"text": "✖ Abbrechen", "callback_data": f"cmd:q:{out['id']}"}]])
    return out


def confirm(command_id: str) -> dict:
    with SessionLocal() as s:
        r = s.get(CopierCommandRow, command_id)
        if r is None:
            raise CommandError("unknown command")
        if r.status != "awaiting_confirmation":
            raise CommandError(f"command is {r.status}")
        if datetime.now(timezone.utc) - _aware(r.created_at) > EXPIRE:
            r.status = "cancelled"
            s.commit()
            raise CommandError("expired -- ask again")
        r.status = "pending"
        s.commit()
        return _dict(r)


def cancel(command_id: str) -> dict:
    with SessionLocal() as s:
        r = s.get(CopierCommandRow, command_id)
        if r is None:
            raise CommandError("unknown command")
        if r.status in ("awaiting_confirmation", "pending"):
            r.status = "cancelled"
            s.commit()
        return _dict(r)


def pending_for(profile: str) -> list[dict]:
    """What the copier should do now -- handed out with every status push until acked."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as s:
        rows = s.query(CopierCommandRow).filter(CopierCommandRow.profile == profile,
                                                CopierCommandRow.status == "pending").all()
        out = []
        for r in rows:
            if now - _aware(r.created_at) > EXPIRE:
                r.status = "cancelled"
                r.result = "not picked up in 10 minutes (copier offline?)"
            else:
                out.append({"id": r.id, "action": r.action})
        s.commit()
        return out


def done(command_id: str, ok: bool, result: str) -> dict:
    with SessionLocal() as s:
        r = s.get(CopierCommandRow, command_id)
        if r is None:
            raise CommandError("unknown command")
        r.status, r.result, r.done_at = ("done" if ok else "failed"), result, datetime.now(timezone.utc)
        s.commit()
        out = _dict(r)
    if out["action"] == "close_all" or not ok:
        _telegram(f"{out['profile']}: {result}")
    return out


def recent(limit: int = 20) -> list[dict]:
    with SessionLocal() as s:
        return [_dict(r) for r in s.query(CopierCommandRow).order_by(CopierCommandRow.created_at.desc()).limit(limit).all()]


def handle_tap(update: dict) -> str:
    """The confirm / cancel buttons in Telegram -- only from Brano's chat."""
    q = update.get("callback_query") or {}
    chat = str(((q.get("message") or {}).get("chat") or {}).get("id", ""))
    if not os.getenv("TELEGRAM_CHAT_ID") or chat != str(os.getenv("TELEGRAM_CHAT_ID")):
        raise CommandError(f"chat {chat} not allowed")
    _, action, cid = (q.get("data") or "").split(":", 2)
    try:
        if action == "z":
            confirm(cid)
            text = "Bestätigt -- wird in den nächsten Sekunden ausgeführt."
        else:
            cancel(cid)
            text = "Abgebrochen."
    except CommandError as exc:
        text = f"Nicht ausgeführt: {exc}"
    _telegram(text)
    msg_id = (q.get("message") or {}).get("message_id")
    if msg_id:
        from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
        try:
            TelegramDeliveryClient().clear_keyboard(msg_id)
        except TelegramDeliveryError:
            pass
    return text
