from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class TrustedMemoryState(str, Enum):
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    STALE = "stale"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class TrustedMemoryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    agent_id: str = Field(min_length=1, max_length=160)
    provenance_record_id: str = Field(min_length=1, max_length=160)
    evidence_bundle_digest: str = Field(min_length=8, max_length=256)
    source_uri: str = Field(min_length=1, max_length=2048)
    citation_label: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=20000)
    topics: List[str] = Field(default_factory=list, max_length=32)
    data_domains: List[str] = Field(default_factory=list, max_length=16)
    memory_scope: str = Field(default="session", pattern="^(session|project|workspace)$")
    provenance_approved: bool = True
    provenance_state: str = Field(default="active")
    confidence: float = Field(ge=0.0, le=1.0)
    source_reliability: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    ttl_seconds: int = Field(default=3600, ge=60, le=2_592_000)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    min_source_reliability: float = Field(default=0.70, ge=0.0, le=1.0)
    min_freshness: float = Field(default=0.60, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_admission_contract(self):
        if not self.provenance_approved or self.provenance_state != "active":
            raise ValueError("approved active provenance required")
        return self


class TrustedMemoryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    agent_id: str
    provenance_record_id: str
    evidence_bundle_digest: str
    source_uri: str
    citation_label: str
    content: str
    topics: List[str]
    data_domains: List[str]
    memory_scope: str
    confidence: float
    source_reliability: float
    freshness: float
    ttl_seconds: int
    state: TrustedMemoryState
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    activated_at_epoch: Optional[int] = None
    expires_at_epoch: Optional[int] = None
    version: int = 1


class TrustedMemoryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class TrustedMemoryRetrieve(BaseModel):
    workspace_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    topics: List[str] = Field(default_factory=list)
    data_domains: List[str] = Field(default_factory=list)
    max_items: int = Field(default=8, ge=1, le=32)
    min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    min_freshness: float = Field(default=0.60, ge=0.0, le=1.0)


class TrustedMemoryHit(BaseModel):
    record_id: str
    citation_label: str
    source_uri: str
    provenance_record_id: str
    evidence_bundle_digest: str
    content: str
    confidence: float
    freshness: float
    score: float
