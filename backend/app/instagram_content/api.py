from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .media_pool_models import (
    CuratedDraft,
    CuratedDraftList,
    FinalizeDraftRequest,
    MediaAnalyzeAndIngestRequest,
    MediaAnalyzeAndIngestResponse,
    MediaPoolIngestRequest,
    MediaPoolIngestResponse,
    MediaPoolList,
)
from .analyze_and_ingest import analyze_and_ingest
from .media_pool_service import MediaPoolError, media_pool_service
from .models import ContentCandidate, ContentCandidateCreate, ContentCandidateList, ContentDecision, ContentStatus
from .posting_schedule import NOTE, PostingWindow, suggested_windows_for_weekday
from .service import InstagramContentError, instagram_content_service
from .vision_analysis import AnthropicVisionAnalyzer

router = APIRouter(prefix="/v1/instagram", tags=["instagram-content"])


class PostingScheduleResponse(BaseModel):
    windows: list[PostingWindow]
    note: str


@router.post("/candidates", response_model=ContentCandidate)
def propose(payload: ContentCandidateCreate) -> ContentCandidate:
    return instagram_content_service.propose(payload)


@router.get("/candidates", response_model=ContentCandidateList)
def list_candidates(status: ContentStatus | None = None) -> ContentCandidateList:
    items = instagram_content_service.list_all(status=status)
    return ContentCandidateList(items=items, count=len(items))


@router.get("/candidates/{candidate_id}", response_model=ContentCandidate)
def get_candidate(candidate_id: UUID) -> ContentCandidate:
    try:
        return instagram_content_service.get(candidate_id)
    except InstagramContentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/decision", response_model=ContentCandidate)
def decide(candidate_id: UUID, decision: ContentDecision) -> ContentCandidate:
    try:
        return instagram_content_service.decide(candidate_id, decision)
    except InstagramContentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/publish", response_model=ContentCandidate)
def publish(candidate_id: UUID) -> ContentCandidate:
    """The one real execution boundary: triggers the n8n webhook. Requires
    status == approved; there is no path from 'proposed' straight to here."""
    try:
        return instagram_content_service.publish(candidate_id)
    except InstagramContentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/posting-schedule/{weekday}", response_model=PostingScheduleResponse)
def posting_schedule(weekday: int) -> PostingScheduleResponse:
    """weekday: 0=Monday .. 6=Sunday. Generic, well-documented Instagram
    usage windows -- not this account's own analytics; see the note field."""
    try:
        windows = suggested_windows_for_weekday(weekday)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PostingScheduleResponse(windows=windows, note=NOTE)


# -- media pool: the source folder's analyzed contents -----------------------


@router.post("/media-pool/ingest", response_model=MediaPoolIngestResponse)
def ingest_media(request: MediaPoolIngestRequest) -> MediaPoolIngestResponse:
    """Adds analyzed photos/videos to the pool AURON curates from. AURON
    does not analyze pixels itself -- theme/tags/aesthetic_score come from
    whatever vision-analysis step runs where the files actually live."""
    return media_pool_service.ingest(request)


@router.get("/media-pool", response_model=MediaPoolList)
def list_media_pool(available_only: bool = False):
    items = media_pool_service.list_available() if available_only else media_pool_service.list_all()
    return MediaPoolList(items=items, count=len(items))


@router.post("/media-pool/analyze-and-ingest", response_model=MediaAnalyzeAndIngestResponse)
def analyze_and_ingest_media(request: MediaAnalyzeAndIngestRequest) -> MediaAnalyzeAndIngestResponse:
    """AURON actually looks at each photo via Claude's vision, deriving the
    theme, tags, and aesthetic score itself instead of requiring them as
    input. AURON still never fetches the file -- the caller supplies image
    bytes or an already-fetchable URL. Every item's real outcome (analyzed
    + ingested, or a specific failure reason) comes back individually; one
    bad item never blocks the rest of the batch."""
    return analyze_and_ingest(request.items, AnthropicVisionAnalyzer(), media_pool_service)


# -- curation: turning the pool into post-worthy groups -----------------------


@router.post("/curate", response_model=CuratedDraftList)
def run_curation(max_groups: int = 10) -> CuratedDraftList:
    """Groups available pool items into hero posts / right-sized carousels
    by theme, reserving each item so a second curation run never proposes
    the same photo twice. Nothing is posted or even a full candidate yet --
    each result still needs a caption via /curate/{draft_id}/finalize."""
    drafts = media_pool_service.run_curation(max_groups=max_groups)
    return CuratedDraftList(items=drafts, count=len(drafts))


@router.get("/curate/drafts", response_model=CuratedDraftList)
def list_drafts(pending_only: bool = True) -> CuratedDraftList:
    drafts = media_pool_service.list_drafts(pending_only=pending_only)
    return CuratedDraftList(items=drafts, count=len(drafts))


@router.get("/curate/drafts/{draft_id}", response_model=CuratedDraft)
def get_draft(draft_id: UUID) -> CuratedDraft:
    try:
        return media_pool_service.get_draft(draft_id)
    except MediaPoolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/curate/drafts/{draft_id}/finalize", response_model=ContentCandidate)
def finalize_draft(draft_id: UUID, request: FinalizeDraftRequest = FinalizeDraftRequest()) -> ContentCandidate:
    """Attaches a caption to a curated draft and runs it through the normal
    moderation/format/edit-plan pipeline. If caption_draft is omitted,
    AURON writes it itself via a real Anthropic API call. Only marks the
    underlying photos permanently 'used' if moderation actually passes."""
    try:
        return instagram_content_service.finalize_draft(draft_id, request)
    except InstagramContentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/curate/drafts/{draft_id}/discard", response_model=CuratedDraft)
def discard_draft(draft_id: UUID) -> CuratedDraft:
    """Releases a draft's reserved photos back into the available pool
    without ever creating a candidate -- e.g. the grouping itself was wrong,
    not just the caption."""
    try:
        return media_pool_service.discard_draft(draft_id)
    except MediaPoolError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
