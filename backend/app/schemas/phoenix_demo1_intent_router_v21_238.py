from typing import Literal

from pydantic import BaseModel, Field


class IntentRouteRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(default='demo', min_length=1, max_length=100)
    operator_id: str = Field(default='operator', min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=4000)
    risk_brain_hard_block: bool = False


class PlannedCapability(BaseModel):
    step_id: str
    intent: str
    adapter_id: str
    capability: str
    risk: Literal['read','write','financial','privileged'] = 'read'
    approval_required: bool = False
    arguments: dict = Field(default_factory=dict)
    reason: str


class IntentRouteResult(BaseModel):
    version: str = 'v21.238'
    state: Literal['planned','blocked','unsupported']
    session_id: str
    workspace_id: str
    operator_id: str
    command: str
    detected_intents: list[str]
    plan: list[PlannedCapability]
    approval_required: bool = False
    autonomous_high_risk_execution_enabled: bool = False
    reasons: list[str] = Field(default_factory=list)
