from __future__ import annotations

from uuid import UUID

from .edit_plan import build_edit_plan
from .format_decision import decide_format
from .hook import check_hook
from .media_pool_models import FinalizeDraftRequest
from .media_pool_service import MediaPoolError, media_pool_service
from .models import ContentCandidate, ContentCandidateCreate, ContentDecision, ContentStatus, MediaItem
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
        hook_warnings = check_hook(payload.caption_draft)

        post_format, format_reasoning = decide_format(payload.media_items)
        edit_plan = build_edit_plan(payload.media_items, post_format)

        item = ContentCandidate(
            media_items=payload.media_items,
            post_format=post_format,
            format_reasoning=format_reasoning,
            edit_plan=edit_plan,
            caption_draft=payload.caption_draft,
            aesthetic_notes=payload.aesthetic_notes,
        )
        item.moderation_warnings = list(result.warnings)
        item.hook_warnings = hook_warnings

        if not result.passed:
            item.status = ContentStatus.moderation_rejected
            item.decision_reason = "Auto-rejected by moderation: " + "; ".join(result.violations)
            item.audit_log.append(item.decision_reason)
        else:
            item.audit_log.append(f"Proposed as {post_format.value}: {format_reasoning}")
            if result.warnings:
                item.audit_log.append("Moderation warnings (still pending human review): " + "; ".join(result.warnings))
            if hook_warnings:
                item.audit_log.append("Hook warnings: " + "; ".join(hook_warnings))

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
                media_items=item.media_items,
                post_format=item.post_format,
                edit_plan=item.edit_plan,
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

    def finalize_draft(self, draft_id: UUID, request: FinalizeDraftRequest) -> ContentCandidate:
        """Turns a curated draft (media already grouped and reserved out of
        the pool) into a real, moderated candidate, once a caption exists
        for it. AURON does not write the caption itself here -- that's
        still a separate step (e.g. n8n's existing Claude-based captioning),
        deliberately not duplicated inside this pipeline.

        Pool items are only marked permanently 'used' if the candidate
        clears moderation. A moderation rejection (e.g. a bad caption)
        leaves the draft pending so a corrected caption can be retried
        without burning fresh photos on what was really a caption problem.
        """
        try:
            draft = media_pool_service.get_draft(draft_id)
        except MediaPoolError as exc:
            raise InstagramContentError(str(exc)) from exc

        if draft.finalized or draft.discarded:
            raise InstagramContentError(f"Draft {draft_id} is already {'finalized' if draft.finalized else 'discarded'}")

        pool_items = media_pool_service.draft_media_items(draft)
        media_items = [
            MediaItem(
                media_ref=pi.media_ref,
                media_type=pi.media_type,
                aesthetic_score=pi.aesthetic_score,
                duration_seconds=pi.duration_seconds,
            )
            for pi in pool_items
        ]

        candidate = self.propose(
            ContentCandidateCreate(
                media_items=media_items,
                caption_draft=request.caption_draft,
                aesthetic_notes=request.aesthetic_notes or f"Curated from theme '{draft.theme}': {draft.reasoning}",
            )
        )

        if candidate.status != ContentStatus.moderation_rejected:
            media_pool_service.mark_finalized(draft_id, candidate.id)
            candidate.audit_log.append(f"Finalized from curated draft {draft_id} (theme: {draft.theme}).")
        else:
            candidate.audit_log.append(
                f"Finalization attempt from draft {draft_id} was moderation-rejected; draft remains pending "
                "for a retry with a corrected caption -- photos were not consumed."
            )

        return candidate


instagram_content_service = InstagramContentService()
