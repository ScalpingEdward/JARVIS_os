from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    MetricsResponse,
    ObservabilityAssessment,
    ObservabilityAssessmentCreate,
    ObservabilityScores,
    ObservabilityState,
    ObservabilityStatusResponse,
)


class ExecutiveObservabilityService:
    def __init__(self) -> None:
        self._records: dict[UUID, ObservabilityAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._trace_ids: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: ObservabilityAssessmentCreate) -> ObservabilityAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        trace_key = (payload.workspace_id, payload.trace_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate observability source key")
        if trace_key in self._trace_ids:
            raise ValueError("Duplicate trace ID")

        o, p = payload.observation, payload.policy
        reasons: list[str] = []
        failure_rate = round((o.failed_operations / o.total_operations * 100), 2) if o.total_operations else 0.0
        trace_safe = o.trace_created and o.trace_context_propagated and o.correlation_id_propagated and o.opentelemetry_compatible
        span_safe = bool(o.spans) and all(
            span.started and span.completed and span.status_recorded and span.attributes_sanitized
            for span in o.spans
        )
        metrics_safe = o.metrics_emitted and o.metrics_exporter_verified and o.trace_exporter_verified
        logs_safe = o.structured_logs_emitted and not o.raw_secrets_present
        attribution_safe = o.error_attribution_verified and o.audit_linked
        budgets_safe = (
            o.workflow_duration_ms <= p.maximum_workflow_duration_ms
            and o.queue_latency_ms <= p.maximum_queue_latency_ms
            and o.adapter_latency_ms <= p.maximum_adapter_latency_ms
            and o.transport_latency_ms <= p.maximum_transport_latency_ms
            and o.retries <= p.maximum_retries
            and failure_rate <= p.maximum_failure_rate_percent
        )

        if not payload.risk_brain_clear:
            state, action = ObservabilityState.blocked, "block-observability-processing"
            reasons.append("Risk Brain blocks observability processing")
        elif payload.executor_transport_state not in {"invocation-ready", "dispatched"}:
            state, action = ObservabilityState.blocked, "complete-executor-transport-governance"
            reasons.append("Executor transport runtime has not authorized observation")
        elif p.prohibit_raw_secrets and o.raw_secrets_present:
            state, action = ObservabilityState.blocked, "remove-secrets-from-telemetry"
            reasons.append("Raw secrets are prohibited in traces, logs and metrics")
        elif p.require_trace_context and (not trace_safe or not span_safe):
            state, action = ObservabilityState.trace_required, "repair-trace-and-span-hierarchy"
            reasons.append("Trace context or span lifecycle is incomplete")
        elif p.require_metrics_and_exporters and not metrics_safe:
            state, action = ObservabilityState.metrics_degraded, "restore-metrics-and-trace-exporters"
            reasons.append("Metrics or trace exporter evidence is incomplete")
        elif p.require_structured_logs and not logs_safe:
            state, action = ObservabilityState.metrics_degraded, "restore-structured-logging"
            reasons.append("Structured logging is incomplete")
        elif (p.require_error_attribution and not attribution_safe) or (p.require_audit_link and not o.audit_linked):
            state, action = ObservabilityState.warning, "repair-error-attribution-and-audit-link"
            reasons.append("Error attribution or audit linkage is incomplete")
        elif not budgets_safe:
            state, action = ObservabilityState.budget_exceeded, "investigate-slo-budget-breach"
            reasons.append("Latency, retry or failure-rate budget exceeded")
        elif failure_rate > p.warning_failure_rate_percent:
            state, action = ObservabilityState.warning, "monitor-elevated-failure-rate"
            reasons.append("Failure rate exceeds warning threshold")
        else:
            state, action = ObservabilityState.observability_ready, "accept-observability-contract"
            reasons.append("Tracing, metrics, logs, attribution and SLO budgets passed")
            state = ObservabilityState.healthy
            action = "dispatch-observability-to-control-plane"

        healthy = state == ObservabilityState.healthy
        trace_score = 100 if trace_safe and span_safe else 0
        metrics_score = 100 if metrics_safe else 0
        log_score = 100 if logs_safe else 0
        attribution_score = 100 if attribution_safe else 0
        slo_score = 100 if budgets_safe else 0
        confidence = round((trace_score + metrics_score + log_score + attribution_score + slo_score) / 5)
        record = ObservabilityAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            trace_id=payload.trace_id,
            correlation_id=payload.correlation_id,
            workflow_instance_id=payload.workflow_instance_id,
            state=state,
            healthy=healthy,
            failure_rate_percent=failure_rate,
            recommended_action=action,
            scores=ObservabilityScores(
                trace_integrity=trace_score,
                metrics_quality=metrics_score,
                log_quality=log_score,
                error_attribution=attribution_score,
                slo_compliance=slo_score,
                observability_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._trace_ids.add(trace_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, trace_id=payload.trace_id, actor_id=payload.actor_id, action=action))
        return record

    def list_assessments(self, workspace_id: str) -> list[ObservabilityAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ObservabilityAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ObservabilityStatusResponse:
        records = self.list_assessments(workspace_id)
        return ObservabilityStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            healthy=sum(record.state == ObservabilityState.healthy for record in records),
            warnings=sum(record.state in {ObservabilityState.warning, ObservabilityState.metrics_degraded, ObservabilityState.trace_required} for record in records),
            budget_exceeded=sum(record.state == ObservabilityState.budget_exceeded for record in records),
            latest_state=records[-1].state if records else None,
        )

    def metrics(self, workspace_id: str) -> MetricsResponse:
        records = self.list_assessments(workspace_id)
        count = len(records)
        total_operations = sum(int(record.failure_rate_percent >= 0) for record in records)
        failed_operations = sum(record.failure_rate_percent > 0 for record in records)
        return MetricsResponse(
            workspace_id=workspace_id,
            traces=count,
            average_workflow_duration_ms=0,
            total_operations=total_operations,
            failed_operations=failed_operations,
            failure_rate_percent=round(failed_operations / total_operations * 100, 2) if total_operations else 0.0,
            total_retries=0,
        )


executive_observability_service = ExecutiveObservabilityService()
