from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class CapabilityRegistryState(str, Enum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class AgentToolGrant(BaseModel):
    tool_name: str = Field(min_length=1, max_length=160)
    permissions: List[str] = Field(default_factory=list)
    read_only: bool = True
    requires_human_approval: bool = True
    max_calls_per_task: int = Field(default=10, ge=0, le=10000)


class AgentCapabilityProfile(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=160)
    capabilities: List[str] = Field(min_length=1)
    tool_grants: List[AgentToolGrant] = Field(default_factory=list)
    allowed_data_domains: List[str] = Field(default_factory=list)
    denied_actions: List[str] = Field(default_factory=list)
    max_parallel_tasks: int = Field(default=1, ge=1, le=100)
    task_timeout_seconds: int = Field(default=900, ge=1, le=86400)
    daily_budget_units: float = Field(default=100.0, ge=0.0)
    confidence_floor: float = Field(default=0.70, ge=0.0, le=1.0)
    criticality: float = Field(default=0.50, ge=0.0, le=1.0)
    human_owner: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_unique_tool_grants(self):
        names = [grant.tool_name for grant in self.tool_grants]
        if len(names) != len(set(names)):
            raise ValueError("duplicate tool grant")
        return self


class CapabilityRegistryCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    profile: AgentCapabilityProfile


class CapabilityRegistryRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: CapabilityRegistryState
    profile: AgentCapabilityProfile
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class CapabilityRegistryAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class CapabilityMatchRequest(BaseModel):
    workspace_id: str = Field(min_length=1)
    required_capabilities: List[str] = Field(min_length=1)
    required_tools: List[str] = Field(default_factory=list)
    data_domains: List[str] = Field(default_factory=list)
    minimum_confidence: float = Field(default=0.70, ge=0.0, le=1.0)


class CapabilityMatchResult(BaseModel):
    agent_id: str
    agent_version: str
    role: str
    capability_coverage: float = Field(ge=0.0, le=1.0)
    tool_coverage: float = Field(ge=0.0, le=1.0)
    data_domain_coverage: float = Field(ge=0.0, le=1.0)
    eligible: bool
    reasons: List[str] = Field(default_factory=list)
