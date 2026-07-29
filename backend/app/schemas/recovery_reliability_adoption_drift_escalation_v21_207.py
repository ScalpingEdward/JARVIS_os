from typing import Literal
from pydantic import BaseModel, Field

Severity = Literal['low','medium','high','critical']

class DriftConsumer(BaseModel):
    consumer_id: str
    drift_reason: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)

class DriftEscalationRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    affected_consumers: list[DriftConsumer]
    healthy_consumers: list[str] = []
    max_blast_radius: float = Field(default=0.50, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class DriftEscalationDecision(BaseModel):
    state: Literal['review-required','reconciliation-ready','blocked']
    readiness_score: float
    blast_radius: float
    residual_risk: float
    affected_consumers: list[str]
    healthy_consumers: list[str]
    reasons: list[str]
    audit_digest: str
