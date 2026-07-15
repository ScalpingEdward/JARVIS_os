from fastapi import APIRouter, HTTPException

from .models import AdapterExecutionResult, AgentAdapterDescriptor, ContributionDispatch, ReviewDispatch
from .service import AgentAdapterError, agent_adapter_service

router = APIRouter(prefix="/v1/agent-adapters", tags=["agent-adapters"])


@router.get("", response_model=list[AgentAdapterDescriptor])
def list_agent_adapters() -> list[AgentAdapterDescriptor]:
    return agent_adapter_service.list_adapters()


@router.post("/contributions", response_model=AdapterExecutionResult)
def dispatch_contribution(payload: ContributionDispatch) -> AdapterExecutionResult:
    try:
        return agent_adapter_service.dispatch_contribution(payload)
    except AgentAdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reviews", response_model=AdapterExecutionResult)
def dispatch_review(payload: ReviewDispatch) -> AdapterExecutionResult:
    try:
        return agent_adapter_service.dispatch_review(payload)
    except AgentAdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
