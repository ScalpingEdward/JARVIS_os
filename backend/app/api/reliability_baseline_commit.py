"""API for PHOENIX v21.144 reliability baseline commit governance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.reliability_baseline_commit import ReliabilityBaselineCommitService

router = APIRouter(prefix="/v1/reliability-baselines", tags=["reliability-baselines"])
service = ReliabilityBaselineCommitService()


class ProposalIn(BaseModel):
    baseline_id: str
    workspace_id: str
    subject_id: str
    closure: dict
    operation_id: str


class ApprovalIn(BaseModel):
    workspace_id: str
    subject_id: str
    version: int
    actor: str
    operation_id: str


class RollbackIn(ApprovalIn):
    target_version: int


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.144",
        "status": "active",
        "autonomous_routing_mutation": False,
        "autonomous_policy_mutation": False,
        "human_approval_required": True,
    }


@router.post("/proposals")
def propose(payload: ProposalIn) -> dict:
    try:
        return service.propose(**payload.model_dump()).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/actions/approve")
def approve(payload: ApprovalIn) -> dict:
    try:
        return service.approve(payload.workspace_id, payload.subject_id, payload.version, actor=payload.actor, operation_id=payload.operation_id).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/actions/propose-rollback")
def propose_rollback(payload: RollbackIn) -> dict:
    try:
        return service.propose_rollback(payload.workspace_id, payload.subject_id, target_version=payload.target_version, actor=payload.actor, operation_id=payload.operation_id).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/actions/approve-rollback")
def approve_rollback(payload: ApprovalIn) -> dict:
    try:
        return service.approve_rollback(payload.workspace_id, payload.subject_id, payload.version, actor=payload.actor, operation_id=payload.operation_id).__dict__
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records")
def records(workspace_id: str, subject_id: str | None = None) -> list[dict]:
    return [r.__dict__ for r in service.list_records(workspace_id, subject_id)]


@router.get("/audit")
def audit() -> list[dict]:
    return service.audit()
