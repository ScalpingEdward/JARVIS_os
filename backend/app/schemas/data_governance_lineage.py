from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DataGovernanceState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    TRUSTED = "trusted"
    LINEAGE_GAP = "lineage-gap"
    QUALITY_ALERT = "quality-alert"
    FRESHNESS_ALERT = "freshness-alert"
    OWNERSHIP_GAP = "ownership-gap"
    ACCESS_ALERT = "access-alert"
    RETENTION_ALERT = "retention-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class DataAssetObservation(BaseModel):
    asset_id: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    owner: Optional[str] = None
    steward: Optional[str] = None
    criticality: float = Field(ge=0.0, le=1.0)
    lineage_coverage: float = Field(ge=0.0, le=1.0)
    source_authority: float = Field(ge=0.0, le=1.0)
    schema_integrity: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    accuracy: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    timeliness: float = Field(ge=0.0, le=1.0)
    access_control_coverage: float = Field(ge=0.0, le=1.0)
    retention_compliance: float = Field(ge=0.0, le=1.0)
    pii_exposure_risk: float = Field(ge=0.0, le=1.0)
    unresolved_quality_issues: int = Field(ge=0)
    downstream_dependencies: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class DataGovernanceCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    observations: List[DataAssetObservation] = Field(min_length=1)
    required_lineage_coverage: float = Field(ge=0.0, le=1.0, default=0.85)
    required_quality_score: float = Field(ge=0.0, le=1.0, default=0.80)
    max_pii_exposure_risk: float = Field(ge=0.0, le=1.0, default=0.20)


class DataAssetDisposition(BaseModel):
    asset_id: str
    trust_score: float
    residual_data_risk: float
    lifecycle_signal: str
    required_actions: List[str]


class DataGovernanceScores(BaseModel):
    lineage_strength: float
    quality_strength: float
    freshness_strength: float
    ownership_strength: float
    access_governance_strength: float
    retention_strength: float
    aggregate_trust: float
    aggregate_residual_risk: float
    confidence: float


class DataGovernanceRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: DataGovernanceState
    scores: DataGovernanceScores
    dispositions: List[DataAssetDisposition]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class DataGovernanceAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
