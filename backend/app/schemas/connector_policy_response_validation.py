from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ConnectorPolicyState(str, Enum):
    BLOCKED = "blocked"
    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class ConnectorResponseState(str, Enum):
    BLOCKED = "blocked"
    RECEIVED = "received"
    SANITIZED = "sanitized"
    VALIDATED = "validated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ConnectorPolicyProfile(BaseModel):
    connector_id: str = Field(min_length=1, max_length=160)
    connector_type: str = Field(min_length=1, max_length=120)
    allowed_content_types: List[str] = Field(default_factory=lambda: ["application/json"])
    max_response_bytes: int = Field(default=1_048_576, ge=1, le=10_485_760)
    required_fields: List[str] = Field(default_factory=list)
    allowed_top_level_fields: List[str] = Field(default_factory=list)
    redact_fields: List[str] = Field(default_factory=lambda: ["token", "access_token", "authorization", "password", "secret", "api_key"])
    deny_fields: List[str] = Field(default_factory=lambda: ["private_key", "seed_phrase", "raw_credential"])
    max_string_length: int = Field(default=16_384, ge=1, le=1_000_000)
    max_collection_items: int = Field(default=10_000, ge=1, le=100_000)
    strip_html: bool = True
    allow_unknown_fields: bool = False
    require_schema_validation: bool = True
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class ConnectorPolicyCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    profile: ConnectorPolicyProfile


class ConnectorPolicyRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: ConnectorPolicyState
    profile: ConnectorPolicyProfile
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class ConnectorPolicyAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None


class ConnectorResponseEnvelope(BaseModel):
    workspace_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    policy_record_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    response_bytes: int = Field(ge=0)
    payload: Dict[str, Any]


class ConnectorResponseRecord(BaseModel):
    response_id: str
    workspace_id: str
    policy_record_id: str
    connector_id: str
    state: ConnectorResponseState
    sanitized_payload: Dict[str, Any] = Field(default_factory=dict)
    removed_fields: List[str] = Field(default_factory=list)
    redacted_fields: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    receipt_digest: str


class ConnectorResponseAcceptAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)


class ConnectorResponseQuery(BaseModel):
    workspace_id: str = Field(min_length=1)
    connector_id: Optional[str] = None


class ConnectorPolicyMatchRequest(BaseModel):
    workspace_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    response_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def ensure_content_type(self):
        if ";" in self.content_type:
            self.content_type = self.content_type.split(";", 1)[0].strip()
        return self
