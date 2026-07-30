from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

InboxState = Literal['pending', 'deferred', 'resolved', 'blocked']

class ApprovalInboxCreate(BaseModel):
    approval_id: str = Field(min_length=8, max_length=120)
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    operator_id: str = Field(min_length=1, max_length=120)
    command: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=1000)
    priority: Literal['low', 'normal', 'high', 'critical']
    action_risk: Literal['read-only', 'low', 'medium', 'high']
    state: InboxState = 'pending'
    created_at: datetime
    deferred_until: datetime | None = None
    risk_brain_hard_block: bool = False

class ApprovalInboxRecord(ApprovalInboxCreate):
    updated_at: datetime
    recovery_count: int = 0

class ApprovalInboxList(BaseModel):
    items: list[ApprovalInboxRecord]
    count: int
    persistent: bool = True

class DeferredRecoveryRequest(BaseModel):
    now: datetime
    interaction_available: bool = True
    risk_brain_hard_block: bool = False

class DeferredRecoveryResult(BaseModel):
    recovered: list[ApprovalInboxRecord]
    still_deferred: list[ApprovalInboxRecord]
    blocked: list[ApprovalInboxRecord]
    autonomous_execution_performed: bool = False

class InboxStatus(BaseModel):
    version: str = 'v21.228'
    persistent: bool
    storage_path: str
    pending: int
    deferred: int
    resolved: int
    blocked: int
    autonomous_high_risk_execution_enabled: bool = False
