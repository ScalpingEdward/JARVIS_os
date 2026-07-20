from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ModuleExecutorState(str, Enum):
    blocked = "blocked"
    adapter_unavailable = "adapter-unavailable"
    schema_rejected = "schema-rejected"
    sandbox_rejected = "sandbox-rejected"
    resource_exceeded = "resource-exceeded"
    retryable_failure = "retryable-failure"
    terminal_failure = "terminal-failure"
    result_ready = "result-ready"
    dispatched = "dispatched"


class FailureClass(str, Enum):
    none = "none"
    transient = "transient"
    timeout = "timeout"
    rate_limited = "rate-limited"
    dependency = "dependency"
    validation = "validation"
    permission = "permission"
    permanent = "permanent"


class AdapterObservation(BaseModel):
    adapter_registered: bool = False
    adapter_enabled: bool = False
    module_match: bool = False
    version_compatible: bool = False
    input_schema_valid: bool = False
    output_schema_valid: bool = False
    sandbox_enabled: bool = False
    filesystem_isolated: bool = False
    network_policy_verified: bool = False
    environment_allowlist_verified: bool = False
    secret_references_isolated: bool = False
    raw_secrets_present: bool = False
    invocation_attempted: bool = False
    invocation_completed: bool = False
    result_normalized: bool = False
    result_checkpoint_persisted: bool = False
    side_effects_detected: bool = False
    cpu_seconds: int = Field(default=0, ge=0)
    memory_mb: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    output_bytes: int = Field(default=0, ge=0)
    exit_code: int | None = None
    error_code: str | None = Field(default=None, max_length=120)
    failure_class: FailureClass = FailureClass.none


class ModuleExecutorPolicy(BaseModel):
    maximum_cpu_seconds: int = Field(default=60, ge=1)
    maximum_memory_mb: int = Field(default=1024, ge=64)
    maximum_duration_ms: int = Field(default=60_000, ge=100)
    maximum_output_bytes: int = Field(default=5_000_000, ge=1)
    require_registered_enabled_adapter: bool = True
    require_version_compatibility: bool = True
    require_input_output_schema: bool = True
    require_sandbox: bool = True
    require_filesystem_isolation: bool = True
    require_network_policy: bool = True
    require_environment_allowlist: bool = True
    require_secret_reference_isolation: bool = True
    require_result_checkpoint: bool = True
    prohibit_raw_secrets: bool = True
    prohibit_unapproved_side_effects: bool = True
    retryable_failure_classes: list[FailureClass] = Field(default_factory=lambda: [FailureClass.transient, FailureClass.timeout, FailureClass.rate_limited, FailureClass.dependency])


class ModuleExecutorAssessmentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    source_key: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=100)
    workflow_executor_assessment_id: str = Field(min_length=1, max_length=120)
    workflow_executor_state: str = Field(min_length=1, max_length=40)
    task_id: UUID
    invocation_id: UUID = Field(default_factory=uuid4)
    adapter_id: str = Field(min_length=1, max_length=120)
    adapter_version: str = Field(min_length=1, max_length=60)
    target_module: str = Field(min_length=1, max_length=180)
    input_schema: str = Field(min_length=1, max_length=180)
    output_schema: str = Field(min_length=1, max_length=180)
    observation: AdapterObservation = Field(default_factory=AdapterObservation)
    risk_brain_clear: bool = True
    human_side_effect_approved: bool = False
    policy: ModuleExecutorPolicy = Field(default_factory=ModuleExecutorPolicy)


class ModuleExecutorScores(BaseModel):
    adapter_readiness: int = Field(ge=0, le=100)
    schema_integrity: int = Field(ge=0, le=100)
    sandbox_integrity: int = Field(ge=0, le=100)
    resource_safety: int = Field(ge=0, le=100)
    result_integrity: int = Field(ge=0, le=100)
    executor_confidence: int = Field(ge=0, le=100)


class ModuleExecutorAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    source_key: str
    actor_id: str
    task_id: UUID
    invocation_id: UUID
    adapter_id: str
    target_module: str
    state: ModuleExecutorState
    failure_class: FailureClass
    dispatchable: bool
    retryable: bool
    target_runtime: str | None
    recommended_action: str
    scores: ModuleExecutorScores
    reasons: list[str]
    autonomous_actions_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModuleExecutorStatusResponse(BaseModel):
    workspace_id: str
    assessments: int
    dispatched: int
    retryable_failures: int
    terminal_failures: int
    latest_state: ModuleExecutorState | None
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    workspace_id: str
    assessment_id: UUID
    invocation_id: UUID
    actor_id: str
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
