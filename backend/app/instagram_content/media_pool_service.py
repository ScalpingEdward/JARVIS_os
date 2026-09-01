from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from .curation import curate
from .media_pool_models import (
    CuratedDraft,
    MediaPoolIngestRequest,
    MediaPoolIngestResponse,
    MediaPoolItem,
)


class MediaPoolError(ValueError):
    pass


class MediaPoolService:
    """The catalog AURON curates candidates from, plus the draft workflow
    on top of it. Enforces exactly what Brano asked for: every photo/video
    can only ever end up in one post, and curation never proposes the same
    item twice across runs while a draft is still pending."""

    def __init__(self) -> None:
        self._items: dict[UUID, MediaPoolItem] = {}
        self._refs_seen: set[str] = set()
        self._drafts: dict[UUID, CuratedDraft] = {}

    def reset(self) -> None:
        self._items.clear()
        self._refs_seen.clear()
        self._drafts.clear()

    def ingest(self, request: MediaPoolIngestRequest) -> MediaPoolIngestResponse:
        ingested = 0
        skipped = 0
        for create in request.items:
            if create.media_ref in self._refs_seen:
                skipped += 1
                continue
            item = MediaPoolItem(**create.model_dump())
            self._items[item.id] = item
            self._refs_seen.add(item.media_ref)
            ingested += 1
        return MediaPoolIngestResponse(
            ingested=ingested, skipped_duplicates=skipped, pool_size_unused=len(self.list_available())
        )

    def list_all(self) -> list[MediaPoolItem]:
        return sorted(self._items.values(), key=lambda i: i.analyzed_at, reverse=True)

    def list_available(self) -> list[MediaPoolItem]:
        return [item for item in self._items.values() if item.available]

    def get(self, item_id: UUID) -> MediaPoolItem:
        item = self._items.get(item_id)
        if item is None:
            raise MediaPoolError("Media pool item not found")
        return item

    # -- curation drafts ------------------------------------------------

    def run_curation(self, max_groups: int = 10) -> list[CuratedDraft]:
        groups = curate(self.list_available(), max_groups=max_groups)
        drafts: list[CuratedDraft] = []
        for group in groups:
            draft = CuratedDraft(
                theme=group.theme,
                reasoning=group.reasoning,
                media_item_ids=[item.id for item in group.media_items],
            )
            for item in group.media_items:
                item.reserved_in_draft_id = draft.id
            self._drafts[draft.id] = draft
            drafts.append(draft)
        return drafts

    def list_drafts(self, *, pending_only: bool = False) -> list[CuratedDraft]:
        drafts = list(self._drafts.values())
        if pending_only:
            drafts = [d for d in drafts if not d.finalized and not d.discarded]
        return sorted(drafts, key=lambda d: d.created_at, reverse=True)

    def get_draft(self, draft_id: UUID) -> CuratedDraft:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise MediaPoolError("Curated draft not found")
        return draft

    def draft_media_items(self, draft: CuratedDraft) -> list[MediaPoolItem]:
        return [self.get(item_id) for item_id in draft.media_item_ids]

    def discard_draft(self, draft_id: UUID) -> CuratedDraft:
        draft = self.get_draft(draft_id)
        if draft.finalized:
            raise MediaPoolError("Cannot discard an already-finalized draft")
        draft.discarded = True
        for item_id in draft.media_item_ids:
            item = self.get(item_id)
            if item.reserved_in_draft_id == draft_id:
                item.reserved_in_draft_id = None
        return draft

    def mark_finalized(self, draft_id: UUID, candidate_id: UUID) -> None:
        draft = self.get_draft(draft_id)
        if draft.finalized or draft.discarded:
            raise MediaPoolError(f"Draft {draft_id} is already {'finalized' if draft.finalized else 'discarded'}")
        now = datetime.now(timezone.utc)
        for item_id in draft.media_item_ids:
            item = self.get(item_id)
            item.used = True
            item.used_in_candidate_id = candidate_id
            item.used_at = now
        draft.finalized = True
        draft.finalized_candidate_id = candidate_id


media_pool_service = MediaPoolService()
