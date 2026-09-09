"""Setup-submission API — submit strategy setups to the approval gate.

Endpoints
---------
POST /v1/setup-submission/submit                    -> SetupSubmissionReport
GET  /v1/setup-submission/pending                    -> list[SubmittedSetup] (undecided only)
GET  /v1/setup-submission/all                        -> list[SubmittedSetup] (full history)
GET  /v1/setup-submission/status                     -> SetupSubmissionStatus
GET  /v1/setup-submission/pending/{id}               -> SubmittedSetup (404 if unknown)
POST /v1/setup-submission/pending/{id}/decision      -> SubmittedSetup

This router never executes trades. Deciding a setup here only records that a
human approved or rejected it -- trade_risk_pipeline.assess() (the next real
link in the chain) refuses anything not explicitly approved, but nothing in
this router itself ever reaches a broker.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.security.operator_auth import require_operator_token

from .models import (
    SetupDecisionRequest,
    SetupSubmissionReport,
    SetupSubmissionRequest,
    SetupSubmissionStatus,
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
    """Return only the setups still awaiting a decision.

    Used to return every setup ever submitted regardless of decision --
    fixed; see SetupSubmissionService.get_pending_approvals()'s own note.
    """
    return setup_submission_service.get_pending_approvals()


@router.get("/all", response_model=list[SubmittedSetup])
def list_all() -> list[SubmittedSetup]:
    """Every setup ever submitted, decided or not -- the full history
    /pending used to silently return under a misleading name."""
    return setup_submission_service.get_all()


@router.get("/status", response_model=SetupSubmissionStatus)
def setup_submission_status() -> SetupSubmissionStatus:
    """Capability health for the approval gate itself: how many setups
    are pending/approved/rejected right now, and how long the oldest
    undecided one has been waiting."""
    return setup_submission_service.status()


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


@router.post("/pending/{approval_request_id}/decision", response_model=SubmittedSetup, dependencies=[Depends(require_operator_token)])
def decide_pending(approval_request_id: UUID, request: SetupDecisionRequest) -> SubmittedSetup:
    """Record a human's approve/reject decision for a submitted setup.

    One-shot: deciding an already-decided setup returns 409, not a silent
    overwrite. This is the actual approval gate -- nothing downstream treats
    a setup as usable until it has been explicitly approved here.

    Requires a real X-Auron-Operator-Token header -- a direct API call
    used to be able to assert decided_by="brano" with nothing verifying
    that claim; found by an external test pass, fixed here. The
    Telegram approval path's own HMAC-signed callback token is
    unaffected and unchanged -- this closes the *other* path into the
    same action.
    """
    try:
        return setup_submission_service.decide(approval_request_id, request)
    except SetupSubmissionError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "unknown" in detail else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=detail) from exc
