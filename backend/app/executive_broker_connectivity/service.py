from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    BrokerConnectivityState,
    BrokerConnectivityStatusResponse,
    BrokerSessionAssessment,
    BrokerSessionAssessmentCreate,
    ReconnectRequest,
)


class ExecutiveBrokerConnectivityService:
    def __init__(self) -> None:
        self._records: dict[UUID, BrokerSessionAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._session_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._session_ids.clear()
        self._audit.clear()

    def assess(self, payload: BrokerSessionAssessmentCreate) -> BrokerSessionAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        session_key = (payload.workspace_id, payload.session_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate broker connectivity source key")
        if session_key in self._session_ids:
            raise ValueError("Duplicate broker session ID")

        state, reasons, action = self._evaluate(payload)
        connected = state in {BrokerConnectivityState.connected, BrokerConnectivityState.session_ready}
        record = BrokerSessionAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            session_id=payload.session_id,
            broker_id=payload.broker_id,
            broker_kind=payload.broker_kind,
            environment=payload.environment,
            endpoint=payload.endpoint,
            account_reference=payload.account_reference,
            state=state,
            connected=connected,
            session_ready=state == BrokerConnectivityState.session_ready,
            reconnect_required=payload.observation.reconnect_required,
            failover_available=payload.observation.failover_endpoint_available,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._session_ids.add(session_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, session_id=record.session_id, actor_id=payload.actor_id, action="broker-session-assessed"))
        return record

    def _evaluate(self, payload: BrokerSessionAssessmentCreate) -> tuple[BrokerConnectivityState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return BrokerConnectivityState.blocked, ["Risk Brain blocked broker session activation"], "keep-session-blocked"
        if p.require_runtime_configuration and o.configuration_state != "runtime-ready":
            return BrokerConnectivityState.blocked, ["Runtime configuration is not ready"], "resolve-configuration"
        if p.prohibit_raw_credentials and o.raw_credentials_present:
            return BrokerConnectivityState.blocked, ["Raw broker credentials are prohibited"], "replace-with-secret-reference"
        if p.require_registered_broker and (not o.broker_registered or not o.endpoint_resolved):
            return BrokerConnectivityState.broker_unavailable, ["Broker registration or endpoint resolution failed"], "verify-broker-registry"
        if p.require_authentication and (not o.authentication_valid or not o.credential_reference_resolved):
            return BrokerConnectivityState.authentication_required, ["Authentication or credential reference is invalid"], "reauthorize-session"
        if o.session_expired or (o.token_refresh_required and p.require_token_refresh_ack and not o.token_refresh_acknowledged):
            return BrokerConnectivityState.session_expired, ["Broker session or token is expired"], "refresh-session-token"
        if o.maintenance_mode:
            return BrokerConnectivityState.maintenance_mode, ["Broker maintenance mode is active"], "wait-or-failover"
        if o.rate_limited:
            return BrokerConnectivityState.rate_limited, ["Broker rate limit is active"], "apply-backoff"
        transport_ok = o.tls_verified and o.hostname_verified and o.api_version_supported
        discovery_ok = o.account_discovery_complete and o.capability_discovery_complete
        reconnect_ok = not o.reconnect_required or o.reconnect_acknowledged
        if not transport_ok or not o.heartbeat_fresh or not o.connection_healthy or not discovery_ok or not reconnect_ok:
            return BrokerConnectivityState.connection_degraded, ["Connection health, transport verification, discovery or reconnect evidence is incomplete"], "reconnect-or-failover"
        return BrokerConnectivityState.session_ready, ["Broker session passed connectivity governance"], "allow-session-use"

    def list_sessions(self, workspace_id: str) -> list[BrokerSessionAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> BrokerSessionAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def reconnect(self, request: ReconnectRequest) -> BrokerSessionAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.session_id == request.session_id), None)
        if record is None:
            raise KeyError("Broker session not found")
        if not request.reconnect_acknowledged:
            raise ValueError("Reconnect acknowledgement is required")
        record.reconnect_required = False
        record.connected = True
        record.session_ready = True
        record.state = BrokerConnectivityState.session_ready
        record.recommended_action = "allow-session-use"
        record.reasons = ["Reconnect acknowledgement recorded"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, assessment_id=record.id, session_id=record.session_id, actor_id=request.actor_id, action="broker-session-reconnected"))
        return record

    def status(self, workspace_id: str) -> BrokerConnectivityStatusResponse:
        records = self.list_sessions(workspace_id)
        ready = sum(r.session_ready for r in records)
        return BrokerConnectivityStatusResponse(workspace_id=workspace_id, sessions=len(records), session_ready=ready, degraded_or_blocked=len(records) - ready, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_broker_connectivity_service = ExecutiveBrokerConnectivityService()
