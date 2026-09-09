"""Account intake API -- propose a new trading account from free text,
then require an explicit, separate confirm before anything real exists.

Never accepts, stores, or forwards a password -- see credential_guard.py.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.accounts.models import TradingAccountRecord

from .models import AccountIntakeRefusal, AccountIntakeRequest, AccountProposal
from .service import AccountIntakeError, account_intake_service

router = APIRouter(prefix="/v1/account-intake", tags=["account-intake"])


@router.get("/status")
def account_intake_status() -> dict:
    return account_intake_service.status()


@router.post("/propose", response_model=AccountProposal | AccountIntakeRefusal)
def propose_account(request: AccountIntakeRequest) -> AccountProposal | AccountIntakeRefusal:
    """Extracts account fields from free text for review -- never
    registers anything. Always returns 200: a refusal (credential
    language detected) is informative content, not an error, same
    reasoning as this session's other propose-only endpoints."""
    return account_intake_service.propose(request.text, request.requester_id)


@router.post("/proposals/{proposal_id}/confirm", response_model=TradingAccountRecord)
def confirm_account(proposal_id: UUID, requester_id: str) -> TradingAccountRecord:
    """The one call that actually registers an account. Requires the
    exact proposal id from /propose -- there is no way to confirm fields
    that were never shown back first."""
    try:
        return account_intake_service.confirm(proposal_id, requester_id)
    except AccountIntakeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/proposals/{proposal_id}", response_model=AccountProposal)
def get_proposal(proposal_id: UUID) -> AccountProposal:
    proposal = account_intake_service.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Unknown proposal")
    return proposal
