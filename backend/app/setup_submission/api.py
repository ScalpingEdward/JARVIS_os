"""Setup-submission API — submit strategy setups to the approval gate.

Endpoints
---------
POST /v1/setup-submission/submit                    -> SetupSubmissionReport
GET  /v1/setup-submission/pending                    -> list[SubmittedSetup]
GET  /v1/setup-submission/pending/{id}               -> SubmittedSetup (404 if unknown)
POST /v1/setup-submission/pending/{id}/decision      -> SubmittedSetup

This router never executes trades. Deciding a setup here only records that a
human approved or rejected it -- trade_risk_pipeline.assess() (the next real
link in the chain) refuses anything not explicitly approved, but nothing in
this router itself ever reaches a broker.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    SetupDecisionRequest,
    SetupSubmissionReport,
    SetupSubmissionRequest,
    SubmittedSetup,
)
from .service import SetupSubmissionError, setup_submission_service

router = APIRouter(prefix="/v1/setup-submission", tags=["setup-submission"])


@router.post("/submit", response_model=SetupSubmissionReport)
def submit_setups(request: SetupSubmissionRequest) -> SetupSubmissionReport:
    """Evaluate accounts against the snapshot and submit executable setups."""
    return setup_submission_service.submit(request)


@router.get("/pending", response_model=list[SubmittedSetup])
def list_pending() -> list[SubmittedSetup]:
    """Return all pending approval requests."""
    return setup_submission_service.get_pending_approvals()


@router.get("/pending/{approval_request_id}", response_model=SubmittedSetup)
def get_pending(approval_request_id: UUID) -> SubmittedSetup:
    """Return one pending approval request by its ID, or 404 if unknown."""
    setup = setup_submission_service.get_approval(approval_request_id)
    if setup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no pending approval request with id {approval_request_id}",
        )
    return setup


@router.post("/pending/{approval_request_id}/decision", response_model=SubmittedSetup)
def decide_pending(approval_request_id: UUID, request: SetupDecisionRequest) -> SubmittedSetup:
    """Record a human's approve/reject decision for a submitted setup.

    One-shot: deciding an already-decided setup returns 409, not a silent
    overwrite. This is the actual approval gate -- nothing downstream treats
    a setup as usable until it has been explicitly approved here.
    """
    try:
        return setup_submission_service.decide(approval_request_id, request)
    except SetupSubmissionError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "unknown" in detail else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=detail) from exc
