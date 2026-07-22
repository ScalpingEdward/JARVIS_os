from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class RolloutState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_REQUIRED = "evidence-required"
    DRAFT = "draft"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    APPROVED = "approved"
    CANARY_RUNNING = "canary-running"
    PAUSED = "paused"
    PROMOTION_READY = "promotion-ready"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled-back"
    FAILED = "failed"
    ARCHIVED = "archived"


class CanaryMetric(BaseModel):
    metric_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    baseline_value: float
    failure_threshold: float
    direction: Literal["max", "min"]
    observed_value: float | None = None


class RolloutStage(BaseModel):
    stage_id: str = Field(min_length=1, max_length=100)
    traffic_percent: float = Field(gt=0, le=100)
    minimum_observations: int = Field(ge=1, le=1_000_000)
    completed: bool = False


class RolloutCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=160)
    reliability_record_id: str = Field(min_length=1, max_length=160)
    proposal_ids: list[str] = Field(min_length=1)
    target_runtime_ids: list[str] = Field(min_length=1)
    config_version: str = Field(min_length=1, max_length=100)
    rollback_version: str = Field(min_length=1, max_length=100)
    stages: list[RolloutStage] = Field(min_length=1)
    metrics: list[CanaryMetric] = Field(min_length=1)
    upstream_evidence_verified: bool = True
    risk_brain_blocked: bool = False

    @model_validator(mode="after")
    def validate_integrity(self) -> "RolloutCreate":
        if len(set(self.proposal_ids)) != len(self.proposal_ids):
            raise ValueError("duplicate proposal id")
        if len(set(self.target_runtime_ids)) != len(self.target_runtime_ids):
            raise ValueError("duplicate target runtime id")
        stage_ids = [item.stage_id for item in self.stages]
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("duplicate rollout stage id")
        percentages = [item.traffic_percent for item in self.stages]
        if percentages != sorted(percentages):
            raise ValueError("rollout stages must be ordered by traffic percent")
        if percentages[-1] != 100:
            raise ValueError("final rollout stage must reach 100 percent")
        metric_ids = [item.metric_id for item in self.metrics]
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("duplicate canary metric id")
        if self.config_version == self.rollback_version:
            raise ValueError("rollback version must differ from config version")
        return self


class RolloutAction(BaseModel):
    action: Literal[
        "approve",
        "start-canary",
        "observe",
        "advance-stage",
        "pause",
        "resume",
        "promote",
        "rollback",
        "fail",
        "archive",
    ]
    actor_id: str = Field(min_length=1, max_length=160)
    approval_token: str | None = Field(default=None, min_length=1)
    receipt_id: str | None = Field(default=None, min_length=1)
    observations: dict[str, float] | None = None
    observation_count: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class RolloutRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_key: str
    reliability_record_id: str
    proposal_ids: list[str]
    target_runtime_ids: list[str]
    config_version: str
    rollback_version: str
    stages: list[RolloutStage]
    metrics: list[CanaryMetric]
    current_stage_index: int = 0
    observation_count: int = 0
    state: RolloutState
    risk_brain_blocked: bool
    upstream_evidence_verified: bool
    approval_token_hash: str | None = None
    last_receipt_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    record_id: str
    workspace_id: str
    action: str
    actor_id: str
    state: RolloutState
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
