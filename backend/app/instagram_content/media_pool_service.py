from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import InstagramCuratedDraftRow, InstagramMediaPoolItemRow

from .analysis_completeness import analysis_is_complete
from .captured_at_resolution import (
    CapturedAtSource,
    is_plausible_capture_time,
    parse_capture_time_from_filename,
)
from .curation import analyze_gaps, curate
from .media_pool_models import (
    CapturedAtFromNameRequest,
    PendingUploadItem,
    PendingUploadList,
    ProcessedUploadedRequest,
    ProcessedUploadedResponse,
    CapturedAtFromNameResponse,
    ContentGapReport,
    CuratedDraft,
    MediaPoolIngestRequest,
    MediaPoolIngestResponse,
    MediaPoolItem,
    MediaPoolItemCreate,
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
        refuse_reset_in_production("the media pool and its drafts")
        with SessionLocal() as session:
            session.query(InstagramMediaPoolItemRow).delete()
            session.query(InstagramCuratedDraftRow).delete()
            session.commit()

    #: Overwritten when a placeholder analysis is replaced by a real one.
    #: Everything not listed here survives an update untouched -- identity
    #: (id, media_ref), usage state (used, used_in_candidate_id, used_at),
    #: the draft reservation, and the trim window, which comes from a
    #: separate analysis step and must not be clobbered by a re-ingest.
    _ANALYSIS_FIELDS = (
        "theme",
        "tags",
        "aesthetic_score",
        "captured_at",
        "captured_at_source",
        "source_group",
        "duration_seconds",
        "dominant_color_hex",
        "analyzed_at",
        "cover_timestamp_seconds",
    )

    def backfill_captured_at_source(self) -> dict[str, int]:
        """One-off migration for rows written before captured_at carried its
        source. Operates on the raw stored JSON, deliberately: those rows no
        longer validate (the model requires captured_at and
        captured_at_source to be set or unset together), so they cannot be
        loaded as models until this has run.

        Rows are filled with 'exif' only where that is a fact rather than a
        guess: before this field existed, the sole code path that ever set
        captured_at on an image was _read_captured_at(), which reads EXIF
        DateTimeOriginal out of the image bytes. No workflow has ever sent a
        captured_at of its own. A video could not have reached that path, so
        a video row carrying a timestamp would be unexplained -- those are
        counted and reported, never guessed at.

        Idempotent: rows that already carry a source are left alone.
        """
        filled = 0
        already = 0
        untouched_videos = 0
        with SessionLocal() as session:
            for row in session.query(InstagramMediaPoolItemRow).all():
                data = json.loads(row.data)
                if data.get("captured_at") is None:
                    continue
                if data.get("captured_at_source") is not None:
                    already += 1
                    continue
                if data.get("media_type") != "image":
                    untouched_videos += 1
                    continue
                data["captured_at_source"] = CapturedAtSource.exif.value
                row.data = json.dumps(data)
                filled += 1
            session.commit()
        return {
            "filled_exif": filled,
            "already_had_a_source": already,
            "non_image_left_untouched": untouched_videos,
        }

    def pending_uploads(self) -> PendingUploadList:
        """Processed files that still exist only on this disk.

        n8n asks rather than guesses: it has no view into which items were
        processed, and a directory listing would not say which media_ref a
        file belongs to or whether its upload already succeeded. Items whose
        processed version is already in Drive drop out here, so a repeated
        run uploads nothing twice.
        """
        items = [
            PendingUploadItem(
                media_ref=item.media_ref,
                processed_file=item.processed_file,
                media_type=item.media_type,
            )
            for item in self.list_all()
            if item.processed_file is not None and item.processed_media_ref is None
        ]
        return PendingUploadList(items=items, count=len(items))

    def record_processed_uploads(self, request: ProcessedUploadedRequest) -> ProcessedUploadedResponse:
        """Remember where the processed version ended up in Drive.

        Kept separate from the original media_ref rather than replacing it:
        the original stays the source of record, so a re-grade later starts
        from the footage as uploaded instead of from something already cut
        and colour-graded once.
        """
        recorded = 0
        unknown = 0
        with SessionLocal() as session:
            for entry in request.items:
                row = (
                    session.query(InstagramMediaPoolItemRow)
                    .filter(InstagramMediaPoolItemRow.media_ref == entry.media_ref)
                    .first()
                )
                if row is None:
                    unknown += 1
                    continue
                item = MediaPoolItem.model_validate_json(row.data)
                item.processed_media_ref = entry.processed_media_ref
                row.data = item.model_dump_json()
                recorded += 1
            session.commit()
        return ProcessedUploadedResponse(recorded=recorded, unknown_media_ref=unknown)

    def captured_at_from_names(self, request: CapturedAtFromNameRequest) -> CapturedAtFromNameResponse:
        """Recovers a capture date from a file name, for items already in
        the pool with a real analysis.

        Renaming a file in Drive keeps its id, so the media_ref -- and with
        it the paid-for analysis -- survives. What does not happen by itself
        is anyone reading the new name: the ingest pre-filter skips a
        media_ref that is already fully analyzed, so those files are never
        downloaded or looked at again. This is the way in for the name alone.

        Never overwrites an existing captured_at: a value already there came
        from EXIF or the container, and a name typed later is not grounds to
        replace it. A name without a readable date is simply skipped -- the
        item keeps no date at all rather than being given an invented one.

        Costs nothing: no download, no frames, no vision call.
        """
        filled = 0
        already = 0
        no_date = 0
        unknown = 0
        filled_refs: list[str] = []
        with SessionLocal() as session:
            for entry in request.items:
                row = (
                    session.query(InstagramMediaPoolItemRow)
                    .filter(InstagramMediaPoolItemRow.media_ref == entry.media_ref)
                    .first()
                )
                if row is None:
                    unknown += 1
                    continue
                item = MediaPoolItem.model_validate_json(row.data)
                if item.captured_at is not None:
                    already += 1
                    continue
                parsed = parse_capture_time_from_filename(entry.file_name)
                if not is_plausible_capture_time(parsed):
                    no_date += 1
                    continue
                item.captured_at = parsed
                item.captured_at_source = CapturedAtSource.filename
                row.data = item.model_dump_json()
                filled += 1
                filled_refs.append(entry.media_ref)
            session.commit()
        return CapturedAtFromNameResponse(
            filled=filled, already_had_one=already, no_date_in_name=no_date,
            unknown_media_ref=unknown, filled_refs=filled_refs,
        )

    def backfill_content_day(self) -> dict[str, int]:
        """One-off migration for drafts created before content_day existed.

        Without it every already-pending draft sorts as "day unknown" and
        lands behind everything dated, which is exactly backwards: those are
        the oldest drafts in the queue. The day is not guessed at -- it is
        re-derived from the draft's own media items, the same source
        curate() grouped them by in the first place.

        A draft whose items carry no captured_at keeps content_day=None.
        That is the honest answer, not a failure. Idempotent: a draft that
        already has a day is left alone.
        """
        filled = 0
        already = 0
        no_date = 0
        with SessionLocal() as session:
            for row in session.query(InstagramCuratedDraftRow).all():
                draft = CuratedDraft.model_validate_json(row.data)
                if draft.content_day is not None:
                    already += 1
                    continue
                days = []
                for item_id in draft.media_item_ids:
                    item_row = session.get(InstagramMediaPoolItemRow, str(item_id))
                    if item_row is None:
                        continue
                    item = MediaPoolItem.model_validate_json(item_row.data)
                    if item.captured_at is not None:
                        days.append(item.captured_at.date())
                if not days:
                    no_date += 1
                    continue
                draft.content_day = min(days)
                row.data = draft.model_dump_json()
                filled += 1
            session.commit()
        return {"filled": filled, "already_had_a_day": already, "no_dated_items": no_date}

    def ingest(self, request: MediaPoolIngestRequest) -> MediaPoolIngestResponse:
        ingested = 0
        skipped = 0
        updated = 0
        with SessionLocal() as session:
            for create in request.items:
                exists = (
                    session.query(InstagramMediaPoolItemRow)
                    .filter(InstagramMediaPoolItemRow.media_ref == create.media_ref)
                    .first()
                )
                if exists is not None:
                    existing = MediaPoolItem.model_validate_json(exists.data)
                    if analysis_is_complete(existing) or not analysis_is_complete(create):
                        # Either the stored analysis is real (nothing to gain by
                        # overwriting it), or the incoming one is no better than
                        # the placeholder already there.
                        skipped += 1
                        continue
                    exists.data = self._with_analysis_from(existing, create).model_dump_json()
                    updated += 1
                    continue
                item = MediaPoolItem(**create.model_dump())
                session.add(InstagramMediaPoolItemRow(
                    id=str(item.id), media_ref=item.media_ref, data=item.model_dump_json(),
                ))
                session.flush()  # so a later duplicate within this same batch sees this one
                ingested += 1
            session.commit()
        return MediaPoolIngestResponse(
            ingested=ingested,
            skipped_duplicates=skipped,
            pool_size_unused=len(self.list_available()),
            updated_incomplete=updated,
        )

    def _with_analysis_from(self, existing: MediaPoolItem, create: MediaPoolItemCreate) -> MediaPoolItem:
        """Copies the freshly analyzed fields onto an existing item, leaving
        its identity, usage state, draft reservation and trim window alone.
        A re-analysis must be able to improve a placeholder entry without
        ever detaching it from the draft that already reserved it."""
        updated = existing.model_copy()
        for field in self._ANALYSIS_FIELDS:
            setattr(updated, field, getattr(create, field))
        return updated

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
                    content_day=group.day,
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
        if not pending_only:
            return sorted(drafts, key=lambda d: d.created_at, reverse=True)
        pending = [d for d in drafts if not d.finalized and not d.discarded]
        # This is the actual work queue Brano decides from -- it must reflect
        # posting order (oldest shoot day exhausted before the next begins),
        # not creation time, or a later curation run could surface a newer
        # day's draft ahead of an older day's still-pending one and content
        # from two days would end up interleaved on the grid.
        return sorted(
            pending,
            key=lambda d: (d.content_day is None, d.content_day or date.max, d.created_at),
        )

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

    def release_items_used_by(self, candidate_id: UUID) -> int:
        """Reverses mark_finalized() for a candidate that turned out to be a
        dead end (e.g. a publish that failed for good) -- its media items
        go back into the available pool instead of staying blocked forever
        as 'used' with nothing left able to reclaim them. No indexed column
        for used_in_candidate_id exists, so this scans like list_all()
        does; fine at this table's scale."""
        released = 0
        with SessionLocal() as session:
            rows = session.query(InstagramMediaPoolItemRow).all()
            for row in rows:
                item = MediaPoolItem.model_validate_json(row.data)
                if item.used_in_candidate_id != candidate_id:
                    continue
                item.used = False
                item.used_in_candidate_id = None
                item.used_at = None
                item.reserved_in_draft_id = None
                row.data = item.model_dump_json()
                released += 1
            session.commit()
        return released


media_pool_service = MediaPoolService()
