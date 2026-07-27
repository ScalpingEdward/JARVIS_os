from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ProvenanceState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    STALE = "stale"
    LOW_CONFIDENCE = "low-confidence"
    EVIDENCE_GAP = "evidence-gap"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ExternalEvidenceObservation(BaseModel):
    response_id: str = Field(min_length=1, max_length=160)
    connector_id: str = Field(min_length=1, max_length=160)
    source_uri: str = Field(min_length=1, max_length=2048)
    source_identity: str = Field(min_length=1, max_length=255)
    source_timestamp: str = Field(min_length=1, max_length=80)
    observed_at: str = Field(min_length=1, max_length=80)
    evidence_hash: str = Field(min_length=8, max_length=256)
    payload_digest: str = Field(min_length=8, max_length=256)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    source_reliability: float = Field(ge=0.0, le=1.0)
    schema_validation_passed: bool = True
    sanitization_passed: bool = True
    accepted_response: bool = True
    corroboration_count: int = Field(default=0, ge=0)
    metadata: Dict[str, str] = Field(default_factory=dict)


class ExternalEvidenceCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[ExternalEvidenceObservation] = Field(min_length=1)
    min_confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    min_freshness: float = Field(default=0.75, ge=0.0, le=1.0)
    min_source_reliability: float = Field(default=0.80, ge=0.0, le=1.0)
    require_accepted_response: bool = True
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_responses(self):
        ids = [o.response_id for o in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate response_id")
        return self


class ExternalEvidenceDisposition(BaseModel):
    response_id: str
    connector_id: str
    provenance_assurance: float = Field(ge=0.0, le=1.0)
    evidence_confidence: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class ExternalEvidenceScores(BaseModel):
    identity_assurance: float = Field(ge=0.0, le=1.0)
    integrity_assurance: float = Field(ge=0.0, le=1.0)
    freshness_assurance: float = Field(ge=0.0, le=1.0)
    confidence_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)


class ExternalEvidenceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ProvenanceState
    scores: ExternalEvidenceScores
    dispositions: List[ExternalEvidenceDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    evidence_bundle_digest: str
    version: int = 1


class ExternalEvidenceAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
