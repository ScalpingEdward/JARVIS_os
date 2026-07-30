from fastapi import APIRouter
from app.schemas.phoenix_demo1_tool_adapters_v21_231 import AdapterStatus, GovernedToolInvocation, GovernedToolResult
from app.services.phoenix_demo1_tool_adapters_v21_231 import adapter_status, invoke_tool

router = APIRouter(prefix='/phoenix/demo1/v21.231/tools', tags=['phoenix-demo1-v21.231'])

@router.get('/status', response_model=AdapterStatus)
def tool_adapter_status() -> AdapterStatus:
    return adapter_status()

@router.post('/invoke', response_model=GovernedToolResult)
def governed_tool_invoke(payload: GovernedToolInvocation) -> GovernedToolResult:
    return invoke_tool(payload)
