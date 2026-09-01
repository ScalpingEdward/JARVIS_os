from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .models import ContentCandidate, ContentCandidateCreate, ContentCandidateList, ContentDecision, ContentStatus
from .posting_schedule import NOTE, PostingWindow, suggested_windows_for_weekday
from .service import InstagramContentError, instagram_content_service

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
