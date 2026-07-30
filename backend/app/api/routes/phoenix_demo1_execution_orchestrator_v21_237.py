from fastapi import APIRouter

from app.schemas.phoenix_demo1_execution_orchestrator_v21_237 import ExecutionOrchestratorRequest, ExecutionOrchestratorResult
from app.services.phoenix_demo1_execution_orchestrator_v21_237 import execute_demo_command

router = APIRouter(prefix='/phoenix/demo1/v21.237', tags=['phoenix-demo1-execution'])


@router.post('/execute', response_model=ExecutionOrchestratorResult)
def execute(payload: ExecutionOrchestratorRequest) -> ExecutionOrchestratorResult:
    return execute_demo_command(payload)
