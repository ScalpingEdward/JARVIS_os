from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class ConsumerAdoptionObservation(BaseModel):
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    receipt_nonce: str
    observed_at: datetime
    adopted: bool
    healthy: bool
    confidence: float = Field(ge=0.0, le=1.0)

class AdoptionConsistencyRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    expected_consumers: list[str]
    observations: list[ConsumerAdoptionObservation]
    now: datetime
    observation_ttl_seconds: int = Field(default=900, ge=1)
    min_confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class AdoptionConsistencyDecision(BaseModel):
    state: Literal['review-required', 'consistent', 'drift-detected', 'blocked']
    consistency_score: float
    consistent_consumers: list[str]
    drifted_consumers: list[str]
    drift_reasons: list[str]
    audit_digest: str
