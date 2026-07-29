from typing import Literal
from pydantic import BaseModel, Field

class FeedbackImpactPreviewRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    current_value: float = Field(ge=0.0, le=1.0)
    feedback_adjustment: float = Field(ge=-0.05, le=0.05)
    score_impact: float = Field(ge=-1.0, le=1.0)
    rank_impact: float = Field(ge=-1.0, le=1.0)
    failover_impact: float = Field(ge=-1.0, le=1.0)
    recovery_readiness_impact: float = Field(ge=-1.0, le=1.0)
    blast_radius: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    max_blast_radius: float = Field(default=0.35, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.25, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class FeedbackImpactPreviewDecision(BaseModel):
    state: Literal['review-required', 'approved-preview', 'blocked']
    candidate_value: float
    aggregate_impact: float
    reasons: list[str]
    preview_digest: str
    audit_digest: str
