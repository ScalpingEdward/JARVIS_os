"""Setup-submission API — submit strategy setups to the approval gate.

Endpoints
---------
POST /v1/setup-submission/submit           -> SetupSubmissionReport
GET  /v1/setup-submission/pending          -> list[SubmittedSetup]
GET  /v1/setup-submission/pending/{id}     -> SubmittedSetup (404 if unknown)

This router never executes trades. It only records pending approval requests for
a human operator to resolve through the existing approval-gated execution chain.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import SetupSubmissionReport, SetupSubmissionRequest, SubmittedSetup
from .service import setup_submission_service

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
