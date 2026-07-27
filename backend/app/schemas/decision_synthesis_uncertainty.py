from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class DecisionSynthesisState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    CONFLICT = "conflict"
    APPROVED = "approved"
    READY = "ready"
    REJECTED = "rejected"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class DecisionAlternative(BaseModel):
    alternative_id: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    expected_utility: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    downside_risk: float = Field(ge=0.0, le=1.0)
    reversibility: float = Field(ge=0.0, le=1.0)
    evidence_refs: List[str] = Field(default_factory=list)


class DecisionSynthesisCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    reasoning_record_id: str = Field(min_length=1, max_length=160)
    reasoning_packet_digest: str = Field(min_length=8, max_length=256)
    objective: str = Field(min_length=1, max_length=2000)
    preferred_alternative_id: str = Field(min_length=1, max_length=120)
    alternatives: List[DecisionAlternative] = Field(min_length=2)
    assumptions: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    aggregate_evidence_confidence: float = Field(ge=0.0, le=1.0)
    aggregate_freshness: float = Field(ge=0.0, le=1.0)
    context_conflict_resolved: bool = True
    min_decision_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    max_uncertainty: float = Field(default=0.35, ge=0.0, le=1.0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_alternatives(self):
        ids = [a.alternative_id for a in self.alternatives]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate alternative_id")
        if self.preferred_alternative_id not in ids:
            raise ValueError("preferred alternative not present")
        return self


class DecisionSynthesisScores(BaseModel):
    preferred_confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    evidence_assurance: float = Field(ge=0.0, le=1.0)
    alternative_separation: float = Field(ge=0.0, le=1.0)
    reversibility_assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)


class DecisionSynthesisRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: DecisionSynthesisState
    reasoning_record_id: str
    reasoning_packet_digest: str
    objective: str
    preferred_alternative_id: str
    alternatives: List[DecisionAlternative]
    assumptions: List[str]
    unresolved_questions: List[str]
    scores: DecisionSynthesisScores
    risk_flags: List[str] = Field(default_factory=list)
    decision_packet_digest: str
    approved_by: Optional[str] = None
    version: int = 1


class DecisionSynthesisAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
