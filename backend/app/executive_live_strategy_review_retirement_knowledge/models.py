from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReviewState(str, Enum):
    blocked = "blocked"
    retain = "retain"
    remediate = "remediate"
    archive = "archive"
    retire = "retire"


class StrategyReviewInput(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=100)
    lifecycle_state: str = Field(min_length=1, max_length=40)
    consecutive_failed_reviews: int = Field(default=0, ge=0)
    active_incidents: int = Field(default=0, ge=0)
    unresolved_findings: int = Field(default=0, ge=0)
    evidence_items: int = Field(default=0, ge=0)
    evidence_completeness_score: int = Field(ge=0, le=100)
    reproducibility_score: int = Field(ge=0, le=100)
    documentation_score: int = Field(ge=0, le=100)
    operational_dependency_score: int = Field(ge=0, le=100)
    retirement_candidate: bool = False


class ReviewPolicy(BaseModel):
    minimum_evidence_items: int = Field(default=10, ge=1)
    minimum_evidence_completeness_score: int = Field(default=75, ge=0, le=100)
    minimum_reproducibility_score: int = Field(default=70, ge=0, le=100)
    minimum_documentation_score: int = Field(default=70, ge=0, le=100)
    maximum_operational_dependency_score: int = Field(default=60, ge=0, le=100)
    retire_after_consecutive_failures: int = Field(default=3, ge=1, le=20)


class StrategyReviewCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=100)
    human_approved: bool = False
    risk_brain_clear: bool = True
    strategy: StrategyReviewInput
    policy: ReviewPolicy


class KnowledgePackage(BaseModel):
    evidence_ready: bool
    reproducible: bool
    documented: bool
    dependency_safe: bool
    preservation_score: int = Field(ge=0, le=100)
    required_artifacts: list[str]


class StrategyReviewAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    strategy_id: str
    state: ReviewState
    deployable: bool
    recommended_action: str
    reasons: list[str]
    knowledge: KnowledgePackage
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: ReviewState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
