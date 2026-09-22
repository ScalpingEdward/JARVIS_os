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

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import TelegramInstagramAuditRow
from app.instagram_content.media_pool_models import FinalizeDraftRequest
from app.instagram_content.media_pool_service import media_pool_service
from app.instagram_content.models import ContentCandidate, ContentDecision, ContentStatus, MediaType
from app.instagram_content.service import InstagramContentError, instagram_content_service
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError

from . import tokens
from .preview import PostPreviewSender, PreviewError
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


def _escape_markdown(text: str) -> str:
    """The card is sent with legacy Markdown; an underscore in a hashtag
    like #trading_life would otherwise open an italic span and Telegram
    rejects the whole message."""
    for char in ("\\", "_", "*", "`", "["):
        text = text.replace(char, "\\" + char)
    return text


def _format_card(candidate: ContentCandidate, preview_problem: str | None = None) -> str:
    """Everything needed to decide. The post itself arrives just above this
    card as numbered photos/videos (see preview.py); if that failed, the
    card says so in its first lines rather than pretending it was shown.
    """
    lines = []
    if preview_problem:
        lines += [f"⚠️ Vorschau fehlt: {_escape_markdown(preview_problem)}", ""]
    lines += [
        f"*Instagram: {candidate.post_format.value} zur Freigabe*",
        f"{len(candidate.media_items)} Medium/Medien"
        f" · Score {sum(m.aesthetic_score for m in candidate.media_items) / len(candidate.media_items):.2f}",
        "",
        _escape_markdown(candidate.caption_draft[:900]),
    ]
    if len(candidate.media_items) > 1:
        # The preview above is a Telegram album, which lays the items out as
        # a collage -- the posting order is not obvious from it.
        kinds = ["Video" if m.media_type == MediaType.video else "Foto" for m in candidate.media_items]
        order = " → ".join(f"{i + 1} {k}" + (" (Hook)" if i == 0 else "") for i, k in enumerate(kinds))
        lines += ["", f"Reihenfolge: {order}"]
    if candidate.edit_warnings:
        lines += ["", "⚠️ " + "\n⚠️ ".join(candidate.edit_warnings)]
    if candidate.moderation_warnings:
        lines += ["", "Moderation: " + "; ".join(candidate.moderation_warnings)]
    if candidate.hook_warnings:
        lines += ["", "Hook: " + "; ".join(candidate.hook_warnings)]
    lines += ["", f"`{candidate.id}`"]
    return "\n".join(lines)


class TelegramInstagramService:
    #: Bounded, same reasoning as the other Telegram audit logs: a
    #: recent-activity window, not a permanent archive.
    MAX_AUDIT_RECORDS = 500

    def __init__(
        self,
        config: TelegramInstagramConfig | None = None,
        client: TelegramDeliveryClient | None = None,
        preview: PostPreviewSender | None = None,
    ) -> None:
        self.config = config or TelegramInstagramConfig()
        self._client = client or TelegramDeliveryClient()
        self._preview = preview or PostPreviewSender()

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
        refuse_reset_in_production("telegram_instagram's audit log")
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

        preview_problem = None
        try:
            self._preview.send(candidate)
        except PreviewError as exc:
            # Still send the card: the decision can wait for a retry, but
            # Brano should see that something is missing rather than nothing.
            preview_problem = str(exc)
            self._record("preview", False, preview_problem, candidate_id)

        secret = self.config.callback_secret
        keyboard = [[
            {"text": "✅ Freigeben",
             "callback_data": tokens.make_token(secret, candidate_id, tokens.PUBLISH_OK)},
            {"text": "❌ Ablehnen",
             "callback_data": tokens.make_token(secret, candidate_id, tokens.DECLINE)},
        ]]
        count = len(candidate.media_items)
        if count > 1:
            removes = [
                {"text": f"{i + 1} raus",
                 "callback_data": tokens.make_token(secret, candidate_id, tokens.remove_action(i))}
                for i in range(min(count, 10))
            ]
            keyboard += [removes[i:i + 5] for i in range(0, len(removes), 5)]
        try:
            message_id = self._client.send_with_keyboard(_format_card(candidate, preview_problem), keyboard)
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

        # Whatever was tapped, this card is spent: a removal shifts every
        # position after it, and a decision ends the card's purpose. Leaving
        # the buttons would invite a second tap on a stale layout.
        message_id = (query.get("message") or {}).get("message_id")
        if message_id is not None:
            self._safe_clear_keyboard(int(message_id))

        if action in tokens.REMOVE_ACTIONS:
            index = int(action)
            try:
                updated = instagram_content_service.remove_media_item(
                    candidate_id, index, f"Telegram tap by {actor or 'unknown'}"
                )
            except InstagramContentError as exc:
                self._record("remove", False, str(exc), candidate_id, actor)
                self._safe_send(f"Konnte Nr. {index + 1} nicht entfernen: {exc}")
                raise TelegramInstagramError(str(exc)) from exc
            self._record("remove", True, f"item {index + 1}", candidate_id, actor)
            self._safe_send(f"Nr. {index + 1} ist raus. Neue Vorschau kommt.")
            self.notify(candidate_id)
            return updated

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

    def _safe_clear_keyboard(self, message_id: int) -> None:
        try:
            self._client.clear_keyboard(message_id)
        except TelegramDeliveryError as exc:
            log.warning("telegram_instagram: could not clear the old card's buttons: %s", exc)

    def _safe_send(self, message: str) -> None:
        """A confirmation nobody depends on. The decision is already
        recorded by the time this runs, so a delivery failure here must not
        turn a successful decision into an error."""
        try:
            self._client.send("Instagram", message)
        except TelegramDeliveryError as exc:
            log.warning("telegram_instagram: could not send confirmation: %s", exc)


telegram_instagram_service = TelegramInstagramService()
