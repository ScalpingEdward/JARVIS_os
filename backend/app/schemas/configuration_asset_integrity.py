from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ConfigurationAssetState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    INTEGRITY_VERIFIED = "integrity-verified"
    INVENTORY_GAP = "inventory-gap"
    DRIFT_ALERT = "drift-alert"
    BASELINE_GAP = "baseline-gap"
    OWNERSHIP_GAP = "ownership-gap"
    CONFIGURATION_ALERT = "configuration-alert"
    LIFECYCLE_ALERT = "lifecycle-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AssetObservation(BaseModel):
    asset_id: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    criticality: float = Field(ge=0.0, le=1.0)
    inventory_coverage: float = Field(ge=0.0, le=1.0)
    ownership_coverage: float = Field(ge=0.0, le=1.0)
    baseline_compliance: float = Field(ge=0.0, le=1.0)
    configuration_integrity: float = Field(ge=0.0, le=1.0)
    patch_baseline_compliance: float = Field(ge=0.0, le=1.0)
    hardening_coverage: float = Field(ge=0.0, le=1.0)
    dependency_mapping: float = Field(ge=0.0, le=1.0)
    lifecycle_currency: float = Field(ge=0.0, le=1.0)
    backup_configuration_coverage: float = Field(ge=0.0, le=1.0)
    unauthorized_change_score: float = Field(ge=0.0, le=1.0)
    drift_score: float = Field(ge=0.0, le=1.0)
    open_configuration_findings: int = Field(ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    freshness: float = Field(default=1.0, ge=0.0, le=1.0)


class ConfigurationAssetCreate(BaseModel):
    workspace_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    observations: List[AssetObservation] = Field(min_length=1)
    required_inventory_coverage: float = Field(default=0.95, ge=0.0, le=1.0)
    required_baseline_compliance: float = Field(default=0.90, ge=0.0, le=1.0)
    max_acceptable_residual_risk: float = Field(default=0.35, ge=0.0, le=1.0)


class ConfigurationAssetScores(BaseModel):
    inventory_strength: float
    ownership_strength: float
    baseline_strength: float
    configuration_integrity: float
    lifecycle_strength: float
    dependency_visibility: float
    aggregate_integrity: float
    aggregate_residual_risk: float
    confidence: float


class AssetDisposition(BaseModel):
    asset_id: str
    asset_type: str
    integrity_score: float
    residual_risk: float
    lifecycle_signal: str
    required_actions: List[str]


class ConfigurationAssetRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ConfigurationAssetState
    scores: ConfigurationAssetScores
    dispositions: List[AssetDisposition]
    risk_flags: List[str]
    approved_by: Optional[str] = None
    version: int = 1


class ConfigurationAssetAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
