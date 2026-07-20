from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    FailureClass,
    ModuleExecutorAssessment,
    ModuleExecutorAssessmentCreate,
    ModuleExecutorScores,
    ModuleExecutorState,
    ModuleExecutorStatusResponse,
)


class ExecutiveModuleExecutorAdapterService:
    def __init__(self) -> None:
        self._records: dict[UUID, ModuleExecutorAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._invocation_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: ModuleExecutorAssessmentCreate) -> ModuleExecutorAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        invocation_key = (payload.workspace_id, payload.invocation_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate module executor source key")
        if invocation_key in self._invocation_ids:
            raise ValueError("Duplicate module invocation")

        o, p = payload.observation, payload.policy
        reasons: list[str] = []
        adapter_safe = o.adapter_registered and o.adapter_enabled and o.module_match
        version_safe = o.version_compatible
        schema_safe = o.input_schema_valid and o.output_schema_valid
        sandbox_safe = (
            o.sandbox_enabled
            and o.filesystem_isolated
            and o.network_policy_verified
            and o.environment_allowlist_verified
            and o.secret_references_isolated
            and not o.raw_secrets_present
        )
        resource_safe = (
            o.cpu_seconds <= p.maximum_cpu_seconds
            and o.memory_mb <= p.maximum_memory_mb
            and o.duration_ms <= p.maximum_duration_ms
            and o.output_bytes <= p.maximum_output_bytes
        )
        result_safe = o.invocation_completed and o.result_normalized and o.result_checkpoint_persisted
        retryable = o.failure_class in p.retryable_failure_classes

        if not payload.risk_brain_clear:
            state, action = ModuleExecutorState.blocked, "block-module-invocation"
            reasons.append("Risk Brain blocks module invocation")
        elif payload.workflow_executor_state not in {"task-ready", "dispatched", "recovery-required"}:
            state, action = ModuleExecutorState.blocked, "complete-workflow-executor-governance"
            reasons.append("Workflow executor runtime has not authorized invocation")
        elif p.prohibit_raw_secrets and o.raw_secrets_present:
            state, action = ModuleExecutorState.blocked, "remove-raw-executor-secrets"
            reasons.append("Raw executor secrets are prohibited")
        elif p.require_registered_enabled_adapter and not adapter_safe:
            state, action = ModuleExecutorState.adapter_unavailable, "register-compatible-module-adapter"
            reasons.append("Adapter registration, enablement or module match is incomplete")
        elif p.require_version_compatibility and not version_safe:
            state, action = ModuleExecutorState.adapter_unavailable, "select-compatible-adapter-version"
            reasons.append("Adapter version is incompatible with the target module")
        elif p.require_input_output_schema and not schema_safe:
            state, action = ModuleExecutorState.schema_rejected, "repair-invocation-schema-contract"
            reasons.append("Input or output schema validation failed")
        elif p.require_sandbox and not sandbox_safe:
            state, action = ModuleExecutorState.sandbox_rejected, "repair-invocation-sandbox"
            reasons.append("Sandbox, filesystem, network, environment or secret isolation is incomplete")
        elif p.prohibit_unapproved_side_effects and o.side_effects_detected and not payload.human_side_effect_approved:
            state, action = ModuleExecutorState.blocked, "require-human-side-effect-approval"
            reasons.append("Invocation reported unapproved side effects")
        elif not resource_safe:
            state, action = ModuleExecutorState.resource_exceeded, "terminate-resource-exceeding-invocation"
            reasons.append("CPU, memory, duration or output budget exceeded")
        elif o.failure_class != FailureClass.none:
            if retryable:
                state, action = ModuleExecutorState.retryable_failure, "return-retryable-failure-to-v18-68"
                reasons.append("Invocation failed with a retryable failure class")
            else:
                state, action = ModuleExecutorState.terminal_failure, "return-terminal-failure-to-v18-67"
                reasons.append("Invocation failed with a terminal failure class")
        elif not o.invocation_attempted:
            state, action = ModuleExecutorState.result_ready, "invoke-approved-module-adapter"
            reasons.append("Adapter and sandbox passed all pre-invocation gates")
        elif p.require_result_checkpoint and not result_safe:
            state, action = ModuleExecutorState.terminal_failure, "normalize-and-checkpoint-module-result"
            reasons.append("Completed invocation lacks normalized persistent result evidence")
        else:
            state, action = ModuleExecutorState.result_ready, "accept-normalized-module-result"
            reasons.append("Module invocation and normalized result passed all gates")

        dispatchable = state == ModuleExecutorState.result_ready
        if dispatchable:
            state = ModuleExecutorState.dispatched
            action = "dispatch-normalized-result-to-v18-68"
            reasons.append("Normalized result is ready for workflow executor checkpointing")

        values = [adapter_safe and version_safe, schema_safe, sandbox_safe, resource_safe, result_safe or not o.invocation_attempted]
        scores = [100 if value else 0 for value in values]
        record = ModuleExecutorAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            task_id=payload.task_id,
            invocation_id=payload.invocation_id,
            adapter_id=payload.adapter_id,
            target_module=payload.target_module,
            state=state,
            failure_class=o.failure_class,
            dispatchable=dispatchable,
            retryable=retryable,
            target_runtime="executive-workflow-executor-runtime" if dispatchable or retryable else None,
            recommended_action=action,
            scores=ModuleExecutorScores(
                adapter_readiness=scores[0],
                schema_integrity=scores[1],
                sandbox_integrity=scores[2],
                resource_safety=scores[3],
                result_integrity=scores[4],
                executor_confidence=round(sum(scores) / len(scores)),
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._invocation_ids.add(invocation_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, invocation_id=payload.invocation_id, actor_id=payload.actor_id, action=action))
        return record

    def list_assessments(self, workspace_id: str) -> list[ModuleExecutorAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ModuleExecutorAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ModuleExecutorStatusResponse:
        records = self.list_assessments(workspace_id)
        return ModuleExecutorStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            dispatched=sum(record.state == ModuleExecutorState.dispatched for record in records),
            retryable_failures=sum(record.state == ModuleExecutorState.retryable_failure for record in records),
            terminal_failures=sum(record.state == ModuleExecutorState.terminal_failure for record in records),
            latest_state=records[-1].state if records else None,
        )


executive_module_executor_adapter_service = ExecutiveModuleExecutorAdapterService()
