"""AURON's post office: every few minutes new mail is sorted, what matters is reported.

poll()   new inbox mail -> Claude sorts it -> stored; important ones once to Telegram
draft()  a reply AURON wrote, shown with Send / Discard -- on the dashboard and in Telegram
send()   only ever called by Brano's button, never by AURON's own tools
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import MailDraftRow, MailItemRow

from .classify import ClassifyError, classify
from .gmail import Gmail, GmailAuthExpired, GmailError, address

log = logging.getLogger(__name__)
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s mail: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False

PER_RUN = 40        # new mails looked at per poll; the rest waits for the next one
BATCH = 20          # mails per Claude call


class MailError(RuntimeError):
    pass


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


class MailService:
    def __init__(self) -> None:
        self.gmail = Gmail()
        self.last_poll: datetime | None = None
        self.last_error = ""
        self._reminded: date | None = None

    def reset(self) -> None:
        refuse_reset_in_production("mail")
        with SessionLocal() as s:
            s.query(MailItemRow).delete()
            s.query(MailDraftRow).delete()
            s.commit()

    # ---------------------------------------------------------------- sorting
    def poll(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        if not self.gmail.configured():
            self.last_error = "Gmail ist nicht verbunden"
            return {"new": 0, "important": 0, "error": self.last_error}
        try:
            ids = self.gmail.list_ids()
            with SessionLocal() as s:
                known = {r[0] for r in s.query(MailItemRow.id).filter(MailItemRow.id.in_(ids)).all()} if ids else set()
            fresh = [self.gmail.message(i) for i in ids if i not in known][:PER_RUN]
            sorted_ = []
            for i in range(0, len(fresh), BATCH):
                sorted_ += classify(fresh[i:i + BATCH])
        except GmailAuthExpired as exc:
            self.last_error = str(exc)
            self._remind_sign_in()
            return {"new": 0, "important": 0, "error": self.last_error}
        except (GmailError, ClassifyError) as exc:
            self.last_error = str(exc)
            log.warning("poll failed: %s", exc)
            return {"new": 0, "important": 0, "error": self.last_error}
        by_id = {m["id"]: m for m in fresh}
        alert = []
        with SessionLocal() as s:
            for c in sorted_:
                if not c["sorted"]:
                    continue  # the model skipped it -- try again next run instead of filing it as unimportant
                m = by_id[c["id"]]
                row = MailItemRow(id=m["id"], thread_id=m["thread_id"], sender=m["from"][:300], subject=m["subject"][:500],
                                  received_at=datetime.fromtimestamp(m["received"], timezone.utc), snippet=m["snippet"],
                                  important=int(c["important"]), category=c["category"], summary=c["summary"])
                s.add(row)
                if c["important"]:
                    alert.append(row)
            lines, alert_ids = [self._line(r) for r in alert], [r.id for r in alert]
            s.commit()
            if alert and self._telegram(lines, "Wichtige Post"):
                s.query(MailItemRow).filter(MailItemRow.id.in_(alert_ids)).update({"alerted": 1}, synchronize_session=False)
                s.commit()
        self.last_poll, self.last_error = now, ""
        log.info("polled: %d new, %d important", len(sorted_), len(alert))
        return {"new": len(sorted_), "important": len(alert), "error": ""}

    @staticmethod
    def _line(r: MailItemRow) -> str:
        who = r.sender.split("<")[0].strip().strip('"') or address(r.sender)
        return f"• {who}: {r.subject}\n  {r.summary}"

    def _telegram(self, lines: list[str], title: str, keyboard: list[list[dict]] | None = None) -> bool:
        from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
        try:
            c = TelegramDeliveryClient()
            if keyboard:
                c.send_with_keyboard(f"{title}\n\n" + "\n\n".join(lines), keyboard)
            else:
                c.send(title, "\n\n".join(lines))
            return True
        except TelegramDeliveryError as exc:
            log.warning("telegram failed: %s", exc)
            return False

    def _remind_sign_in(self) -> None:
        today = date.today()
        if self._reminded == today:
            return
        if self._telegram(["Die Gmail-Anmeldung ist abgelaufen (Google-Testmodus: alle 7 Tage), Sir. "
                           "Am Laptop: python tools/gmail_auth.py -- 30 Sekunden, dann lese ich wieder mit."], "Gmail"):
            self._reminded = today

    # ---------------------------------------------------------------- reading
    def items(self, important_only: bool = False, days: int = 14, limit: int = 50) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with SessionLocal() as s:
            q = s.query(MailItemRow).filter(MailItemRow.received_at >= since)
            if important_only:
                q = q.filter(MailItemRow.important == 1)
            rows = q.order_by(MailItemRow.received_at.desc()).limit(limit).all()
            return [{"id": r.id, "from": r.sender, "subject": r.subject, "received_at": _aware(r.received_at).isoformat(),
                     "important": bool(r.important), "category": r.category, "summary": r.summary, "done": bool(r.done)}
                    for r in rows]

    def status(self) -> dict:
        return {"connected": self.gmail.configured(), "last_poll": self.last_poll.isoformat() if self.last_poll else None,
                "error": self.last_error}

    def read(self, mail_id: str) -> dict:
        m = self.gmail.message(mail_id, full=True)
        return {k: m[k] for k in ("id", "from", "reply_to", "subject", "body")}

    def mark_done(self, mail_id: str, done: bool = True) -> None:
        with SessionLocal() as s:
            r = s.get(MailItemRow, mail_id)
            if r is None:
                raise MailError("unknown mail")
            r.done = int(done)
            s.commit()

    # ---------------------------------------------------------------- replying
    def draft(self, mail_id: str, body: str) -> dict:
        """A reply, waiting for Brano. Shown on Telegram with Send / Discard."""
        m = self.gmail.message(mail_id)
        to = m["reply_to"] or m["from"]
        d = MailDraftRow(id=str(uuid.uuid4()), mail_id=mail_id, thread_id=m["thread_id"], to=to[:300],
                         subject=(m["subject"] if m["subject"].lower().startswith("re:") else f"Re: {m['subject']}")[:500],
                         body=body.strip(), in_reply_to=m["message_id"][:500], created_at=datetime.now(timezone.utc))
        with SessionLocal() as s:
            s.add(d)
            s.commit()
            out = self._draft_dict(d)
        self._telegram([f"An: {to}\nBetreff: {out['subject']}\n\n{out['body']}"], "Antwort-Entwurf -- senden?",
                       keyboard=[[{"text": "✅ Senden", "callback_data": f"mail:m:{out['id']}"},
                                  {"text": "🗑 Verwerfen", "callback_data": f"mail:k:{out['id']}"}]])
        return out

    @staticmethod
    def _draft_dict(d: MailDraftRow) -> dict:
        return {"id": d.id, "mail_id": d.mail_id, "to": d.to, "subject": d.subject, "body": d.body, "status": d.status,
                "created_at": _aware(d.created_at).isoformat()}

    def drafts(self, status: str = "pending") -> list[dict]:
        with SessionLocal() as s:
            return [self._draft_dict(d) for d in s.query(MailDraftRow).filter(MailDraftRow.status == status)
                    .order_by(MailDraftRow.created_at.desc()).limit(20).all()]

    def send(self, draft_id: str) -> dict:
        """Brano pressed Send. The one place mail leaves AURON."""
        with SessionLocal() as s:
            d = s.get(MailDraftRow, draft_id)
            if d is None:
                raise MailError("unknown draft")
            if d.status != "pending":
                raise MailError(f"draft is {d.status}, not pending")
            self.gmail.send_reply(d.to, d.subject, d.body, d.thread_id, d.in_reply_to)
            d.status, d.sent_at = "sent", datetime.now(timezone.utc)
            s.commit()
            log.info("reply sent to %s", address(d.to))
            return self._draft_dict(d)

    def discard(self, draft_id: str) -> dict:
        with SessionLocal() as s:
            d = s.get(MailDraftRow, draft_id)
            if d is None:
                raise MailError("unknown draft")
            if d.status == "pending":
                d.status = "discarded"
                s.commit()
            return self._draft_dict(d)

    def handle_tap(self, update: dict) -> str:
        """A Send / Discard tap in Telegram -- only from Brano's chat."""
        q = update.get("callback_query") or {}
        chat = str(((q.get("message") or {}).get("chat") or {}).get("id", ""))
        if not os.getenv("TELEGRAM_CHAT_ID") or chat != str(os.getenv("TELEGRAM_CHAT_ID")):
            raise MailError(f"chat {chat} not allowed")
        _, action, draft_id = (q.get("data") or "").split(":", 2)
        try:
            d = self.send(draft_id) if action == "m" else self.discard(draft_id)
            text = f"✅ Gesendet an {address(d['to'])}" if action == "m" else "🗑 Entwurf verworfen"
        except (MailError, GmailError) as exc:
            text = f"Nicht gesendet: {exc}"
        self._telegram([text], "Mail")
        msg_id = (q.get("message") or {}).get("message_id")
        if msg_id:
            from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
            try:
                TelegramDeliveryClient().clear_keyboard(msg_id)
            except TelegramDeliveryError:
                pass
        return text


class MailPoller:
    """Every MAIL_POLL_SECONDS (default 300) one poll, on the side of the event loop."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def _run(self, every: float) -> None:
        while True:
            try:
                await asyncio.to_thread(mail_service.poll)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- one bad run must not end the loop
                log.warning("poll crashed: %s", exc)
            await asyncio.sleep(every)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(float(os.getenv("MAIL_POLL_SECONDS", "300"))))
        log.info("mail polling started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


mail_service = MailService()
mail_poller = MailPoller()
