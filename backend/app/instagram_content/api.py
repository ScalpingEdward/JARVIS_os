from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import ContentCandidate, ContentCandidateCreate, ContentCandidateList, ContentDecision, ContentStatus
from .service import InstagramContentError, instagram_content_service

router = APIRouter(prefix="/v1/instagram", tags=["instagram-content"])


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
