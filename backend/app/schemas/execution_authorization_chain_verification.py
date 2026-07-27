from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AuthorizationChainState(str, Enum):
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review-required"
    VERIFIED = "verified"
    APPROVED = "approved"
    ELIGIBLE = "eligible"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AuthorizationChainLink(BaseModel):
    stage: str = Field(min_length=1, max_length=80)
    record_id: str = Field(min_length=1, max_length=160)
    digest: str = Field(min_length=8, max_length=256)
    state: str = Field(min_length=1, max_length=80)
    workspace_id: str = Field(min_length=1, max_length=120)
    operation: Optional[str] = Field(default=None, max_length=160)
    target: Optional[str] = Field(default=None, max_length=512)
    human_approved: bool = False
    risk_brain_blocked: bool = False


class AuthorizationChainCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    links: List[AuthorizationChainLink] = Field(min_length=7)
    expected_operation: str = Field(min_length=1, max_length=160)
    expected_target: str = Field(min_length=1, max_length=512)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_chain_shape(self):
        required = {"decision", "proposal", "binding", "sandbox", "adapter", "gateway", "worker"}
        stages = [link.stage for link in self.links]
        if not required.issubset(set(stages)):
            missing = sorted(required - set(stages))
            raise ValueError(f"missing authorization stages: {','.join(missing)}")
        if len(stages) != len(set(stages)):
            raise ValueError("duplicate authorization stage")
        return self


class AuthorizationChainScores(BaseModel):
    continuity: float = Field(ge=0.0, le=1.0)
    approval_coverage: float = Field(ge=0.0, le=1.0)
    digest_coverage: float = Field(ge=0.0, le=1.0)
    operation_binding: float = Field(ge=0.0, le=1.0)
    target_binding: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)


class AuthorizationChainRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AuthorizationChainState
    expected_operation: str
    expected_target: str
    chain_digest: str
    scores: AuthorizationChainScores
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AuthorizationChainAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
