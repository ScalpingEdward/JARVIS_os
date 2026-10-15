"""One Drive file, one pool row -- and what to do with the five that got in
twice before the ingest check and the insert became one step."""

from __future__ import annotations

import threading

import pytest

from app.db import SessionLocal
from app.db_models import InstagramMediaPoolItemRow
from app.instagram_content.media_pool_models import (
    MediaPoolIngestRequest,
    MediaPoolItem,
    MediaPoolItemCreate,
)
from app.instagram_content.media_pool_service import MediaPoolService, media_pool_service


def _create(ref="same-file", theme="beach", score=0.7):
    return MediaPoolItemCreate(media_ref=ref, media_type="image", theme=theme, aesthetic_score=score)


@pytest.fixture(autouse=True)
def _clean():
    MediaPoolService().reset()
    yield


def _row_count(ref: str) -> int:
    with SessionLocal() as session:
        return session.query(InstagramMediaPoolItemRow).filter(
            InstagramMediaPoolItemRow.media_ref == ref
        ).count()


def test_two_ingests_of_the_same_file_at_the_same_time_leave_one_row():
    """Reproduces the real cause: n8n retried a request whose answer got
    lost, and both attempts looked up the media_ref before either had
    committed."""
    barrier = threading.Barrier(2)

    def ingest():
        barrier.wait(timeout=5)
        media_pool_service.ingest(MediaPoolIngestRequest(items=[_create()]))

    threads = [threading.Thread(target=ingest) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert _row_count("same-file") == 1


def _force_duplicate(ref: str, **fields) -> None:
    """Writes a second row for a media_ref directly, the way the race did."""
    item = MediaPoolItem(**{**_create(ref=ref).model_dump(), **fields})
    with SessionLocal() as session:
        session.add(InstagramMediaPoolItemRow(
            id=str(item.id), media_ref=ref, data=item.model_dump_json()))
        session.commit()


def test_deduplicate_reports_before_it_deletes_anything():
    media_pool_service.ingest(MediaPoolIngestRequest(items=[_create()]))
    _force_duplicate("same-file")

    report = media_pool_service.deduplicate()

    assert report["duplicate_refs"] == 1
    assert report["applied"] is False
    assert _row_count("same-file") == 2, "a dry run must not delete a paid analysis"


def test_deduplicate_keeps_the_row_the_work_hangs_off():
    media_pool_service.ingest(MediaPoolIngestRequest(items=[_create()]))
    _force_duplicate("same-file", processed_file="same-file.jpg")

    report = media_pool_service.deduplicate(apply=True)

    assert _row_count("same-file") == 1
    kept = [i for i in media_pool_service.list_all() if i.media_ref == "same-file"][0]
    assert kept.processed_file == "same-file.jpg"
    assert report["details"][0]["kept"] == str(kept.id)
    assert report["details"][0]["dropped_were_planned"] == []


def test_a_pool_without_duplicates_is_left_alone():
    media_pool_service.ingest(MediaPoolIngestRequest(items=[_create("a"), _create("b")]))
    assert media_pool_service.deduplicate(apply=True) == {
        "duplicate_refs": 0, "applied": True, "drafts_touched": 0,
        "drafts_discarded": 0, "details": []}


def _draft_with(item_ids, theme="beach"):
    from app.db_models import InstagramCuratedDraftRow
    from app.instagram_content.media_pool_models import CuratedDraft

    draft = CuratedDraft(media_item_ids=item_ids, theme=theme, reasoning="test")
    with SessionLocal() as session:
        session.add(InstagramCuratedDraftRow(id=str(draft.id), data=draft.model_dump_json()))
        session.commit()
    return draft.id


def _draft(draft_id):
    from app.db_models import InstagramCuratedDraftRow
    from app.instagram_content.media_pool_models import CuratedDraft

    with SessionLocal() as session:
        return CuratedDraft.model_validate_json(
            session.get(InstagramCuratedDraftRow, str(draft_id)).data)


def test_a_dropped_row_is_taken_out_of_the_draft_that_planned_it():
    """The real damage of a duplicate: the same file planned into two posts.
    Deleting the row alone would leave the second draft pointing at nothing."""
    media_pool_service.ingest(MediaPoolIngestRequest(items=[_create(), _create("other")]))
    pool = {i.media_ref: i.id for i in media_pool_service.list_all()}
    _force_duplicate("same-file", processed_file="same-file.jpg")
    twin = [i for i in media_pool_service.list_all()
            if i.media_ref == "same-file" and i.processed_file][0]

    keeps = _draft_with([twin.id, pool["other"]])
    loses = _draft_with([pool["same-file"]])

    report = media_pool_service.deduplicate(apply=True)

    assert report["drafts_touched"] == 1
    assert report["drafts_discarded"] == 1
    assert _draft(keeps).media_item_ids == [twin.id, pool["other"]], "the kept row's draft is untouched"
    assert _draft(loses).discarded is True, "a draft left with nothing is discarded, not left empty"
