from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import AllocationPlan, AllocationRequest, AllocationStatus, RebalanceReport, RebalanceRequest
from .service import capital_allocation_service

router = APIRouter(prefix="/v1/capital-allocation", tags=["capital-allocation"])


@router.get("/status", response_model=AllocationStatus)
def allocation_status() -> AllocationStatus:
    return capital_allocation_service.status()


@router.post("/plans", response_model=AllocationPlan, status_code=status.HTTP_201_CREATED)
def create_plan(payload: AllocationRequest) -> AllocationPlan:
    try:
        return capital_allocation_service.create_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/plans", response_model=list[AllocationPlan])
def list_plans() -> list[AllocationPlan]:
    return capital_allocation_service.list_plans()


@router.get("/plans/{plan_id}", response_model=AllocationPlan)
def get_plan(plan_id: UUID) -> AllocationPlan:
    plan = capital_allocation_service.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Allocation plan not found")
    return plan


@router.post("/rebalance", response_model=RebalanceReport)
def rebalance(payload: RebalanceRequest) -> RebalanceReport:
    try:
        return capital_allocation_service.rebalance(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
