from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import AuditEntry, RuntimeMission, RuntimeMissionCreate, RuntimeReport, RuntimeUpdate
from .service import company_runtime_service

router = APIRouter(prefix="/v1/company-runtime", tags=["company-runtime"])


@router.get("/status", response_model=RuntimeReport)
def runtime_status() -> RuntimeReport:
    return company_runtime_service.report()


@router.post("/missions", response_model=RuntimeMission, status_code=status.HTTP_201_CREATED)
def create_runtime_mission(payload: RuntimeMissionCreate) -> RuntimeMission:
    return company_runtime_service.create(payload)


@router.get("/missions", response_model=list[RuntimeMission])
def list_runtime_missions() -> list[RuntimeMission]:
    return company_runtime_service.list_all()


@router.post("/missions/claim-next", response_model=RuntimeMission)
def claim_next_runtime_mission() -> RuntimeMission:
    mission = company_runtime_service.claim_next()
    if mission is None:
        raise HTTPException(status_code=409, detail="No queued mission available")
    return mission


@router.patch("/missions/{mission_id}", response_model=RuntimeMission)
def update_runtime_mission(mission_id: UUID, payload: RuntimeUpdate) -> RuntimeMission:
    mission = company_runtime_service.update(mission_id, payload)
    if mission is None:
        raise HTTPException(status_code=404, detail="Runtime mission not found")
    return mission


@router.post("/missions/{mission_id}/approve", response_model=RuntimeMission)
def approve_runtime_mission(mission_id: UUID) -> RuntimeMission:
    mission = company_runtime_service.approve(mission_id)
    if mission is None:
        raise HTTPException(status_code=409, detail="Mission is not waiting for human approval")
    return mission


@router.get("/audit", response_model=list[AuditEntry])
def runtime_audit(mission_id: UUID | None = None) -> list[AuditEntry]:
    return company_runtime_service.audit(mission_id)
