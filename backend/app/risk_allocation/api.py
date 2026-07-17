from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import AllocationCreate, AllocationPlan, RiskAllocationStatus
from .service import risk_allocation_service


router = APIRouter(prefix="/v1/risk-allocation", tags=["risk-allocation"])


@router.get("/status", response_model=RiskAllocationStatus)
def allocation_status() -> RiskAllocationStatus:
    return risk_allocation_service.status()


@router.post("/plans", response_model=AllocationPlan, status_code=status.HTTP_201_CREATED)
def create_plan(payload: AllocationCreate) -> AllocationPlan:
    return risk_allocation_service.create(payload)


@router.get("/plans", response_model=list[AllocationPlan])
def list_plans() -> list[AllocationPlan]:
    return risk_allocation_service.list_all()


@router.get("/plans/{plan_id}", response_model=AllocationPlan)
def get_plan(plan_id: UUID) -> AllocationPlan:
    plan = risk_allocation_service.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Risk allocation plan not found")
    return plan
