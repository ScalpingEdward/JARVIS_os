"""Sends a setup as an approval card, and turns a tap back into a decision.

Two responsibilities only. Composing the message and calling
setup_submission.decide() -- nothing here evaluates a strategy, sizes a
position, or reaches a broker. Those all happen elsewhere, gated on the
decision this module records.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
from app.setup_submission.models import SetupDecisionRequest, SetupDecisionStatus, SubmittedSetup
from app.setup_submission.service import SetupSubmissionError, setup_submission_service

from . import tokens
from .models import TelegramApprovalConfig, TelegramWebhookUpdate

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
            return setup_submission_service.decide(
                approval_request_id,
                SetupDecisionRequest(decision=decision, decided_by=who),
            )
        except SetupSubmissionError as exc:
            raise TelegramApprovalError(str(exc)) from exc


telegram_approval_service = TelegramApprovalService()
