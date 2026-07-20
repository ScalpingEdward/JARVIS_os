from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class ObservabilityState(str, Enum):
    blocked = "blocked"
    trace_required = "trace-required"
    metrics_degraded = "metrics-degraded"
    budget_exceeded = "budget-exceeded"
    warning = "warning"
    observability_ready = "observability-ready"
    healthy = "healthy"


class SpanKind(str, Enum):
    workflow = "workflow"
    step = "step"
    task = "task"
    adapter = "adapter"
    transport = "transport"
    module = "module"


class SpanObservation(BaseModel):
    span_id: str = Field(min_length=8, max_length=64)
    parent_span_id: str | None = Field(default=None, min_length=8, max_length=64)
    kind: SpanKind
    component: str = Field(min_length=1, max_length=180)
    started: bool = False
    completed: bool = False
    status_recorded: bool = False
    attributes_sanitized: bool = False
    duration_ms: int = Field(default=0, ge=0)
    error_recorded: bool = False


class ObservabilityObservation(BaseModel):
    trace_created: bool = False
    trace_context_propagated: bool = False
    correlation_id_propagated: bool = False
    opentelemetry_compatible: bool = False
    structured_logs_emitted: bool = False
    metrics_emitted: bool = False
    metrics_exporter_verified: bool = False
    trace_exporter_verified: bool = False
    audit_linked: bool = False
    error_attribution_verified: bool = False
    raw_secrets_present: bool = False
    workflow_duration_ms: int = Field(default=0, ge=0)
    queue_latency_ms: int = Field(default=0, ge=0)
    adapter_latency_ms: int = Field(default=0, ge=0)
    transport_latency_ms: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    total_operations: int = Field(default=0, ge=0)
    failed_operations: int = Field(default=0, ge=0)
    spans: list[SpanObservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_spans(self) -> "ObservabilityObservation":
        ids = [span.span_id for span in self.spans]
        if len(ids) != len(set(ids)):
            raise ValueError("Span IDs must be unique within one trace")
        known = set(ids)
        for span in self.spans:
            if span.parent_span_id and span.parent_span_id not in known:
                raise ValueError("Parent span must exist within trace")
        return self


class ObservabilityPolicy(BaseModel):
    require_trace_context: bool = True
    require_correlation_propagation: bool = True
    require_opentelemetry_compatibility: bool = True
    require_structured_logs: bool = True
    require_metrics_and_exporters: bool = True
    require_complete_span_lifecycle: bool = True
    require_error_attribution: bool = True
    require_audit_link: bool = True
    prohibit_raw_secrets: bool = True
    maximum_workflow_duration_ms: int = Field(default=300_000, gt=0)
    maximum_queue_latency_ms: int = Field(default=30_000, gt=0)
    maximum_adapter_latency_ms: int = Field(default=60_000, gt=0)
    maximum_transport_latency_ms: int = Field(default=20_000, gt=0)
    maximum_retries: int = Field(default=10, ge=0)
    maximum_failure_rate_percent: float = Field(default=5.0, ge=0, le=100)
    warning_failure_rate_percent: float = Field(default=2.0, ge=0, le=100)


class ObservabilityAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    executor_transport_assessment_id: str = Field(min_length=1, max_length=120)
    executor_transport_state: str = Field(min_length=1, max_length=40)
    trace_id: str = Field(min_length=16, max_length=64)
    correlation_id: str = Field(min_length=8, max_length=120)
    workflow_instance_id: UUID
    observation: ObservabilityObservation = Field(default_factory=ObservabilityObservation)
    risk_brain_clear: bool = True
    policy: ObservabilityPolicy = Field(default_factory=ObservabilityPolicy)


class ObservabilityScores(BaseModel):
    trace_integrity: int = Field(ge=0, le=100)
    metrics_quality: int = Field(ge=0, le=100)
    log_quality: int = Field(ge=0, le=100)
    error_attribution: int = Field(ge=0, le=100)
    slo_compliance: int = Field(ge=0, le=100)
    observability_confidence: int = Field(ge=0, le=100)


class ObservabilityAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    trace_id: str
    correlation_id: str
    workflow_instance_id: UUID
    state: ObservabilityState
    healthy: bool
    failure_rate_percent: float
    recommended_action: str
    scores: ObservabilityScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ObservabilityStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    healthy: int
    warnings: int
    budget_exceeded: int
    latest_state: ObservabilityState | None
    autonomous_actions_enabled: bool = False


class MetricsResponse(BaseModel):
    workspace_id: str
    traces: int
    average_workflow_duration_ms: int
    total_operations: int
    failed_operations: int
    failure_rate_percent: float
    total_retries: int


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    trace_id: str
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
