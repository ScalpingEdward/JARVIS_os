from typing import Literal
from pydantic import BaseModel, Field

class OutcomeLearningRequest(BaseModel):
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
    current_baseline_value: float = Field(ge=0.0, le=1.0)
    max_feedback_adjustment: float = Field(default=0.05, ge=0.0, le=0.05)
    min_learning_score: float = Field(default=0.75, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.20, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class OutcomeLearningDecision(BaseModel):
    state: Literal['review-required', 'approved-feedback', 'blocked']
    learning_score: float
    feedback_adjustment: float
    candidate_feedback_value: float
    reasons: list[str]
    feedback_digest: str
    audit_digest: str
