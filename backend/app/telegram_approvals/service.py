"""Sends a setup as an approval card, and turns a tap back into a decision.

Composing the message and calling setup_submission.decide() -- nothing here
evaluates a strategy, sizes a position, or reaches a broker by default.
Optionally (see TelegramApprovalConfig.auto_advance, off unless explicitly
enabled) an Approve tap also runs trade_risk_pipeline.advance_to_preflight()
and reports the outcome back as a follow-up message -- still stops exactly
where that pipeline already stops: human_approved always False, no broker
call, ever, from anything reachable through this module.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
from app.setup_submission.models import (
    SetupDecisionRequest,
    SetupDecisionStatus,
    SetupSubmissionReport,
    SetupSubmissionRequest,
    SubmittedSetup,
)
from app.setup_submission.service import SetupSubmissionError, setup_submission_service
from app.trade_risk_pipeline.models import AdvanceToPreflightFailure, AdvanceToPreflightResult
from app.trade_risk_pipeline.service import trade_risk_pipeline_service

from . import tokens
from .models import (
    NotifyOutcome,
    NotifyPendingResult,
    SubmitAndNotifyResult,
    TelegramApprovalConfig,
    TelegramApprovalStatus,
    TelegramWebhookUpdate,
)

log = logging.getLogger(__name__)


class TelegramApprovalError(RuntimeError):
    pass


def _format_card(setup: SubmittedSetup) -> str:
    tps = ", ".join(f"{tp.price:.5f} ({tp.close_pct:g}%)" for tp in setup.take_profits)
    return (
        f"*Setup pending approval*\n"
        f"Login: `{setup.login}`\n"
        f"Strategy: `{setup.strategy_id}`\n"
        f"{setup.symbol} {setup.side.value.upper()}\n"
        f"Entry: `{setup.entry_price:.5f}`  SL: `{setup.stop_loss:.5f}`\n"
        f"TPs: {tps}\n"
        f"RR: {setup.risk_reward:.2f}  Confidence: {setup.confidence:.0f}%\n"
        f"{setup.reasoning}\n"
        f"`{setup.approval_request_id}`"
    )


class TelegramApprovalService:
    def __init__(
        self,
        config: TelegramApprovalConfig | None = None,
        client: TelegramDeliveryClient | None = None,
    ) -> None:
        self.config = config or TelegramApprovalConfig()
        self._client = client or TelegramDeliveryClient()

    def status(self) -> TelegramApprovalStatus:
        """Capability health: what's configured, and whether the bot is
        actually reachable right now -- not sent to Telegram, never a
        side effect, safe to poll as often as wanted.
        """
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
        return TelegramApprovalStatus(
            callback_secret_configured=callback_secret_configured,
            allowed_chat_configured=allowed_chat_configured,
            auto_advance=self.config.auto_advance,
            bot_reachable=bot_reachable,
            bot_username=bot_username,
            error=error,
        )

    # ------------------------------------------------------------- outbound

    def notify(self, approval_request_id: UUID) -> int:
        """Send the approval card for one pending setup. Returns the
        Telegram message id. Raises if the setup is unknown or the secret
        is not configured -- never sends a card nobody could act on safely."""
        if not self.config.callback_secret:
            raise TelegramApprovalError(
                "TELEGRAM_CALLBACK_SECRET is not set -- refusing to send an approval "
                "card whose buttons could not be verified when tapped."
            )
        setup = setup_submission_service.get_approval(approval_request_id)
        if setup is None:
            raise TelegramApprovalError(f"unknown approval_request_id {approval_request_id}")

        keyboard = [[
            {"text": "\u2705 Approve",
             "callback_data": tokens.make_token(self.config.callback_secret, approval_request_id, tokens.APPROVE)},
            {"text": "\u274c Reject",
             "callback_data": tokens.make_token(self.config.callback_secret, approval_request_id, tokens.REJECT)},
        ]]
        try:
            return self._client.send_with_keyboard(_format_card(setup), keyboard)
        except TelegramDeliveryError as exc:
            raise TelegramApprovalError(f"could not deliver the approval card: {exc}") from exc

    def notify_pending(self) -> NotifyPendingResult:
        """Send a card for every still-undecided pending setup.

        One failing delivery must not stop the rest -- same principle as
        the trading worker's own task isolation (a broker hiccup on one
        card is not a reason to leave three other operators' setups
        unannounced). Returns which ids were sent and which failed, with
        the reason, rather than raising on the first problem.
        """
        sent: list[NotifyOutcome] = []
        failed: list[NotifyOutcome] = []
        for setup in setup_submission_service.get_pending_approvals():
            if setup.decision != SetupDecisionStatus.pending:
                continue
            try:
                message_id = self.notify(setup.approval_request_id)
                sent.append(NotifyOutcome(approval_request_id=setup.approval_request_id, message_id=message_id))
            except TelegramApprovalError as exc:
                log.warning("telegram_approvals: could not notify %s: %s",
                           setup.approval_request_id, exc)
                failed.append(NotifyOutcome(approval_request_id=setup.approval_request_id, error=str(exc)))
        return NotifyPendingResult(sent=sent, failed=failed)

    def submit_and_notify(self, request: SetupSubmissionRequest) -> SubmitAndNotifyResult:
        """Submit against a snapshot, then send a card for every setup it
        just produced. One call from the operator's side: run the
        strategies, and the phone lights up for whatever came out of it.

        Kept here rather than inside setup_submission.submit() itself so
        that module's dependency direction stays one-way -- setup_submission
        knows nothing about Telegram, this module depends on it, not the
        other way around. A caller who wants both calls this method (or the
        /submit-and-notify route); one who only wants the evaluation, with
        no notification, still has plain submit() available untouched.
        """
        report: SetupSubmissionReport = setup_submission_service.submit(request)
        sent: list[NotifyOutcome] = []
        failed: list[NotifyOutcome] = []
        for setup in report.submitted_setups:
            try:
                message_id = self.notify(setup.approval_request_id)
                sent.append(NotifyOutcome(approval_request_id=setup.approval_request_id, message_id=message_id))
            except TelegramApprovalError as exc:
                log.warning("telegram_approvals: could not notify %s: %s",
                           setup.approval_request_id, exc)
                failed.append(NotifyOutcome(approval_request_id=setup.approval_request_id, error=str(exc)))
        return SubmitAndNotifyResult(report=report, notified=NotifyPendingResult(sent=sent, failed=failed))

    # -------------------------------------------------------------- inbound

    def handle_update(self, raw_update: dict) -> SubmittedSetup | None:
        """Process one Telegram Update. Returns the decided setup, or None
        for an update this module has nothing to do with (e.g. a plain
        message, not a button tap) -- that is not an error, most updates a
        webhook receives are not approval taps."""
        update = TelegramWebhookUpdate.model_validate(raw_update)
        if update.callback_query is None:
            return None

        cq = update.callback_query
        chat_id = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
        if not self.config.allowed_chat_id or chat_id != self.config.allowed_chat_id:
            log.warning("telegram_approvals: rejected callback from unauthorized chat %r", chat_id)
            raise TelegramApprovalError(f"chat {chat_id!r} is not authorized to decide setups")

        if not self.config.callback_secret:
            raise TelegramApprovalError("TELEGRAM_CALLBACK_SECRET is not set -- cannot verify the tap")

        raw_token = cq.get("data", "")
        try:
            approval_request_id, action = tokens.verify_token(self.config.callback_secret, raw_token)
        except tokens.TokenError as exc:
            raise TelegramApprovalError(f"invalid callback token: {exc}") from exc

        who = ((cq.get("from") or {}).get("username")
               or str((cq.get("from") or {}).get("id", "unknown")))
        decision = SetupDecisionStatus.approved if action == tokens.APPROVE else SetupDecisionStatus.rejected

        try:
            decided = setup_submission_service.decide(
                approval_request_id,
                SetupDecisionRequest(decision=decision, decided_by=who),
            )
        except SetupSubmissionError as exc:
            raise TelegramApprovalError(str(exc)) from exc

        if decision == SetupDecisionStatus.approved and self.config.auto_advance:
            self._advance_and_report(approval_request_id)

        return decided

    def _advance_and_report(self, approval_request_id: UUID) -> None:
        """Best-effort follow-up: the decision above already succeeded and
        is returned regardless of what happens here. A problem advancing
        (bad quote data, no matching mt5_bridge terminal, whatever) is
        reported back as a Telegram message, not raised -- the tap itself
        must not appear to fail just because the next, optional step did.
        """
        try:
            result = trade_risk_pipeline_service.advance_to_preflight(approval_request_id)
        except Exception:
            log.exception("telegram_approvals: advance_to_preflight crashed for %s", approval_request_id)
            self._safe_send("Preflight failed", f"Unerwarteter Fehler bei {approval_request_id}.")
            return

        if isinstance(result, AdvanceToPreflightResult):
            self._safe_send(
                "Preflight bereit",
                f"Risk: {result.risk_record.state.value}\n"
                f"Position: {result.position.state.value}, size={result.position.position_size:.4f}\n"
                f"Live-Order: {result.live_order.state.value}",
            )
        elif isinstance(result, AdvanceToPreflightFailure):
            self._safe_send(
                f"Preflight gestoppt bei {result.failed_at}",
                result.error,
            )

    def _safe_send(self, title: str, message: str) -> None:
        try:
            self._client.send(title, message)
        except TelegramDeliveryError:
            log.exception("telegram_approvals: could not deliver the follow-up message")


telegram_approval_service = TelegramApprovalService()
