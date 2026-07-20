from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TelethonBootstrapState(str, Enum):
    blocked = "blocked"
    bootstrap_required = "bootstrap-required"
    authentication_required = "authentication-required"
    dry_run_failed = "dry-run-failed"
    runtime_ready = "runtime-ready"
    dispatched = "dispatched"


class TelethonBootstrapObservation(BaseModel):
    client_instantiated: bool = False
    session_loaded: bool = False
    connected: bool = False
    authorized: bool = False
    identity_verified: bool = False
    read_only_verified: bool = True
    dry_run_only: bool = True
    update_handler_registered: bool = False
    media_download_probe_succeeded: bool = False
    write_method_exposed: bool = False
    latency_ms: int = Field(default=0, ge=0)
    reconnects: int = Field(default=0, ge=0)
    flood_wait_seconds: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=120)


class TelethonBootstrapPolicy(BaseModel):
    maximum_latency_ms: int = Field(default=20_000, gt=0)
    maximum_reconnects: int = Field(default=3, ge=0)
    maximum_flood_wait_seconds: int = Field(default=300, ge=0)
    require_authorized_session: bool = True
    require_identity_verification: bool = True
    require_read_only_runtime: bool = True
    require_dry_run: bool = True
    require_update_handler: bool = True
    require_media_download_probe: bool = True
    prohibit_write_methods: bool = True


class TelethonBootstrapAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    sdk_client_assessment_id: str = Field(min_length=1, max_length=120)
    sdk_client_state: str = Field(min_length=1, max_length=40)
    client_id: str = Field(min_length=1, max_length=100)
    session_reference: str = Field(min_length=1, max_length=250)
    session_reference_resolved: bool = False
    raw_session_embedded: bool = False
    expected_account_id: str | None = Field(default=None, max_length=120)
    observed_account_id: str | None = Field(default=None, max_length=120)
    risk_brain_clear: bool = True
    observation: TelethonBootstrapObservation
    policy: TelethonBootstrapPolicy = Field(default_factory=TelethonBootstrapPolicy)


class TelethonBootstrapScores(BaseModel):
    session_integrity: int = Field(ge=0, le=100)
    instantiation_quality: int = Field(ge=0, le=100)
    authentication_quality: int = Field(ge=0, le=100)
    read_only_safety: int = Field(ge=0, le=100)
    dry_run_quality: int = Field(ge=0, le=100)
    bootstrap_confidence: int = Field(ge=0, le=100)


class TelethonBootstrapAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    sdk_client_assessment_id: str
    client_id: str
    state: TelethonBootstrapState
    dispatchable: bool
    target_module: str | None
    recommended_action: str
    scores: TelethonBootstrapScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelethonBootstrapStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    latest_state: TelethonBootstrapState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
