from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.db import SessionLocal
from app.db_models import InstagramCuratedDraftRow, InstagramMediaPoolItemRow

from .curation import analyze_gaps, curate
from .media_pool_models import (
    ContentGapReport,
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
    item twice across runs while a draft is still pending.

    Persisted via the same SessionLocal infrastructure the rest of this
    codebase now uses -- previously the pool, its drafts, and the
    duplicate-media_ref index all lived only in process memory. Named
    directly by an external test pass: "Instagram-Entwuerfe,
    Medienreservierungen" among the state that silently disappeared on
    restart.
    """

    def reset(self) -> None:
        with SessionLocal() as session:
            session.query(InstagramMediaPoolItemRow).delete()
            session.query(InstagramCuratedDraftRow).delete()
            session.commit()

    def ingest(self, request: MediaPoolIngestRequest) -> MediaPoolIngestResponse:
        ingested = 0
        skipped = 0
        with SessionLocal() as session:
            for create in request.items:
                exists = (
                    session.query(InstagramMediaPoolItemRow)
                    .filter(InstagramMediaPoolItemRow.media_ref == create.media_ref)
                    .first()
                )
                if exists is not None:
                    skipped += 1
                    continue
                item = MediaPoolItem(**create.model_dump())
                session.add(InstagramMediaPoolItemRow(
                    id=str(item.id), media_ref=item.media_ref, data=item.model_dump_json(),
                ))
                session.flush()  # so a later duplicate within this same batch sees this one
                ingested += 1
            session.commit()
        return MediaPoolIngestResponse(
            ingested=ingested, skipped_duplicates=skipped, pool_size_unused=len(self.list_available())
        )

    def list_all(self) -> list[MediaPoolItem]:
        with SessionLocal() as session:
            rows = session.query(InstagramMediaPoolItemRow).all()
        items = [MediaPoolItem.model_validate_json(r.data) for r in rows]
        return sorted(items, key=lambda i: i.analyzed_at, reverse=True)

    def list_available(self) -> list[MediaPoolItem]:
        return [item for item in self.list_all() if item.available]

    def get(self, item_id: UUID) -> MediaPoolItem:
        with SessionLocal() as session:
            row = session.get(InstagramMediaPoolItemRow, str(item_id))
        if row is None:
            raise MediaPoolError("Media pool item not found")
        return MediaPoolItem.model_validate_json(row.data)

    def _save_item(self, session, item: MediaPoolItem) -> None:
        row = session.get(InstagramMediaPoolItemRow, str(item.id))
        row.data = item.model_dump_json()

    def set_trim_recommendation(self, item_id: UUID, start_seconds: float, end_seconds: float, reasoning: str) -> MediaPoolItem:
        with SessionLocal() as session:
            row = session.get(InstagramMediaPoolItemRow, str(item_id))
            if row is None:
                raise MediaPoolError("Media pool item not found")
            item = MediaPoolItem.model_validate_json(row.data)
            item.recommended_trim_start_seconds = start_seconds
            item.recommended_trim_end_seconds = end_seconds
            item.trim_reasoning = reasoning
            row.data = item.model_dump_json()
            session.commit()
        return item

    # -- curation drafts ------------------------------------------------

    def content_gaps(self) -> ContentGapReport:
        return analyze_gaps(self.list_available())

    def run_curation(self, max_groups: int = 10) -> list[CuratedDraft]:
        groups = curate(self.list_available(), max_groups=max_groups)
        drafts: list[CuratedDraft] = []
        with SessionLocal() as session:
            for group in groups:
                draft = CuratedDraft(
                    theme=group.theme,
                    reasoning=group.reasoning,
                    media_item_ids=[item.id for item in group.media_items],
                )
                session.add(InstagramCuratedDraftRow(id=str(draft.id), data=draft.model_dump_json()))
                for item in group.media_items:
                    item.reserved_in_draft_id = draft.id
                    self._save_item(session, item)
                drafts.append(draft)
            session.commit()
        return drafts

    def list_drafts(self, *, pending_only: bool = False) -> list[CuratedDraft]:
        with SessionLocal() as session:
            rows = session.query(InstagramCuratedDraftRow).all()
        drafts = [CuratedDraft.model_validate_json(r.data) for r in rows]
        if pending_only:
            drafts = [d for d in drafts if not d.finalized and not d.discarded]
        return sorted(drafts, key=lambda d: d.created_at, reverse=True)

    def get_draft(self, draft_id: UUID) -> CuratedDraft:
        with SessionLocal() as session:
            row = session.get(InstagramCuratedDraftRow, str(draft_id))
        if row is None:
            raise MediaPoolError("Curated draft not found")
        return CuratedDraft.model_validate_json(row.data)

    def draft_media_items(self, draft: CuratedDraft) -> list[MediaPoolItem]:
        return [self.get(item_id) for item_id in draft.media_item_ids]

    def discard_draft(self, draft_id: UUID) -> CuratedDraft:
        with SessionLocal() as session:
            row = session.get(InstagramCuratedDraftRow, str(draft_id))
            if row is None:
                raise MediaPoolError("Curated draft not found")
            draft = CuratedDraft.model_validate_json(row.data)
            if draft.finalized:
                raise MediaPoolError("Cannot discard an already-finalized draft")
            draft.discarded = True
            for item_id in draft.media_item_ids:
                item_row = session.get(InstagramMediaPoolItemRow, str(item_id))
                item = MediaPoolItem.model_validate_json(item_row.data)
                if item.reserved_in_draft_id == draft_id:
                    item.reserved_in_draft_id = None
                    item_row.data = item.model_dump_json()
            row.data = draft.model_dump_json()
            session.commit()
        return draft

    def mark_finalized(self, draft_id: UUID, candidate_id: UUID) -> None:
        with SessionLocal() as session:
            row = session.get(InstagramCuratedDraftRow, str(draft_id))
            if row is None:
                raise MediaPoolError("Curated draft not found")
            draft = CuratedDraft.model_validate_json(row.data)
            if draft.finalized or draft.discarded:
                raise MediaPoolError(f"Draft {draft_id} is already {'finalized' if draft.finalized else 'discarded'}")
            now = datetime.now(timezone.utc)
            for item_id in draft.media_item_ids:
                item_row = session.get(InstagramMediaPoolItemRow, str(item_id))
                item = MediaPoolItem.model_validate_json(item_row.data)
                item.used = True
                item.used_in_candidate_id = candidate_id
                item.used_at = now
                item_row.data = item.model_dump_json()
            draft.finalized = True
            draft.finalized_candidate_id = candidate_id
            row.data = draft.model_dump_json()
            session.commit()


media_pool_service = MediaPoolService()
