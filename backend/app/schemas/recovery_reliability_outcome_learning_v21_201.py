from typing import Literal
from pydantic import BaseModel, Field

class RecoveryOutcomeLearningRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    stability_score: float = Field(ge=0.0, le=1.0)
    aggregate_confidence: float = Field(ge=0.0, le=1.0)
    recovery_quality: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    proposed_feedback_adjustment: float = Field(ge=-0.05, le=0.05)
    risk_brain_hard_block: bool = False

class RecoveryOutcomeLearningDecision(BaseModel):
    state: Literal['review-required', 'approved-feedback', 'blocked']
    learning_score: float
    bounded_feedback_adjustment: float
    reasons: list[str]
    audit_digest: str
