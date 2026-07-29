from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

DemoMode = Literal['interactive', 'focus', 'sleep']
Priority = Literal['low', 'normal', 'high', 'critical']
ActionRisk = Literal['read-only', 'low', 'medium', 'high']

class DemoToolState(BaseModel):
    tool_id: str
    available: bool
    healthy: bool
    requires_approval: bool = False

class DemoRequest(BaseModel):
    session_id: str
    workspace_id: str
    operator_id: str
    command: str
    mode: DemoMode = 'interactive'
    priority: Priority = 'normal'
    action_risk: ActionRisk = 'read-only'
    now: datetime
    suppress_interaction_until: datetime | None = None
    tools: list[DemoToolState] = []
    memory_context_available: bool = True
    voice_available: bool = True
    text_available: bool = True
    risk_brain_hard_block: bool = False

class DemoApprovalRequest(BaseModel):
    approval_id: str
    reason: str
    priority: Priority
    action_risk: ActionRisk

class DemoResponse(BaseModel):
    state: Literal['ready', 'working', 'queued-for-approval', 'deferred', 'blocked']
    interaction_channel: Literal['voice', 'text', 'silent']
    summary: str
    approval_requests: list[DemoApprovalRequest]
    executable_without_approval: list[str]
    deferred_items: list[str]
    operator_message: str
    audit_digest: str

class DemoStatus(BaseModel):
    version: str = 'v21.225'
    demo_name: str = 'PHOENIX Demo 1'
    vertical_slice_ready: bool
    operator_experience_ready: bool
    approval_governance_ready: bool
    memory_path_ready: bool
    voice_or_text_path_ready: bool
    autonomous_high_risk_execution_enabled: bool = False
    notes: list[str] = []
