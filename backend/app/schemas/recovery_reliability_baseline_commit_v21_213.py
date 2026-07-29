from typing import Literal
from pydantic import BaseModel, Field

class BaselineCommitRequest(BaseModel):
    source_id: str
    source_state: str
    source_human_approved: bool
    workspace_id: str
    preview_id: str
    previous_baseline_id: str
    previous_version: int = Field(ge=1)
    previous_value: float = Field(ge=0.0, le=1.0)
    previous_digest: str
    candidate_baseline_id: str
    candidate_version: int = Field(ge=2)
    candidate_value: float = Field(ge=0.0, le=1.0)
    candidate_preview_digest: str
    rollback_version: int = Field(ge=1)
    rollback_value: float = Field(ge=0.0, le=1.0)
    max_delta: float = Field(default=0.05, ge=0.0, le=0.05)
    risk_brain_hard_block: bool = False

class BaselineCommitDecision(BaseModel):
    state: Literal['review-required','committed','blocked']
    candidate_delta: float
    candidate_digest: str
    reasons: list[str]
    audit_digest: str
