from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import StrategyCreate, StrategyListResponse, StrategyRecord, StrategyStatus, StrategyStatusResponse
from .service import strategy_builder_service


router = APIRouter(prefix="/v1/strategy-builder", tags=["strategy-builder"])


@router.get("/status", response_model=StrategyStatusResponse)
def builder_status() -> StrategyStatusResponse:
    return strategy_builder_service.status()


@router.post("/strategies", response_model=StrategyRecord, status_code=status.HTTP_201_CREATED)
def create_strategy(payload: StrategyCreate) -> StrategyRecord:
    return strategy_builder_service.create(payload)


@router.get("/strategies", response_model=StrategyListResponse)
def list_strategies(strategy_status: StrategyStatus | None = Query(default=None, alias="status")) -> StrategyListResponse:
    return strategy_builder_service.list_all(status=strategy_status)


@router.get("/strategies/{strategy_id}", response_model=StrategyRecord)
def get_strategy(strategy_id: UUID) -> StrategyRecord:
    record = strategy_builder_service.get(strategy_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return record


@router.post("/strategies/{strategy_id}/validate", response_model=StrategyRecord)
def validate_strategy(strategy_id: UUID) -> StrategyRecord:
    record = strategy_builder_service.validate(strategy_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return record
