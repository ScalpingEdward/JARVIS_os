from typing import Literal
from pydantic import BaseModel, Field

class RolloutStage(BaseModel):
    order: int = Field(ge=1)
    consumers: list[str]
    exposure: float = Field(gt=0.0, le=1.0)
    approved: bool = False

class BaselineRolloutRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    candidate_baseline_id: str
    candidate_version: int = Field(ge=1)
    candidate_digest: str
    rollback_baseline_id: str
    rollback_version: int = Field(ge=1)
    rollback_digest: str
    recovery_sequence_digest: str
    candidate_consumers: list[str]
    stages: list[RolloutStage]
    max_stage_exposure: float = Field(default=0.50, gt=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class BaselineRolloutDecision(BaseModel):
    state: Literal['review-required', 'eligible', 'staged', 'blocked']
    approved_stages: int
    total_stages: int
    ordered_consumers: list[str]
    reasons: list[str]
    rollout_digest: str
    audit_digest: str
