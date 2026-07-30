from typing import Literal
from pydantic import BaseModel


class DemoRuntimeReadiness(BaseModel):
    version: str
    state: Literal['ready', 'degraded', 'blocked']
    demo_router_registered: bool
    readiness_router_registered: bool
    voice_adapter_bound: bool
    memory_provider_bound: bool
    approval_store_persistent: bool
    operator_ui_bound: bool
    concrete_tool_adapters_bound: bool
    autonomous_high_risk_execution_enabled: bool
    missing_integrations: list[str]
    next_priority: str
