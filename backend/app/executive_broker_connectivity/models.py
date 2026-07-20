from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BrokerConnectivityState(str, Enum):
    blocked = "blocked"
    broker_unavailable = "broker-unavailable"
    authentication_required = "authentication-required"
    session_expired = "session-expired"
    maintenance_mode = "maintenance-mode"
    connection_degraded = "connection-degraded"
    rate_limited = "rate-limited"
    connected = "connected"
    session_ready = "session-ready"


class BrokerKind(str, Enum):
    mt5 = "mt5"
    mt4 = "mt4"
    dxtrade = "dxtrade"
    ctrader = "ctrader"
    interactive_brokers = "interactive-brokers"
    fix_gateway = "fix-gateway"
    rest = "rest"
    paper = "paper"
    simulation = "simulation"


class BrokerCapability(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    available: bool = True


class BrokerSessionObservation(BaseModel):
    configuration_state: str = Field(default="runtime-ready", min_length=1, max_length=40)
    broker_registered: bool = True
    endpoint_resolved: bool = True
    authentication_valid: bool = True
    credential_reference_resolved: bool = True
    raw_credentials_present: bool = False
    tls_verified: bool = True
    hostname_verified: bool = True
    api_version_supported: bool = True
    heartbeat_fresh: bool = True
    session_expired: bool = False
    token_refresh_required: bool = False
    token_refresh_acknowledged: bool = True
    maintenance_mode: bool = False
    rate_limited: bool = False
    connection_healthy: bool = True
    reconnect_required: bool = False
    reconnect_acknowledged: bool = True
    failover_endpoint_available: bool = True
    account_discovery_complete: bool = True
    capability_discovery_complete: bool = True
    capabilities: list[BrokerCapability] = Field(default_factory=list)


class BrokerSessionPolicy(BaseModel):
    require_runtime_configuration: bool = True
    require_registered_broker: bool = True
    require_endpoint_resolution: bool = True
    require_authentication: bool = True
    require_credential_reference: bool = True
    prohibit_raw_credentials: bool = True
    require_tls: bool = True
    require_hostname_verification: bool = True
    require_supported_api_version: bool = True
    require_fresh_heartbeat: bool = True
    require_account_discovery: bool = True
    require_capability_discovery: bool = True
    require_reconnect_ack: bool = True
    require_token_refresh_ack: bool = True


class BrokerSessionAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    session_id: UUID = Field(default_factory=uuid4)
    broker_id: str = Field(min_length=1, max_length=120)
    broker_kind: BrokerKind
    environment: str = Field(min_length=1, max_length=80)
    endpoint: str = Field(min_length=1, max_length=240)
    account_reference: str = Field(min_length=1, max_length=180)
    observation: BrokerSessionObservation = Field(default_factory=BrokerSessionObservation)
    risk_brain_clear: bool = True
    policy: BrokerSessionPolicy = Field(default_factory=BrokerSessionPolicy)


class BrokerSessionAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    session_id: UUID
    broker_id: str
    broker_kind: BrokerKind
    environment: str
    endpoint: str
    account_reference: str
    state: BrokerConnectivityState
    connected: bool
    session_ready: bool
    reconnect_required: bool
    failover_available: bool
    recommended_action: str
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrokerConnectivityStatusResponse(BaseModel):
    workspace_id: str
    sessions: int
    session_ready: int
    degraded_or_blocked: int
    latest_state: BrokerConnectivityState | None
    autonomous_actions_enabled: bool = False


class ReconnectRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    session_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    reconnect_acknowledged: bool = True


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    session_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
