from fastapi import APIRouter

from app.schemas.phoenix_demo1_intent_router_v21_238 import DynamicIntentExecutionResult, IntentRouteRequest, IntentRouteResult
from app.services.phoenix_demo1_intent_router_v21_238 import execute_operator_command, plan_operator_command

router = APIRouter(prefix='/phoenix/demo1/v21.238', tags=['phoenix-demo1-intent-router'])


@router.post('/plan', response_model=IntentRouteResult)
def plan(payload: IntentRouteRequest) -> IntentRouteResult:
    return plan_operator_command(payload)


@router.post('/route-and-execute', response_model=DynamicIntentExecutionResult)
def route_and_execute(payload: IntentRouteRequest) -> DynamicIntentExecutionResult:
    return execute_operator_command(payload)
