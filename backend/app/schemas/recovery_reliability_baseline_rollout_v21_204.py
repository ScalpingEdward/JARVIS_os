from typing import Literal
from pydantic import BaseModel, Field

class RolloutStage(BaseModel):
    stage_index: int = Field(ge=1)
    consumer_ids: list[str]
    max_stage_exposure: float = Field(default=0.25, gt=0.0, le=1.0)

class BaselineRolloutRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    rollback_version: int = Field(ge=1)
    rollback_value: float = Field(ge=0.0, le=1.0)
    candidate_consumers: list[str]
    stages: list[RolloutStage]
    risk_brain_hard_block: bool = False

class BaselineRolloutDecision(BaseModel):
    state: Literal['review-required', 'eligible', 'staged', 'blocked']
    stage_count: int
    eligible_consumers: list[str]
    approved_stage_indices: list[int]
    reasons: list[str]
    audit_digest: str
