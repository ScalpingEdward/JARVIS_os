from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import SetupEvaluationRequest, TradingAgentStatus, TradingSetup
from .service import TradingAgentError, trading_agent_service

router = APIRouter(prefix="/v1/trading", tags=["trading"])


@router.get("/status", response_model=TradingAgentStatus)
def status() -> TradingAgentStatus:
    return trading_agent_service.status()


@router.post("/evaluate", response_model=TradingSetup)
def evaluate(payload: SetupEvaluationRequest) -> TradingSetup:
    return trading_agent_service.evaluate(payload)


@router.get("/setups", response_model=list[TradingSetup])
def list_setups() -> list[TradingSetup]:
    return trading_agent_service.list_all()


@router.get("/setups/{setup_id}", response_model=TradingSetup)
def get_setup(setup_id: UUID) -> TradingSetup:
    try:
        return trading_agent_service.get(setup_id)
    except TradingAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
