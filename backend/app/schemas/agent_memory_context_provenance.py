from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentMemoryState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    TRUSTED = "trusted"
    PROVENANCE_ALERT = "provenance-alert"
    STALE_CONTEXT_ALERT = "stale-context-alert"
    CONTAMINATION_ALERT = "contamination-alert"
    RETENTION_ALERT = "retention-alert"
    SENSITIVE_MEMORY_ALERT = "sensitive-memory-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class MemoryContextObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    memory_id: str = Field(min_length=1, max_length=200)
    memory_type: str = Field(min_length=1, max_length=120)
    source_authority: float = Field(ge=0.0, le=1.0)
    provenance_coverage: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    context_relevance: float = Field(ge=0.0, le=1.0)
    conflict_resolution_score: float = Field(ge=0.0, le=1.0)
    contamination_resilience: float = Field(ge=0.0, le=1.0)
    retention_compliance: float = Field(ge=0.0, le=1.0)
    sensitive_data_control: float = Field(ge=0.0, le=1.0)
    deletion_traceability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    stale_reads: int = Field(default=0, ge=0)
    provenance_gaps: int = Field(default=0, ge=0)
    conflicting_memory_events: int = Field(default=0, ge=0)
    contamination_events: int = Field(default=0, ge=0)
    retention_breaches: int = Field(default=0, ge=0)
    sensitive_memory_events: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class AgentMemoryContextCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[MemoryContextObservation] = Field(min_length=1)
    min_source_authority: float = Field(default=0.80, ge=0.0, le=1.0)
    min_provenance_coverage: float = Field(default=0.90, ge=0.0, le=1.0)
    min_freshness_score: float = Field(default=0.75, ge=0.0, le=1.0)
    min_contamination_resilience: float = Field(default=0.85, ge=0.0, le=1.0)
    min_retention_compliance: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_memory_observations(self):
        pairs = [(o.agent_id, o.memory_id) for o in self.observations]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate agent/memory observation")
        return self


class MemoryContextDisposition(BaseModel):
    agent_id: str
    memory_id: str
    memory_type: str
    assurance_score: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class AgentMemoryContextScores(BaseModel):
    provenance_assurance: float = Field(ge=0.0, le=1.0)
    freshness_assurance: float = Field(ge=0.0, le=1.0)
    relevance_assurance: float = Field(ge=0.0, le=1.0)
    contamination_resilience: float = Field(ge=0.0, le=1.0)
    retention_assurance: float = Field(ge=0.0, le=1.0)
    sensitive_data_assurance: float = Field(ge=0.0, le=1.0)
    deletion_traceability: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentMemoryContextRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: AgentMemoryState
    scores: AgentMemoryContextScores
    dispositions: List[MemoryContextDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class AgentMemoryContextAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
