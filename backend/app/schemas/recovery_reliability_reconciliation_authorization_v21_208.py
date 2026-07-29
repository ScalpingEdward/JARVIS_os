from typing import Literal
from pydantic import BaseModel, Field

class RecoveryStep(BaseModel):
    order: int = Field(ge=1)
    consumer_id: str
    drift_reason: str
    action: Literal['reconcile', 'restart', 'rollback', 'revalidate']
    approved: bool = False

class ReconciliationAuthorizationRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    affected_consumers: list[str]
    healthy_consumers: list[str] = []
    recovery_steps: list[RecoveryStep]
    blast_radius: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    max_blast_radius: float = Field(default=0.50, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class ReconciliationAuthorizationDecision(BaseModel):
    state: Literal['review-required', 'authorized', 'staged', 'recovery-ready', 'blocked']
    ordered_consumers: list[str]
    approved_steps: int
    total_steps: int
    reasons: list[str]
    sequence_digest: str
    audit_digest: str
