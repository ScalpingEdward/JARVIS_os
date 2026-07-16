from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import CompanyAgentList, CompanyStatus, MissionCreate, MissionDetail, WorkItem, WorkStatusUpdate
from .service import company_service

router = APIRouter(prefix="/v1/company", tags=["company"])


@router.get("/status", response_model=CompanyStatus)
def company_status() -> CompanyStatus:
    return company_service.status()


@router.get("/agents", response_model=CompanyAgentList)
def list_company_agents() -> CompanyAgentList:
    items = company_service.list_agents()
    return CompanyAgentList(items=items, count=len(items))


@router.post("/missions", response_model=MissionDetail, status_code=status.HTTP_201_CREATED)
def create_mission(payload: MissionCreate) -> MissionDetail:
    return company_service.create_mission(payload)


@router.get("/missions", response_model=list[MissionDetail])
def list_missions() -> list[MissionDetail]:
    return company_service.list_missions()


@router.get("/missions/{mission_id}", response_model=MissionDetail)
def get_mission(mission_id: UUID) -> MissionDetail:
    try:
        return company_service.get_mission(mission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mission not found") from exc


@router.patch("/work-items/{work_item_id}", response_model=WorkItem)
def update_work_item(work_item_id: UUID, payload: WorkStatusUpdate) -> WorkItem:
    try:
        return company_service.update_work_item(work_item_id, payload.status, payload.result_summary)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Work item not found") from exc
