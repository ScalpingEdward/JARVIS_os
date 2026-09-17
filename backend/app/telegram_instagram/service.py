"""Turns a curated draft into a card on Brano's phone, and a tap back into
a decision.

What a tap does NOT do is publish. Approving sets the candidate to
`approved` and stops there, exactly as the existing HTTP decision route
does -- publishing stays a separate, explicit call. That separation is not
bureaucracy here: Instagram's audio catalogue is unreachable from the
publishing path this account uses, so Brano picks the sound in the app and
posts Reels himself. A button that published on tap would take that away.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.db import SessionLocal
from app.db_models import TelegramInstagramAuditRow
from app.instagram_content.media_pool_models import FinalizeDraftRequest
from app.instagram_content.media_pool_service import media_pool_service
from app.instagram_content.models import ContentCandidate, ContentDecision, ContentStatus
from app.instagram_content.service import InstagramContentError, instagram_content_service
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError

from . import tokens
from .models import (
    InstagramAuditRecord,
    NotifyResult,
    TelegramInstagramConfig,
    TelegramInstagramStatus,
    TelegramWebhookUpdate,
)

log = logging.getLogger(__name__)


class TelegramInstagramError(RuntimeError):
    pass


def _format_card(candidate: ContentCandidate) -> str:
    """Everything needed to decide, and nothing that needs a second screen.

    No preview image: AURON holds no Drive credentials and never has the
    file, only its reference. Saying the media_ref plainly is honest about
    that -- a card that looked like it had seen the photo would be worse
    than one that admits it has not.
    """
    lines = [
        f"*Instagram: {candidate.post_format.value} zur Freigabe*",
        f"{len(candidate.media_items)} Medium/Medien"
        f" · Score {sum(m.aesthetic_score for m in candidate.media_items) / len(candidate.media_items):.2f}",
        "",
        candidate.caption_draft[:600],
    ]
    if candidate.edit_warnings:
        lines += ["", "⚠️ " + "\n⚠️ ".join(candidate.edit_warnings)]
    if candidate.moderation_warnings:
        lines += ["", "Moderation: " + "; ".join(candidate.moderation_warnings)]
    if candidate.hook_warnings:
        lines += ["", "Hook: " + "; ".join(candidate.hook_warnings)]
    lines += ["", "Dateien: " + ", ".join(m.media_ref for m in candidate.media_items[:5])]
    lines += [f"`{candidate.id}`"]
    return "\n".join(lines)


class TelegramInstagramService:
    #: Bounded, same reasoning as the other Telegram audit logs: a
    #: recent-activity window, not a permanent archive.
    MAX_AUDIT_RECORDS = 500

    def __init__(
        self,
        config: TelegramInstagramConfig | None = None,
        client: TelegramDeliveryClient | None = None,
    ) -> None:
        self.config = config or TelegramInstagramConfig()
        self._client = client or TelegramDeliveryClient()

    # --------------------------------------------------------------- audit

    def _record(
        self, action: str, success: bool, detail: str = "",
        candidate_id: UUID | None = None, actor: str | None = None,
    ) -> None:
        event = InstagramAuditRecord(
            candidate_id=candidate_id, action=action, success=success,
            detail=detail[:500], actor=actor,
        )
        with SessionLocal() as session:
            session.add(TelegramInstagramAuditRow(
                id=str(event.id), created_at=event.created_at, data=event.model_dump_json(),
            ))
            session.flush()
            total = session.query(TelegramInstagramAuditRow).count()
            if total > self.MAX_AUDIT_RECORDS:
                stale_ids = [
                    r.id for r in session.query(TelegramInstagramAuditRow.id)
                    .order_by(TelegramInstagramAuditRow.created_at)
                    .limit(total - self.MAX_AUDIT_RECORDS).all()
                ]
                session.query(TelegramInstagramAuditRow).filter(
                    TelegramInstagramAuditRow.id.in_(stale_ids)
                ).delete(synchronize_session=False)
            session.commit()

    def audit_records(self, limit: int = 50) -> list[InstagramAuditRecord]:
        with SessionLocal() as session:
            rows = (
                session.query(TelegramInstagramAuditRow)
                .order_by(TelegramInstagramAuditRow.created_at.desc())
                .limit(limit).all()
            )
        return [InstagramAuditRecord.model_validate_json(r.data) for r in rows]

    def reset(self) -> None:
        with SessionLocal() as session:
            session.query(TelegramInstagramAuditRow).delete()
            session.commit()

    # -------------------------------------------------------------- status

    def status(self) -> TelegramInstagramStatus:
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
        return TelegramInstagramStatus(
            callback_secret_configured=bool(self.config.callback_secret),
            allowed_chat_configured=bool(self.config.allowed_chat_id),
            bot_reachable=bot_reachable,
            bot_username=bot_username,
            pending_drafts=len(media_pool_service.list_drafts(pending_only=True)),
            candidates_awaiting_decision=len(
                instagram_content_service.list_all(status=ContentStatus.proposed)
            ),
            error=error,
        )

    # ------------------------------------------------------------ outbound

    def notify(self, candidate_id: UUID) -> int:
        """Send the approval card for one existing candidate."""
        if not self.config.callback_secret:
            raise TelegramInstagramError(
                "TELEGRAM_INSTAGRAM_CALLBACK_SECRET is not set -- refusing to send a card "
                "whose buttons could not be verified when tapped."
            )
        try:
            candidate = instagram_content_service.get(candidate_id)
        except InstagramContentError as exc:
            raise TelegramInstagramError(str(exc)) from exc
        if candidate.status != ContentStatus.proposed:
            raise TelegramInstagramError(
                f"candidate {candidate_id} is {candidate.status.value}, not awaiting a decision"
            )

        secret = self.config.callback_secret
        keyboard = [[
            {"text": "✅ Freigeben",
             "callback_data": tokens.make_token(secret, candidate_id, tokens.PUBLISH_OK)},
            {"text": "❌ Ablehnen",
             "callback_data": tokens.make_token(secret, candidate_id, tokens.DECLINE)},
        ]]
        try:
            message_id = self._client.send_with_keyboard(_format_card(candidate), keyboard)
        except TelegramDeliveryError as exc:
            self._record("notify", False, str(exc), candidate_id)
            raise TelegramInstagramError(f"could not deliver the card: {exc}") from exc
        self._record("notify", True, f"message_id={message_id}", candidate_id)
        return message_id

    def finalize_next_and_notify(self, caption_draft: str | None = None) -> NotifyResult:
        """Take the next draft in posting order, give it a caption, send it.

        "Next" is the queue's own order, which is shoot-day order: the
        oldest day first, and that day exhausted before the next begins.
        Deliberately one draft per call rather than the whole backlog --
        finalizing writes a caption via a real Anthropic call, and fifty of
        those for posts that may never go out is not a decision to make by
        accident.
        """
        drafts = media_pool_service.list_drafts(pending_only=True)
        if not drafts:
            raise TelegramInstagramError("no pending drafts to finalize")
        draft = drafts[0]
        try:
            candidate = instagram_content_service.finalize_draft(
                draft.id, FinalizeDraftRequest(caption_draft=caption_draft)
            )
        except InstagramContentError as exc:
            self._record("finalize", False, str(exc))
            raise TelegramInstagramError(f"could not finalize draft {draft.id}: {exc}") from exc

        if candidate.status == ContentStatus.moderation_rejected:
            self._record("finalize", False, "moderation rejected", candidate.id)
            raise TelegramInstagramError(
                f"candidate {candidate.id} was rejected by moderation: {candidate.decision_reason}"
            )

        message_id = self.notify(candidate.id)
        return NotifyResult(candidate_id=candidate.id, message_id=message_id, from_draft_id=draft.id)

    # ------------------------------------------------------------- inbound

    def handle_update(self, raw_update: dict) -> ContentCandidate | None:
        """Process one Telegram Update. Returns the decided candidate, or
        None for an update this module has nothing to do with -- most
        updates a webhook receives are not button taps, and that is not an
        error."""
        update = TelegramWebhookUpdate.model_validate(raw_update)
        if not update.callback_query:
            return None

        query = update.callback_query
        chat_id = str(((query.get("message") or {}).get("chat") or {}).get("id", ""))
        actor = str((query.get("from") or {}).get("id", "")) or None

        # The allowlist is the primary defense: only the configured chat can
        # decide anything, whatever it sends.
        if not self.config.allowed_chat_id or chat_id != str(self.config.allowed_chat_id):
            self._record("callback", False, f"chat {chat_id!r} not allowed", actor=actor)
            raise TelegramInstagramError("callback from a chat that is not allowed to decide")

        if not self.config.callback_secret:
            self._record("callback", False, "callback secret not configured", actor=actor)
            raise TelegramInstagramError("TELEGRAM_INSTAGRAM_CALLBACK_SECRET is not set")

        try:
            candidate_id, action = tokens.verify_token(
                self.config.callback_secret, query.get("data", "")
            )
        except tokens.TokenError as exc:
            self._record("callback", False, str(exc), actor=actor)
            raise TelegramInstagramError(f"rejected callback token: {exc}") from exc

        # State is re-read now rather than trusted from the card, which may
        # be hours old: covers a double tap and a stale retry after the
        # candidate already moved on.
        try:
            current = instagram_content_service.get(candidate_id)
        except InstagramContentError as exc:
            self._record("callback", False, str(exc), candidate_id, actor)
            raise TelegramInstagramError(str(exc)) from exc
        if current.status != ContentStatus.proposed:
            self._record("callback", False, f"already {current.status.value}", candidate_id, actor)
            self._safe_send(f"Schon entschieden: {current.status.value}.")
            return current

        approved = action == tokens.PUBLISH_OK
        decision = ContentDecision(
            approved=approved,
            reason=f"Telegram tap by {actor or 'unknown'}",
        )
        try:
            decided = instagram_content_service.decide(candidate_id, decision)
        except InstagramContentError as exc:
            self._record("decide", False, str(exc), candidate_id, actor)
            raise TelegramInstagramError(str(exc)) from exc

        self._record("decide", True, decided.status.value, candidate_id, actor)
        if approved:
            self._safe_send(
                "Freigegeben. Nichts wurde gepostet -- Musik aussuchen und selbst posten, "
                "oder publish ausloesen."
            )
        else:
            self._safe_send("Abgelehnt. Die Medien bleiben vergeben, der Post geht nicht raus.")
        return decided

    def _safe_send(self, message: str) -> None:
        """A confirmation nobody depends on. The decision is already
        recorded by the time this runs, so a delivery failure here must not
        turn a successful decision into an error."""
        try:
            self._client.send("Instagram", message)
        except TelegramDeliveryError as exc:
            log.warning("telegram_instagram: could not send confirmation: %s", exc)


telegram_instagram_service = TelegramInstagramService()
