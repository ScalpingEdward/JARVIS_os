from typing import Literal
from pydantic import BaseModel, Field

class BaselineCommitRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    previous_baseline_id: str
    previous_baseline_version: int = Field(ge=1)
    previous_baseline_digest: str
    candidate_baseline_id: str
    candidate_baseline_version: int = Field(ge=2)
    preview_digest: str
    previous_value: float = Field(ge=0.0, le=1.0)
    candidate_value: float = Field(ge=0.0, le=1.0)
    rollback_baseline_id: str
    rollback_baseline_version: int = Field(ge=1)
    rollback_baseline_digest: str
    recovery_sequence_digest: str
    max_candidate_delta: float = Field(default=0.05, ge=0.0, le=1.0)
    risk_brain_hard_block: bool = False

class BaselineCommitDecision(BaseModel):
    state: Literal['review-required', 'committed', 'blocked']
    candidate_baseline_id: str
    candidate_baseline_version: int
    candidate_value: float
    candidate_delta: float
    candidate_digest: str
    reasons: list[str]
    audit_digest: str
