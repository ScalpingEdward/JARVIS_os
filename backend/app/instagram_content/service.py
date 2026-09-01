from __future__ import annotations

from uuid import UUID

from .models import ContentCandidate, ContentCandidateCreate, ContentDecision, ContentStatus
from .moderation import moderate
from .publisher import N8nInstagramPublisher, N8nInstagramPublisherError


class InstagramContentError(ValueError):
    pass


class InstagramContentService:
    """Stateful gateway between proposed content and the real n8n publish step.

    Nothing reaches n8n unless a human explicitly approved it first. This is
    the same simulation/execution separation the master plan requires
    elsewhere: propose and score are simulation, publish is the one real
    execution boundary, and it is gated by ContentStatus.approved only.
    """

    def __init__(self, publisher: N8nInstagramPublisher | None = None) -> None:
        self._items: dict[UUID, ContentCandidate] = {}
        self._publisher = publisher or N8nInstagramPublisher()

    def reset(self) -> None:
        self._items.clear()

    def propose(self, payload: ContentCandidateCreate) -> ContentCandidate:
        recent_captions = [item.caption_draft.strip() for item in self._items.values()]
        result = moderate(payload, recent_captions)

        item = ContentCandidate(**payload.model_dump())
        item.moderation_warnings = list(result.warnings)

        if not result.passed:
            item.status = ContentStatus.moderation_rejected
            item.decision_reason = "Auto-rejected by moderation: " + "; ".join(result.violations)
            item.audit_log.append(item.decision_reason)
        else:
            item.audit_log.append(f"Proposed with aesthetic_score={item.aesthetic_score:.2f}")
            if result.warnings:
                item.audit_log.append("Moderation warnings (still pending human review): " + "; ".join(result.warnings))

        self._items[item.id] = item
        return item

    def list_all(self, status: ContentStatus | None = None) -> list[ContentCandidate]:
        items = list(self._items.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get(self, candidate_id: UUID) -> ContentCandidate:
        item = self._items.get(candidate_id)
        if item is None:
            raise InstagramContentError("Content candidate not found")
        return item

    def decide(self, candidate_id: UUID, decision: ContentDecision) -> ContentCandidate:
        item = self.get(candidate_id)
        if item.status not in (ContentStatus.proposed, ContentStatus.moderation_rejected):
            raise InstagramContentError(f"Cannot decide on a candidate in status {item.status}")

        was_moderation_rejected = item.status == ContentStatus.moderation_rejected

        if decision.edited_caption is not None:
            item.caption_draft = decision.edited_caption

        item.status = ContentStatus.approved if decision.approved else ContentStatus.rejected
        item.decision_reason = decision.reason
        item.audit_log.append(f"{'Approved' if decision.approved else 'Rejected'}: {decision.reason}")
        if was_moderation_rejected and decision.approved:
            item.audit_log.append("Human override: approved despite automated moderation rejection.")
        return item

    def publish(self, candidate_id: UUID) -> ContentCandidate:
        item = self.get(candidate_id)
        if item.status != ContentStatus.approved:
            raise InstagramContentError(
                f"Cannot publish a candidate in status {item.status}; it must be explicitly approved first"
            )

        try:
            media_id = self._publisher.publish(
                image_source_ref=item.image_source_ref,
                caption=item.caption_draft,
                request_id=str(item.id),
            )
        except N8nInstagramPublisherError as exc:
            item.status = ContentStatus.post_failed
            item.audit_log.append(f"Publish failed: {exc}")
            raise InstagramContentError(str(exc)) from exc

        item.status = ContentStatus.posted
        item.published_media_id = media_id
        item.audit_log.append(f"Published via n8n, media_id={media_id}")
        return item


instagram_content_service = InstagramContentService()
