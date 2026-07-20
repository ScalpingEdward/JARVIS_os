from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExecutorTransportState(str, Enum):
    blocked = "blocked"
    configuration_required = "configuration-required"
    credential_rejected = "credential-rejected"
    transport_unavailable = "transport-unavailable"
    circuit_open = "circuit-open"
    health_degraded = "health-degraded"
    invocation_ready = "invocation-ready"
    dispatched = "dispatched"


class TransportKind(str, Enum):
    python = "python"
    http = "http"
    rpc = "rpc"


class TransportObservation(BaseModel):
    dependency_installed: bool = True
    import_verified: bool = True
    adapter_factory_verified: bool = True
    endpoint_resolved: bool = False
    callable_resolved: bool = False
    protocol_compatible: bool = False
    tls_verified: bool = False
    hostname_verified: bool = False
    credential_reference_resolved: bool = False
    credential_scope_verified: bool = False
    raw_credentials_present: bool = False
    health_probe_verified: bool = False
    circuit_breaker_registered: bool = False
    circuit_open: bool = False
    request_serialization_verified: bool = False
    response_deserialization_verified: bool = False
    correlation_headers_verified: bool = False
    cancellation_propagation_verified: bool = False
    invocation_acknowledged: bool = False
    latency_ms: int = Field(default=0, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)
    inflight_requests: int = Field(default=0, ge=0)
    response_bytes: int = Field(default=0, ge=0)


class ExecutorTransportPolicy(BaseModel):
    allowed_transports: list[TransportKind] = Field(default_factory=lambda: list(TransportKind))
    require_dependency_and_factory: bool = True
    require_endpoint_or_callable: bool = True
    require_protocol_compatibility: bool = True
    require_tls_for_remote_transport: bool = True
    require_hostname_verification: bool = True
    require_scoped_credential_reference: bool = True
    prohibit_raw_credentials: bool = True
    require_health_probe: bool = True
    require_circuit_breaker: bool = True
    require_serialization_contract: bool = True
    require_correlation_headers: bool = True
    require_cancellation_propagation: bool = True
    require_invocation_ack: bool = True
    maximum_latency_ms: int = Field(default=20_000, gt=0)
    maximum_consecutive_failures: int = Field(default=5, ge=0)
    maximum_inflight_requests: int = Field(default=100, ge=1)
    maximum_response_bytes: int = Field(default=5_000_000, ge=1)


class ExecutorTransportAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    module_executor_assessment_id: str = Field(min_length=1, max_length=120)
    module_executor_state: str = Field(min_length=1, max_length=40)
    invocation_id: UUID
    transport_id: str = Field(min_length=1, max_length=120)
    transport_kind: TransportKind
    target_module: str = Field(min_length=1, max_length=180)
    endpoint_or_callable: str = Field(min_length=1, max_length=500)
    protocol_version: str = Field(min_length=1, max_length=60)
    credential_reference: str | None = Field(default=None, max_length=240)
    observation: TransportObservation = Field(default_factory=TransportObservation)
    risk_brain_clear: bool = True
    policy: ExecutorTransportPolicy = Field(default_factory=ExecutorTransportPolicy)


class ExecutorTransportScores(BaseModel):
    transport_readiness: int = Field(ge=0, le=100)
    credential_integrity: int = Field(ge=0, le=100)
    protocol_integrity: int = Field(ge=0, le=100)
    health_quality: int = Field(ge=0, le=100)
    invocation_reliability: int = Field(ge=0, le=100)
    runtime_confidence: int = Field(ge=0, le=100)


class ExecutorTransportAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    invocation_id: UUID
    transport_id: str
    transport_kind: TransportKind
    target_module: str
    state: ExecutorTransportState
    dispatchable: bool
    target_runtime: str | None
    recommended_action: str
    scores: ExecutorTransportScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutorTransportStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    dispatched: int
    degraded_or_open: int
    latest_state: ExecutorTransportState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    invocation_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
