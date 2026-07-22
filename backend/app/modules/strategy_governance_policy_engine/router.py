from fastapi import APIRouter, HTTPException, Query

from .models import AuditEvent, GovernanceAction, StrategyPolicyCreate, StrategyPolicyRecord
from .service import GovernanceError, StrategyGovernanceService

router = APIRouter(
    prefix="/v1/strategy-governance",
    tags=["PHOENIX v21.21 Strategy Governance & Policy Engine"],
)
service = StrategyGovernanceService()


@router.get("/status")
def status() -> dict:
    return {
        "module": "PHOENIX v21.21 Strategy Governance & Policy Engine",
        "status": "operational",
        "live_strategy_mutation": False,
        "human_approval_required": True,
    }


@router.post("/policies", response_model=StrategyPolicyRecord)
def create_policy(payload: StrategyPolicyCreate) -> StrategyPolicyRecord:
    try:
        return service.create(payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/policies", response_model=list[StrategyPolicyRecord])
def list_policies(workspace_id: str = Query(..., min_length=1)) -> list[StrategyPolicyRecord]:
    return service.list(workspace_id)


@router.get("/policies/{record_id}", response_model=StrategyPolicyRecord)
def get_policy(record_id: str, workspace_id: str = Query(..., min_length=1)) -> StrategyPolicyRecord:
    try:
        return service.get(workspace_id, record_id)
    except GovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/policies/{record_id}/actions", response_model=StrategyPolicyRecord)
def apply_action(
    record_id: str,
    payload: GovernanceAction,
    workspace_id: str = Query(..., min_length=1),
) -> StrategyPolicyRecord:
    try:
        return service.act(workspace_id, record_id, payload)
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/active", response_model=StrategyPolicyRecord)
def active_policy(
    workspace_id: str = Query(..., min_length=1),
    strategy_id: str = Query(..., min_length=1),
) -> StrategyPolicyRecord:
    try:
        return service.active_policy(workspace_id, strategy_id)
    except GovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(..., min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
