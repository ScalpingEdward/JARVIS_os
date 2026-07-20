from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    ExecutorTransportAssessment,
    ExecutorTransportAssessmentCreate,
    ExecutorTransportScores,
    ExecutorTransportState,
    ExecutorTransportStatusResponse,
    TransportKind,
)


class ExecutiveExecutorTransportRuntimeService:
    def __init__(self) -> None:
        self._records: dict[UUID, ExecutorTransportAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._transport_invocations: set[tuple[str, str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: ExecutorTransportAssessmentCreate) -> ExecutorTransportAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        invocation_key = (payload.workspace_id, payload.transport_id, payload.invocation_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate executor transport source key")
        if invocation_key in self._transport_invocations:
            raise ValueError("Duplicate executor transport invocation")

        o, p = payload.observation, payload.policy
        reasons: list[str] = []
        remote = payload.transport_kind in {TransportKind.http, TransportKind.rpc}
        dependency_safe = o.dependency_installed and o.import_verified and o.adapter_factory_verified
        target_safe = o.endpoint_resolved if remote else o.callable_resolved
        protocol_safe = o.protocol_compatible and o.request_serialization_verified and o.response_deserialization_verified
        tls_safe = not remote or (o.tls_verified and o.hostname_verified)
        credentials_safe = (
            o.credential_reference_resolved
            and o.credential_scope_verified
            and not o.raw_credentials_present
        )
        health_safe = o.health_probe_verified and o.circuit_breaker_registered and not o.circuit_open
        invocation_safe = (
            o.correlation_headers_verified
            and o.cancellation_propagation_verified
            and o.invocation_acknowledged
        )
        budgets_safe = (
            o.latency_ms <= p.maximum_latency_ms
            and o.consecutive_failures <= p.maximum_consecutive_failures
            and o.inflight_requests <= p.maximum_inflight_requests
            and o.response_bytes <= p.maximum_response_bytes
        )

        if not payload.risk_brain_clear:
            state, action = ExecutorTransportState.blocked, "block-executor-transport"
            reasons.append("Risk Brain blocks executor transport invocation")
        elif payload.module_executor_state not in {"result-ready", "dispatched"}:
            state, action = ExecutorTransportState.blocked, "complete-module-executor-governance"
            reasons.append("Module executor adapter has not authorized transport invocation")
        elif payload.transport_kind not in p.allowed_transports:
            state, action = ExecutorTransportState.configuration_required, "select-approved-transport"
            reasons.append("Transport kind is not permitted")
        elif p.prohibit_raw_credentials and o.raw_credentials_present:
            state, action = ExecutorTransportState.credential_rejected, "remove-raw-transport-credentials"
            reasons.append("Raw transport credentials are prohibited")
        elif p.require_dependency_and_factory and not dependency_safe:
            state, action = ExecutorTransportState.transport_unavailable, "install-and-register-transport-adapter"
            reasons.append("Transport dependency, import or factory verification is incomplete")
        elif p.require_endpoint_or_callable and not target_safe:
            state, action = ExecutorTransportState.configuration_required, "resolve-endpoint-or-callable"
            reasons.append("Transport endpoint or Python callable is unresolved")
        elif p.require_scoped_credential_reference and not credentials_safe:
            state, action = ExecutorTransportState.credential_rejected, "bind-scoped-credential-reference"
            reasons.append("Credential reference or scope verification is incomplete")
        elif p.require_tls_for_remote_transport and not tls_safe:
            state, action = ExecutorTransportState.transport_unavailable, "verify-tls-and-hostname"
            reasons.append("Remote transport TLS or hostname verification failed")
        elif p.require_protocol_compatibility and not protocol_safe:
            state, action = ExecutorTransportState.configuration_required, "repair-transport-protocol-contract"
            reasons.append("Protocol or serialization contract is incompatible")
        elif p.require_circuit_breaker and o.circuit_open:
            state, action = ExecutorTransportState.circuit_open, "wait-for-circuit-recovery"
            reasons.append("Transport circuit breaker is open")
        elif p.require_health_probe and not health_safe:
            state, action = ExecutorTransportState.health_degraded, "restore-transport-health"
            reasons.append("Transport health probe or circuit-breaker registration is incomplete")
        elif not budgets_safe:
            state, action = ExecutorTransportState.health_degraded, "reduce-transport-load-or-latency"
            reasons.append("Latency, failure, inflight or response-size budget is exceeded")
        elif (
            (p.require_correlation_headers and not o.correlation_headers_verified)
            or (p.require_cancellation_propagation and not o.cancellation_propagation_verified)
            or (p.require_invocation_ack and not o.invocation_acknowledged)
        ):
            state, action = ExecutorTransportState.transport_unavailable, "verify-invocation-control-contract"
            reasons.append("Correlation, cancellation or invocation acknowledgement is incomplete")
        else:
            state, action = ExecutorTransportState.invocation_ready, "accept-executor-transport"
            reasons.append("Executor transport passed configuration, credential, health and protocol gates")

        dispatchable = state == ExecutorTransportState.invocation_ready
        if dispatchable:
            state = ExecutorTransportState.dispatched
            action = "dispatch-transport-result-to-v18-69"
            reasons.append("Transport invocation is ready for normalized module execution")

        transport_score = 100 if dependency_safe and target_safe else 0
        credential_score = 100 if credentials_safe else 0
        protocol_score = 100 if protocol_safe and tls_safe else 0
        health_score = 100 if health_safe and budgets_safe else 0
        invocation_score = 100 if invocation_safe else 0
        confidence = round((transport_score + credential_score + protocol_score + health_score + invocation_score) / 5)
        record = ExecutorTransportAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            invocation_id=payload.invocation_id,
            transport_id=payload.transport_id,
            transport_kind=payload.transport_kind,
            target_module=payload.target_module,
            state=state,
            dispatchable=dispatchable,
            target_runtime="executive-module-executor-adapter" if dispatchable else None,
            recommended_action=action,
            scores=ExecutorTransportScores(
                transport_readiness=transport_score,
                credential_integrity=credential_score,
                protocol_integrity=protocol_score,
                health_quality=health_score,
                invocation_reliability=invocation_score,
                runtime_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._transport_invocations.add(invocation_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, invocation_id=payload.invocation_id, actor_id=payload.actor_id, action=action))
        return record

    def list_assessments(self, workspace_id: str) -> list[ExecutorTransportAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ExecutorTransportAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ExecutorTransportStatusResponse:
        records = self.list_assessments(workspace_id)
        return ExecutorTransportStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            dispatched=sum(record.state == ExecutorTransportState.dispatched for record in records),
            degraded_or_open=sum(record.state in {ExecutorTransportState.health_degraded, ExecutorTransportState.circuit_open, ExecutorTransportState.transport_unavailable} for record in records),
            latest_state=records[-1].state if records else None,
        )


executive_executor_transport_runtime_service = ExecutiveExecutorTransportRuntimeService()
