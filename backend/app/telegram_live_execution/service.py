"""Sends the final "place this real order" card, and turns a tap back
into the one call that flips human_approved=True on a live order record.

This is the last gate before a remote execution agent (real MetaTrader5,
on the Windows machine with the terminal) can pick the order up via
GET .../pending-execution and actually call order_send(). Today that
gate is a human running curl or a PowerShell one-liner by hand; this
module exists purely to move that same explicit tap onto a phone --
exactly the same principle telegram_approvals already established for
the earlier setup-decision gate: "a faster, mobile way to reach the
exact same gate, not a new one." It calls nothing that a human with API
access could not already call directly.

Deliberately narrow: notify() only ever sends a card for a record
service-side confirmed to be in APPROVAL_REQUIRED right at send time --
never for an order already executed, blocked, or otherwise not actually
waiting on this exact decision. handle_update()'s execute path re-checks
the record is still eligible before calling live_order_executor_service
at all, since state may have changed between the card being sent and the
tap arriving (paused in between, cancelled from elsewhere, etc.) --
the underlying service's own state machine is the real authority here,
this module never assumes the card it sent is still accurate.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.db import SessionLocal
from app.db_models import LiveOrderRecordRow, TelegramLiveExecutionAuditRow
from app.executive_mt5_live_order_executor.models import (
    LiveOrderExecuteRequest,
    LiveOrderRecord,
    LiveOrderState,
)
from app.executive_mt5_live_order_executor.service import live_order_executor_service
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError

from . import tokens
from .models import (
    NotifyOutcome,
    NotifyPendingResult,
    TelegramLiveExecutionAuditRecord,
    TelegramLiveExecutionConfig,
    TelegramLiveExecutionStatus,
    TelegramWebhookUpdate,
)

log = logging.getLogger(__name__)


class TelegramLiveExecutionError(RuntimeError):
    pass


def _format_card(record: LiveOrderRecord) -> str:
    req = record.request
    return (
        f"\u26a0\ufe0f *ECHTE ORDER \u2014 ECHTES GELD* \u26a0\ufe0f\n"
        f"Konto: `{req.account_login}`\n"
        f"{req.symbol} {req.side.upper()} {req.volume:g} Lot\n"
        f"Typ: `{req.order_type}`"
        + (f"  Preis: `{req.requested_price:.5f}`" if req.requested_price else "")
        + "\n"
        + (f"SL: `{req.stop_loss:.5f}`  " if req.stop_loss else "")
        + (f"TP: `{req.take_profit:.5f}`\n" if req.take_profit else "\n")
        + f"Risiko: `{req.expected_risk_amount:g}` (Limit `{req.max_risk_amount:g}`)\n"
        f"{record.detail}\n"
        f"`{record.id}`"
    )


class TelegramLiveExecutionService:
    #: Same bounded-window reasoning as telegram_approvals's own audit
    #: log -- a recent-activity trail, not a permanent archive.
    #: live_order_executor's own audit remains the durable record of
    #: what actually happened to the order.
    MAX_AUDIT_RECORDS = 500

    def __init__(
        self,
        config: TelegramLiveExecutionConfig | None = None,
        client: TelegramDeliveryClient | None = None,
    ) -> None:
        self.config = config or TelegramLiveExecutionConfig()
        self._client = client or TelegramDeliveryClient()

    def _record(
        self, action: str, success: bool, detail: str = "",
        record_id: UUID | None = None, actor: str | None = None,
    ) -> None:
        event = TelegramLiveExecutionAuditRecord(
            record_id=record_id, action=action, success=success,
            detail=detail[:500], actor=actor,
        )
        with SessionLocal() as session:
            session.add(TelegramLiveExecutionAuditRow(
                id=str(event.id), created_at=event.created_at, data=event.model_dump_json(),
            ))
            session.flush()
            total = session.query(TelegramLiveExecutionAuditRow).count()
            if total > self.MAX_AUDIT_RECORDS:
                excess = total - self.MAX_AUDIT_RECORDS
                stale_ids = [
                    r.id for r in
                    session.query(TelegramLiveExecutionAuditRow.id)
                    .order_by(TelegramLiveExecutionAuditRow.created_at)
                    .limit(excess)
                    .all()
                ]
                session.query(TelegramLiveExecutionAuditRow).filter(
                    TelegramLiveExecutionAuditRow.id.in_(stale_ids)
                ).delete(synchronize_session=False)
            session.commit()

    def audit_records(self, limit: int = 50) -> list[TelegramLiveExecutionAuditRecord]:
        with SessionLocal() as session:
            rows = (
                session.query(TelegramLiveExecutionAuditRow)
                .order_by(TelegramLiveExecutionAuditRow.created_at.desc())
                .limit(limit)
                .all()
            )
        return [TelegramLiveExecutionAuditRecord.model_validate_json(r.data) for r in rows]

    def reset(self) -> None:
        with SessionLocal() as session:
            session.query(TelegramLiveExecutionAuditRow).delete()
            session.commit()

    def status(self) -> TelegramLiveExecutionStatus:
        callback_secret_configured = bool(self.config.callback_secret)
        allowed_chat_configured = bool(self.config.allowed_chat_id)
        bot_reachable: bool | None = None
        bot_username: str | None = None
        error: str | None = None
        try:
            info = self._client.get_me()
            bot_reachable = True
            bot_username = info.get("username")
        except TelegramDeliveryError as exc:
            bot_reachable = False
            error = str(exc)
        return TelegramLiveExecutionStatus(
            callback_secret_configured=callback_secret_configured,
            allowed_chat_configured=allowed_chat_configured,
            bot_reachable=bot_reachable,
            bot_username=bot_username,
            error=error,
        )

    # ------------------------------------------------------------- lookup

    def _get_row_and_workspace(self, record_id: UUID) -> tuple[LiveOrderRecordRow, str] | None:
        """Looks a record up by id alone -- workspace_id lives on the row
        itself, so the callback token never needs to carry it. Keeps the
        token minimal, the same shape as telegram_approvals's own."""
        with SessionLocal() as session:
            row = session.get(LiveOrderRecordRow, str(record_id))
            if row is None:
                return None
            return row, row.workspace_id

    # ------------------------------------------------------------- outbound

    def notify(self, record_id: UUID) -> int:
        """Send the execute/cancel card for one order -- only if it is
        actually, right now, sitting in APPROVAL_REQUIRED. Refuses for
        anything else: an already-executed, blocked, or cancelled order
        must never get a card offering to execute it."""
        if not self.config.callback_secret:
            raise TelegramLiveExecutionError(
                "TELEGRAM_LIVE_EXECUTION_CALLBACK_SECRET is not set -- refusing to send "
                "a real-money execute card whose buttons could not be verified when tapped."
            )
        found = self._get_row_and_workspace(record_id)
        if found is None:
            raise TelegramLiveExecutionError(f"unknown live order record {record_id}")
        _row, workspace_id = found
        record = live_order_executor_service.get(record_id, workspace_id)
        if record is None:
            raise TelegramLiveExecutionError(f"unknown live order record {record_id}")
        if record.state != LiveOrderState.APPROVAL_REQUIRED:
            raise TelegramLiveExecutionError(
                f"record {record_id} is in state {record.state.value!r}, not approval-required -- "
                "nothing to decide via this card."
            )

        keyboard = [[
            {"text": "\U0001f7e2 JETZT AUSF\u00dcHREN",
             "callback_data": tokens.make_token(self.config.callback_secret, record_id, tokens.EXECUTE)},
            {"text": "\u26d4 Abbrechen",
             "callback_data": tokens.make_token(self.config.callback_secret, record_id, tokens.CANCEL)},
        ]]
        try:
            message_id = self._client.send_with_keyboard(_format_card(record), keyboard)
        except TelegramDeliveryError as exc:
            self._record("notify", False, str(exc), record_id)
            raise TelegramLiveExecutionError(f"could not deliver the execute card: {exc}") from exc
        self._record("notify", True, f"message_id={message_id}", record_id)
        return message_id

    def notify_pending(self, workspace_id: str) -> NotifyPendingResult:
        """Send a card for every order in this workspace currently sitting
        in APPROVAL_REQUIRED. One failing delivery never stops the rest --
        same principle as telegram_approvals's own notify_pending()."""
        sent: list[NotifyOutcome] = []
        failed: list[NotifyOutcome] = []
        for record in live_order_executor_service.list_records(workspace_id):
            if record.state != LiveOrderState.APPROVAL_REQUIRED:
                continue
            try:
                message_id = self.notify(record.id)
                sent.append(NotifyOutcome(record_id=record.id, message_id=message_id))
            except TelegramLiveExecutionError as exc:
                log.warning("telegram_live_execution: could not notify %s: %s", record.id, exc)
                failed.append(NotifyOutcome(record_id=record.id, error=str(exc)))
        return NotifyPendingResult(sent=sent, failed=failed)

    # ------------------------------------------------------------- inbound

    def handle_update(self, raw_update: dict) -> LiveOrderRecord | None:
        """Process one Telegram Update. Returns the resulting record, or
        None for an update this module has nothing to do with."""
        update = TelegramWebhookUpdate.model_validate(raw_update)
        if update.callback_query is None:
            return None

        cq = update.callback_query
        chat_id = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
        who_raw = ((cq.get("from") or {}).get("username")
                  or str((cq.get("from") or {}).get("id", "unknown")))
        if not self.config.allowed_chat_id or chat_id != self.config.allowed_chat_id:
            log.warning("telegram_live_execution: rejected callback from unauthorized chat %r", chat_id)
            self._record("unauthorized_chat", False, f"chat={chat_id!r}", actor=who_raw)
            raise TelegramLiveExecutionError(f"chat {chat_id!r} is not authorized to execute orders")

        if not self.config.callback_secret:
            self._record("invalid_token", False, "TELEGRAM_LIVE_EXECUTION_CALLBACK_SECRET is not set", actor=who_raw)
            raise TelegramLiveExecutionError("TELEGRAM_LIVE_EXECUTION_CALLBACK_SECRET is not set -- cannot verify the tap")

        raw_token = cq.get("data", "")
        try:
            record_id, action = tokens.verify_token(self.config.callback_secret, raw_token)
        except tokens.TokenError as exc:
            self._record("invalid_token", False, str(exc), actor=who_raw)
            raise TelegramLiveExecutionError(f"invalid callback token: {exc}") from exc

        who = who_raw
        found = self._get_row_and_workspace(record_id)
        if found is None:
            self._record("execute" if action == tokens.EXECUTE else "cancel", False,
                        "record no longer exists", record_id, actor=who)
            raise TelegramLiveExecutionError(f"unknown live order record {record_id}")
        _row, workspace_id = found

        # Re-check state fresh, right before acting -- the card may have
        # been sent minutes ago; execution could have been paused,
        # cancelled from elsewhere, or already reported by the remote
        # agent in the meantime. The underlying service's own state
        # machine decides what a tap can and cannot do; this module
        # never assumes its own card is still accurate.
        current = live_order_executor_service.get(record_id, workspace_id)
        if current is None:
            self._record("execute" if action == tokens.EXECUTE else "cancel", False,
                        "record no longer exists", record_id, actor=who)
            raise TelegramLiveExecutionError(f"unknown live order record {record_id}")
        if action == tokens.EXECUTE and current.state != LiveOrderState.APPROVAL_REQUIRED:
            self._record("stale_state", False,
                        f"record is {current.state.value!r}, no longer approval-required",
                        record_id, actor=who)
            self._safe_send(
                "Freigabe veraltet",
                f"Order {record_id} ist inzwischen im Status "
                f"`{current.state.value}` -- die Freigabe-Anfrage ist nicht mehr aktuell.",
            )
            raise TelegramLiveExecutionError(
                f"record {record_id} is no longer approval-required (now {current.state.value!r})"
            )

        request = LiveOrderExecuteRequest(
            actor_id=who,
            action="cancel" if action == tokens.CANCEL else "submit",
            human_approved=None if action == tokens.CANCEL else True,
        )
        try:
            result = live_order_executor_service.execute(record_id, workspace_id, request)
        except (KeyError, ValueError) as exc:
            self._record("execute" if action == tokens.EXECUTE else "cancel", False, str(exc), record_id, actor=who)
            raise TelegramLiveExecutionError(str(exc)) from exc

        self._record("execute" if action == tokens.EXECUTE else "cancel", True,
                    f"state={result.state.value}", record_id, actor=who)
        self._safe_send(
            "Order ausgef\u00fchrt" if action == tokens.EXECUTE else "Order abgebrochen",
            f"{result.request.symbol} {result.request.side.upper()}: `{result.state.value}`\n{result.detail}",
        )
        return result

    def _safe_send(self, title: str, message: str) -> None:
        try:
            self._client.send(title, message)
        except TelegramDeliveryError:
            log.exception("telegram_live_execution: could not deliver the follow-up message")


telegram_live_execution_service = TelegramLiveExecutionService()
