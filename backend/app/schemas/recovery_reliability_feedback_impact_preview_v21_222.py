from typing import Literal
from pydantic import BaseModel, Field

class FeedbackImpactSimulationRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    recovery_sequence_digest: str
    current_value: float = Field(ge=0.0, le=1.0)
    feedback_adjustment: float = Field(ge=-0.05, le=0.05)
    current_score: float = Field(ge=0.0, le=1.0)
    current_rank: int = Field(ge=1)
    current_failover_readiness: float = Field(ge=0.0, le=1.0)
    current_recovery_readiness: float = Field(ge=0.0, le=1.0)
    projected_score_delta: float = Field(ge=-1.0, le=1.0)
    projected_rank_delta: int
    projected_failover_delta: float = Field(ge=-1.0, le=1.0)
    projected_recovery_delta: float = Field(ge=-1.0, le=1.0)
    blast_radius: float = Field(ge=0.0, le=1.0)
    max_blast_radius: float = Field(default=0.35, ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.20, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class FeedbackImpactSimulationDecision(BaseModel):
    state: Literal['review-required', 'approved-preview', 'blocked']
    candidate_value: float
    projected_score: float
    projected_rank: int
    projected_failover_readiness: float
    projected_recovery_readiness: float
    reasons: list[str]
    preview_digest: str
    audit_digest: str
