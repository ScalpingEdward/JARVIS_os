from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ChangeProposalState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    VALIDATED = "validated"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    EXECUTION_READY = "execution-ready"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ChangeStep(BaseModel):
    step_id: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=240)
    parameters: Dict[str, str] = Field(default_factory=dict)
    reversible: bool = True
    expected_duration_seconds: int = Field(default=30, ge=0, le=86400)


class ChangeProposalCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    candidate_id: str = Field(min_length=1, max_length=160)
    target_system: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=4000)
    expected_gain: float = Field(ge=-1.0, le=10.0)
    validation_confidence: float = Field(ge=0.0, le=1.0)
    blast_radius: float = Field(ge=0.0, le=1.0)
    rollback_readiness: float = Field(ge=0.0, le=1.0)
    observability_readiness: float = Field(ge=0.0, le=1.0)
    dependency_readiness: float = Field(ge=0.0, le=1.0)
    execution_window_ready: bool = False
    preconditions: List[str] = Field(min_length=1)
    postconditions: List[str] = Field(min_length=1)
    rollback_criteria: List[str] = Field(min_length=1)
    steps: List[ChangeStep] = Field(min_length=1)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_steps(self):
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate change step_id")
        return self


class ChangeProposalAssessment(BaseModel):
    contract_assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    execution_contract_complete: bool
    risk_flags: List[str] = Field(default_factory=list)
    required_actions: List[str] = Field(default_factory=list)


class ChangeProposalRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    candidate_id: str
    target_system: str
    state: ChangeProposalState
    assessment: ChangeProposalAssessment
    approved_by: Optional[str] = None
    execution_authorized_by: Optional[str] = None
    version: int = 1


class ChangeProposalAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
