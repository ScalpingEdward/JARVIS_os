from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ToolAdapterState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ToolAdapterDefinition(BaseModel):
    adapter_id: str = Field(min_length=1, max_length=160)
    adapter_version: str = Field(min_length=1, max_length=80)
    connector_type: str = Field(min_length=1, max_length=120)
    supported_tools: List[str] = Field(min_length=1)
    supported_operations: List[str] = Field(min_length=1)
    permission_scopes: List[str] = Field(default_factory=list)
    data_domains: List[str] = Field(default_factory=list)
    side_effect_level: str = Field(default="read-only")
    requires_human_approval: bool = True
    health_score: float = Field(default=1.0, ge=0.0, le=1.0)
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    max_calls_per_minute: int = Field(default=30, ge=1, le=1000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    allowed_hosts: List[str] = Field(default_factory=list)
    denied_operations: List[str] = Field(default_factory=list)
    credential_reference: Optional[str] = None


class ToolAdapterRegistryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    adapter: ToolAdapterDefinition
    min_health_score: float = Field(default=0.90, ge=0.0, le=1.0)
    min_reliability_score: float = Field(default=0.90, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_operations(self):
        overlap = set(self.adapter.supported_operations) & set(self.adapter.denied_operations)
        if overlap:
            raise ValueError("supported and denied operations overlap")
        return self


class ToolAdapterRegistryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ToolAdapterState
    adapter: ToolAdapterDefinition
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class ToolAdapterRegistryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class ToolAdapterMatchRequest(BaseModel):
    workspace_id: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    permission_scopes: List[str] = Field(default_factory=list)
    data_domain: Optional[str] = None
    require_side_effects: bool = False


class ToolAdapterMatch(BaseModel):
    record_id: str
    adapter_id: str
    adapter_version: str
    eligible: bool
    reasons: List[str] = Field(default_factory=list)
