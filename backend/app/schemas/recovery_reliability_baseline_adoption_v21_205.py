from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class BaselineAdoptionReceipt(BaseModel):
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    rollback_version: int = Field(ge=1)
    rollback_value: float = Field(ge=0.0, le=1.0)
    nonce: str
    observed_at: datetime
    adopted: bool
    healthy: bool
    confidence: float = Field(ge=0.0, le=1.0)

class BaselineAdoptionRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    consumer_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    rollback_version: int = Field(ge=1)
    rollback_value: float = Field(ge=0.0, le=1.0)
    now: datetime
    receipt_ttl_seconds: int = Field(default=900, ge=1)
    min_confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class BaselineAdoptionDecision(BaseModel):
    state: Literal['review-required', 'authorized', 'receipt-required', 'adopted', 'blocked']
    consumer_id: str
    reasons: list[str]
    audit_digest: str
