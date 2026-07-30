from typing import Literal
from pydantic import BaseModel, Field


class DashboardPanel(BaseModel):
    panel_id: str
    title: str
    state: Literal['ready', 'degraded', 'blocked', 'empty']
    summary: str
    endpoint: str
    attention_required: bool = False


class OperatorDashboardSnapshot(BaseModel):
    version: str = 'v21.230'
    state: Literal['ready', 'degraded', 'blocked']
    workspace_id: str
    operator_id: str
    panels: list[DashboardPanel]
    pending_approvals: int = Field(ge=0)
    deferred_approvals: int = Field(ge=0)
    memory_provider_bound: bool
    voice_adapter_bound: bool
    approval_store_persistent: bool
    operator_ui_bound: bool
    concrete_tool_adapters_bound: bool
    autonomous_high_risk_execution_enabled: bool = False
    attention_panels: list[str]
    navigation: dict[str, str]


class OperatorDashboardRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    risk_brain_hard_block: bool = False
