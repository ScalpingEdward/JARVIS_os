from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class RecoveryReceipt(BaseModel):
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    recovery_sequence_digest: str
    step_order: int = Field(ge=1)
    nonce: str
    observed_at: datetime
    recovered: bool
    healthy: bool
    recovery_quality: float = Field(ge=0.0, le=1.0)

class RecoveryReceiptReconciliationRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    recovery_sequence_digest: str
    expected_consumers: list[str]
    expected_order: list[str]
    receipts: list[RecoveryReceipt]
    now: datetime
    receipt_ttl_seconds: int = Field(default=900, ge=1)
    min_recovery_quality: float = Field(default=0.80, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class RecoveryReceiptReconciliationDecision(BaseModel):
    state: Literal['review-required', 'incomplete', 'completed', 'blocked']
    completion_score: float
    completed_consumers: list[str]
    incomplete_consumers: list[str]
    reasons: list[str]
    audit_digest: str
