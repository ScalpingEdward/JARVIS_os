from fastapi import APIRouter, Header, HTTPException

from app.schemas.institutional_compliance import (
    InstitutionalComplianceAction,
    InstitutionalComplianceCreate,
    InstitutionalComplianceRecord,
)
from app.services.institutional_compliance import institutional_compliance_service

router = APIRouter(prefix="/v1/institutional-compliance", tags=["institutional-compliance"])


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header required")
    return x_workspace_id


@router.get("/status")
def status() -> dict:
    return {
        "module": "PHOENIX v21.79 Institutional Compliance Governance",
        "mode": "advisory-only",
        "human_approval_required": True,
        "risk_brain_authoritative": True,
        "policy_mutation_enabled": False,
        "restriction_mutation_enabled": False,
        "portfolio_mutation_enabled": False,
        "execution_enabled": False,
    }


@router.post("/records", response_model=InstitutionalComplianceRecord)
def create_record(payload: InstitutionalComplianceCreate) -> InstitutionalComplianceRecord:
    try:
        return institutional_compliance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[InstitutionalComplianceRecord])
def list_records(x_workspace_id: str | None = Header(default=None)) -> list[InstitutionalComplianceRecord]:
    return institutional_compliance_service.list(_workspace(x_workspace_id))


@router.get("/records/{record_id}", response_model=InstitutionalComplianceRecord)
def get_record(record_id: str, x_workspace_id: str | None = Header(default=None)) -> InstitutionalComplianceRecord:
    try:
        return institutional_compliance_service.get(_workspace(x_workspace_id), record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=InstitutionalComplianceRecord)
def act_on_record(
    record_id: str,
    payload: InstitutionalComplianceAction,
    x_workspace_id: str | None = Header(default=None),
) -> InstitutionalComplianceRecord:
    try:
        return institutional_compliance_service.act(_workspace(x_workspace_id), record_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(x_workspace_id: str | None = Header(default=None)) -> list[dict]:
    return institutional_compliance_service.audit(_workspace(x_workspace_id))
