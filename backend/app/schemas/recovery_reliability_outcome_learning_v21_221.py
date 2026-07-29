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
    recovery_sequence_digest: str
    stability_score: float = Field(ge=0.0, le=1.0)
    mean_confidence: float = Field(ge=0.0, le=1.0)
    mean_recovery_quality: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    requested_feedback_adjustment: float = Field(ge=-0.05, le=0.05)
    min_learning_score: float = Field(default=0.80, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class RecoveryOutcomeLearningDecision(BaseModel):
    state: Literal['review-required', 'approved-feedback', 'blocked']
    learning_score: float
    approved_feedback_adjustment: float
    reasons: list[str]
    feedback_digest: str
    audit_digest: str
