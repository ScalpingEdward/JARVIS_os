from typing import Literal
from pydantic import BaseModel, Field

class RolloutStage(BaseModel):
    order: int = Field(ge=1)
    consumer_ids: list[str]
    max_exposure: float = Field(ge=0.0, le=1.0)
    approved: bool = False

class BaselineRolloutRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    baseline_id: str
    baseline_version: int = Field(ge=1)
    baseline_digest: str
    rollback_baseline_id: str
    rollback_version: int = Field(ge=1)
    candidate_consumers: list[str]
    stages: list[RolloutStage]
    risk_brain_hard_block: bool = False

class BaselineRolloutDecision(BaseModel):
    state: Literal['review-required', 'eligible', 'staged', 'blocked']
    eligible_consumers: list[str]
    approved_stages: int
    total_stages: int
    reasons: list[str]
    rollout_digest: str
    audit_digest: str
