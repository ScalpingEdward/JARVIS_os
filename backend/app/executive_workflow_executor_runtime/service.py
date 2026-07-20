from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    WorkflowExecutorAssessment,
    WorkflowExecutorAssessmentCreate,
    WorkflowExecutorScores,
    WorkflowExecutorState,
    WorkflowExecutorStatusResponse,
)


class ExecutiveWorkflowExecutorRuntimeService:
    def __init__(self) -> None:
        self._records: dict[UUID, WorkflowExecutorAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._task_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: WorkflowExecutorAssessmentCreate) -> WorkflowExecutorAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        task_key = (payload.workspace_id, payload.task_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate workflow executor source key")
        if task_key in self._task_ids:
            raise ValueError("Duplicate workflow task")

        o, p = payload.observation, payload.policy
        reasons: list[str] = []
        task_safe = o.task_persisted and o.queue_registered
        worker_safe = o.worker_registered and o.worker_capability_match
        lease_safe = o.lease_acquired and o.lease_owner_verified and o.lease_age_seconds <= p.maximum_lease_age_seconds
        heartbeat_safe = o.heartbeat_verified and o.heartbeat_age_seconds <= p.maximum_heartbeat_age_seconds
        timer_safe = o.timer_persisted and o.retry_delay_seconds <= p.maximum_retry_delay_seconds
        execution_safe = o.execution_age_seconds <= p.maximum_execution_age_seconds
        queue_safe = o.queue_depth <= p.maximum_queue_depth
        recovery_needed = o.lease_expired or (o.attempts > 0 and not o.dispatch_acknowledged)
        recoverable = recovery_needed and p.allow_expired_lease_recovery and o.retry_checkpoint_persisted

        if not payload.risk_brain_clear:
            state, action = WorkflowExecutorState.blocked, "block-workflow-task-execution"
            reasons.append("Risk Brain blocks workflow executor activity")
        elif payload.workflow_state not in {"running", "retrying", "compensating"}:
            state, action = WorkflowExecutorState.blocked, "complete-workflow-orchestrator-governance"
            reasons.append("Workflow orchestrator has not authorized task execution")
        elif p.prohibit_raw_worker_credentials and o.raw_worker_credentials_present:
            state, action = WorkflowExecutorState.blocked, "remove-raw-worker-credentials"
            reasons.append("Raw worker credentials are prohibited")
        elif p.require_task_persistence and not task_safe:
            state, action = WorkflowExecutorState.blocked, "persist-task-and-register-queue"
            reasons.append("Task durability or queue registration is incomplete")
        elif p.require_worker_capability_match and not worker_safe:
            state, action = WorkflowExecutorState.worker_unavailable, "register-capable-worker"
            reasons.append("No registered worker matches the target module capability")
        elif recovery_needed:
            if recoverable:
                state, action = WorkflowExecutorState.recovery_required, "recover-expired-or-unacknowledged-task"
                reasons.append("Task requires controlled lease or dispatch recovery")
            else:
                state, action = WorkflowExecutorState.lease_conflict, "repair-task-recovery-checkpoint"
                reasons.append("Lease or acknowledgement recovery evidence is incomplete")
        elif p.require_lease_and_heartbeat and (not lease_safe or not heartbeat_safe):
            state, action = WorkflowExecutorState.lease_conflict, "repair-worker-lease-and-heartbeat"
            reasons.append("Worker lease ownership or heartbeat freshness is invalid")
        elif p.require_durable_timer and (not timer_safe or not o.timer_due):
            state, action = WorkflowExecutorState.waiting_timer, "wait-for-durable-task-timer"
            reasons.append("Durable timer is not persisted or not yet due")
        elif o.attempts >= p.maximum_attempts:
            state, action = WorkflowExecutorState.blocked, "escalate-exhausted-task-retries"
            reasons.append("Task exhausted the bounded retry budget")
        elif not execution_safe or not queue_safe:
            state, action = WorkflowExecutorState.worker_unavailable, "reduce-task-age-or-queue-depth"
            reasons.append("Execution age or queue depth exceeds policy")
        elif o.attempts > 0 and not o.result_checkpoint_persisted:
            state, action = WorkflowExecutorState.retry_scheduled, "persist-result-checkpoint-before-retry"
            reasons.append("Retry requires a durable result checkpoint")
        elif p.require_dispatch_ack and not o.dispatch_acknowledged:
            state, action = WorkflowExecutorState.task_ready, "dispatch-task-and-require-ack"
            reasons.append("Task passed runtime gates and is ready for acknowledged dispatch")
        elif p.require_result_checkpoint and not o.result_checkpoint_persisted:
            state, action = WorkflowExecutorState.task_ready, "persist-task-result-checkpoint"
            reasons.append("Dispatch was acknowledged; result checkpoint remains required")
        elif not o.graceful_shutdown_verified:
            state, action = WorkflowExecutorState.worker_unavailable, "verify-worker-lifecycle"
            reasons.append("Worker graceful shutdown contract is incomplete")
        else:
            state, action = WorkflowExecutorState.dispatched, "dispatch-task-to-target-module"
            reasons.append("Task lease, worker, timer, acknowledgement and checkpoint passed all gates")

        dispatchable = state in {WorkflowExecutorState.task_ready, WorkflowExecutorState.dispatched}
        task_score = 100 if task_safe else 0
        worker_score = 100 if worker_safe and queue_safe and execution_safe else 0
        lease_score = 100 if lease_safe and heartbeat_safe else 0
        timer_score = 100 if timer_safe and o.timer_due else 0
        recovery_score = 100 if not recovery_needed or recoverable else 0
        confidence = round((task_score + worker_score + lease_score + timer_score + recovery_score) / 5)
        record = WorkflowExecutorAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            workflow_instance_id=payload.workflow_instance_id,
            task_id=payload.task_id,
            step_id=payload.step_id,
            worker_id=payload.worker_id,
            queue_name=payload.queue_name,
            state=state,
            dispatchable=dispatchable,
            recoverable=recoverable,
            target_module=payload.target_module if dispatchable else None,
            recommended_action=action,
            scores=WorkflowExecutorScores(
                task_durability=task_score,
                worker_readiness=worker_score,
                lease_integrity=lease_score,
                timer_reliability=timer_score,
                recovery_readiness=recovery_score,
                executor_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._task_ids.add(task_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, task_id=payload.task_id, actor_id=payload.actor_id, action=action))
        return record

    def list_assessments(self, workspace_id: str) -> list[WorkflowExecutorAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> WorkflowExecutorAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> WorkflowExecutorStatusResponse:
        records = self.list_assessments(workspace_id)
        return WorkflowExecutorStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            dispatched=sum(record.state == WorkflowExecutorState.dispatched for record in records),
            waiting_or_retrying=sum(record.state in {WorkflowExecutorState.waiting_timer, WorkflowExecutorState.retry_scheduled, WorkflowExecutorState.task_ready} for record in records),
            recovery_required=sum(record.state == WorkflowExecutorState.recovery_required for record in records),
            latest_state=records[-1].state if records else None,
        )


executive_workflow_executor_runtime_service = ExecutiveWorkflowExecutorRuntimeService()
