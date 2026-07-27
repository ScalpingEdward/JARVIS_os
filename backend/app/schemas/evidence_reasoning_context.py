from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ReasoningContextState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    READY = "ready"
    CONFLICT = "conflict"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class EvidenceItem(BaseModel):
    memory_record_id: str = Field(min_length=1, max_length=160)
    provenance_record_id: str = Field(min_length=1, max_length=160)
    source_citation: str = Field(min_length=1, max_length=512)
    claim_key: str = Field(min_length=1, max_length=200)
    claim_value: str = Field(min_length=1, max_length=4000)
    evidence_bundle_digest: str = Field(min_length=8, max_length=256)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    source_reliability: float = Field(ge=0.0, le=1.0)
    corroboration_count: int = Field(default=0, ge=0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class ReasoningContextCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=2000)
    evidence: List[EvidenceItem] = Field(min_length=1)
    min_confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    min_freshness: float = Field(default=0.60, ge=0.0, le=1.0)
    min_source_reliability: float = Field(default=0.60, ge=0.0, le=1.0)
    require_conflict_resolution: bool = True

    @model_validator(mode="after")
    def unique_memory_records(self):
        ids = [item.memory_record_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate memory_record_id")
        return self


class ConflictFinding(BaseModel):
    claim_key: str
    values: List[str]
    evidence_ids: List[str]
    severity: str
    resolution: Optional[str] = None


class ReasoningContextPacket(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ReasoningContextState
    objective: str
    selected_evidence: List[EvidenceItem]
    conflicts: List[ConflictFinding] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    aggregate_confidence: float = Field(ge=0.0, le=1.0)
    aggregate_freshness: float = Field(ge=0.0, le=1.0)
    packet_digest: str
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class ReasoningContextAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
