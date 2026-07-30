from typing import Literal
from pydantic import BaseModel, Field

class AdapterCapability(BaseModel):
    adapter_id: str
    capability: str
    risk: Literal['read','write','financial','privileged'] = 'read'
    healthy: bool = True
    available: bool = True
    approval_required: bool = False

class AdapterStatus(BaseModel):
    version: str = 'v21.231'
    registry_bound: bool = True
    concrete_adapters_bound: bool = True
    capabilities: list[AdapterCapability]
    healthy_count: int
    unavailable_count: int
    autonomous_high_risk_execution_enabled: bool = False

class GovernedToolInvocation(BaseModel):
    adapter_id: str
    capability: str
    arguments: dict = Field(default_factory=dict)
    approved: bool = False
    risk_brain_hard_block: bool = False

class GovernedToolResult(BaseModel):
    state: Literal['completed','approval-required','blocked','unavailable','unsupported']
    adapter_id: str
    capability: str
    output: dict | None = None
    reasons: list[str] = Field(default_factory=list)
