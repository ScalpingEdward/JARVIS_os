from fastapi import APIRouter, Header, HTTPException, Query

from .models import AuditEvent, RollbackActionRequest, RollbackAssessment, RollbackAssessmentCreate
from .service import RollbackIntelligenceError, RollbackIntelligenceService

router = APIRouter(prefix="/v1/rollback-intelligence-provenance", tags=["PHOENIX v21.31"])
service = RollbackIntelligenceService()


def _workspace(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-ID header is required")
    return x_workspace_id


def _handle(error: RollbackIntelligenceError) -> HTTPException:
    text = str(error)
    status = 404 if text == "record not found" else 409
    return HTTPException(status_code=status, detail=text)


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "rollback-intelligence-provenance", "version": "21.31", "status": "ready"}


@router.post("/assessments", response_model=RollbackAssessment, status_code=201)
def create_assessment(payload: RollbackAssessmentCreate, x_actor: str = Header(default="system")) -> RollbackAssessment:
    try:
        return service.create(payload, actor=x_actor)
    except RollbackIntelligenceError as error:
        raise _handle(error) from error


@router.get("/assessments", response_model=list[RollbackAssessment])
def list_assessments(x_workspace_id: str | None = Header(default=None)) -> list[RollbackAssessment]:
    return service.list(_workspace(x_workspace_id))


@router.get("/assessments/{record_id}", response_model=RollbackAssessment)
def get_assessment(record_id: str, x_workspace_id: str | None = Header(default=None)) -> RollbackAssessment:
    try:
        return service.get(_workspace(x_workspace_id), record_id)
    except RollbackIntelligenceError as error:
        raise _handle(error) from error


@router.post("/assessments/{record_id}/actions", response_model=RollbackAssessment)
def apply_action(record_id: str, request: RollbackActionRequest,
                 x_workspace_id: str | None = Header(default=None)) -> RollbackAssessment:
    try:
        return service.act(_workspace(x_workspace_id), record_id, request)
    except RollbackIntelligenceError as error:
        raise _handle(error) from error


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str | None = Header(default=None), limit: int = Query(default=200, ge=1, le=1000)) -> list[AuditEvent]:
    return service.audit(_workspace(x_workspace_id))[-limit:]
