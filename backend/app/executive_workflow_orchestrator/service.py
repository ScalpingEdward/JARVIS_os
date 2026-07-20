from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    StepKind,
    StepState,
    WorkflowAssessment,
    WorkflowAssessmentCreate,
    WorkflowScores,
    WorkflowState,
    WorkflowStatusResponse,
)


class ExecutiveWorkflowOrchestratorService:
    def __init__(self) -> None:
        self._records: dict[UUID, WorkflowAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._workflow_instances: set[tuple[str, UUID]] = set()
        self._workflow_versions: set[tuple[str, str, int]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: WorkflowAssessmentCreate) -> WorkflowAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        instance_key = (payload.workspace_id, payload.workflow_instance_id)
        definition_key = (
            payload.workspace_id,
            payload.definition.workflow_key,
            payload.definition.version,
        )
        if source_key in self._source_keys:
            raise ValueError("Duplicate workflow source key")
        if instance_key in self._workflow_instances:
            raise ValueError("Duplicate workflow instance")

        definition = payload.definition
        observation = payload.observation
        policy = payload.policy
        reasons: list[str] = []
        step_observations = {item.step_id: item for item in observation.steps}
        step_definitions = {item.step_id: item for item in definition.steps}

        graph_safe = (
            observation.definition_validated
            and observation.graph_acyclic
            and len(definition.steps) <= policy.maximum_steps
        )
        context_safe = not policy.require_persisted_context or observation.context_persisted
        workflow_checkpoint_safe = (
            not policy.require_workflow_checkpoint
            or observation.workflow_checkpoint_persisted
        )

        completed_ids = {
            step_id
            for step_id, item in step_observations.items()
            if item.state in {StepState.succeeded, StepState.compensated, StepState.skipped}
        }
        failed_ids = {
            step_id
            for step_id, item in step_observations.items()
            if item.state == StepState.failed
        }
        running_ids = {
            step_id
            for step_id, item in step_observations.items()
            if item.state in {StepState.running, StepState.retrying}
        }

        executable: list[str] = []
        blocked: list[str] = []
        approval_blocked: list[str] = []
        retry_exhausted: list[str] = []
        timeout_failed: list[str] = []

        for step in definition.steps:
            item = step_observations.get(step.step_id)
            state = item.state if item else StepState.pending
            attempts = item.attempts if item else 0
            elapsed = item.elapsed_seconds if item else 0
            approved = item.approval_granted if item else False
            dependencies_complete = all(dependency in completed_ids for dependency in step.depends_on)
            condition_matches = True
            if step.kind == StepKind.condition and step.condition_key:
                observed = payload.execution_context.get(step.condition_key)
                condition_matches = str(observed) == str(step.condition_expected)

            approval_required = step.requires_human_approval or step.kind == StepKind.approval
            approval_ok = (
                not approval_required
                or not policy.require_human_approval_for_approval_steps
                or approved
            )
            checkpoint_ok = (
                not policy.require_step_checkpoints
                or state not in {StepState.succeeded, StepState.compensated}
                or bool(item and item.checkpoint_persisted)
            )

            if attempts >= step.maximum_attempts and state not in {
                StepState.succeeded,
                StepState.compensated,
                StepState.skipped,
            }:
                retry_exhausted.append(step.step_id)
            if elapsed > step.timeout_seconds and state not in {
                StepState.succeeded,
                StepState.compensated,
                StepState.skipped,
            }:
                timeout_failed.append(step.step_id)
            if approval_required and not approval_ok:
                approval_blocked.append(step.step_id)
            if not checkpoint_ok:
                blocked.append(step.step_id)
            elif (
                state in {StepState.pending, StepState.ready, StepState.waiting_approval, StepState.retrying}
                and dependencies_complete
                and condition_matches
                and approval_ok
                and step.step_id not in retry_exhausted
                and step.step_id not in timeout_failed
            ):
                executable.append(step.step_id)
            elif state not in {
                StepState.succeeded,
                StepState.compensated,
                StepState.skipped,
                StepState.running,
            }:
                blocked.append(step.step_id)

        executable = list(dict.fromkeys(executable))
        blocked = list(dict.fromkeys(blocked + approval_blocked + retry_exhausted + timeout_failed))
        parallel_safe = len(executable) <= policy.maximum_parallel_steps

        mutating_completed = [
            step
            for step in definition.steps
            if step.step_id in completed_ids and step.compensation_required
        ]
        compensation_steps = [
            step.step_id
            for step in reversed(mutating_completed)
            if step.compensation_module
        ]
        compensation_contract_complete = all(step.compensation_module for step in mutating_completed)
        compensation_complete = all(
            step_observations.get(step.step_id)
            and step_observations[step.step_id].compensation_completed
            for step in mutating_completed
        )
        compensation_needed = bool(
            observation.compensation_requested
            or failed_ids
            or timeout_failed
            or retry_exhausted
        ) and bool(mutating_completed)

        all_terminal_success = all(
            step.step_id in completed_ids
            or (
                step.kind == StepKind.condition
                and step.condition_key
                and str(payload.execution_context.get(step.condition_key))
                != str(step.condition_expected)
            )
            for step in definition.steps
        )

        if not payload.risk_brain_clear:
            state, action = WorkflowState.blocked, "block-workflow-execution"
            reasons.append("Risk Brain blocks workflow orchestration")
        elif payload.sql_outbox_runtime_state not in {"runtime-ready", "dispatched"}:
            state, action = WorkflowState.blocked, "complete-sql-outbox-runtime-governance"
            reasons.append("SQL outbox runtime has not authorized workflow execution")
        elif not graph_safe:
            state, action = WorkflowState.blocked, "repair-workflow-dag"
            reasons.append("Workflow definition is invalid, cyclic or exceeds step policy")
        elif not context_safe or not workflow_checkpoint_safe:
            state, action = WorkflowState.blocked, "persist-workflow-context-and-checkpoint"
            reasons.append("Workflow context or workflow checkpoint is not persisted")
        elif not parallel_safe:
            state, action = WorkflowState.blocked, "reduce-parallel-workflow-width"
            reasons.append("Executable parallel step count exceeds policy")
        elif observation.cancellation_requested:
            if policy.allow_cancellation:
                state, action = WorkflowState.cancelled, "accept-workflow-cancellation"
                reasons.append("Workflow cancellation was requested")
            else:
                state, action = WorkflowState.blocked, "reject-workflow-cancellation"
                reasons.append("Workflow cancellation is disabled by policy")
        elif observation.pause_requested:
            if policy.allow_pause_resume:
                state, action = WorkflowState.paused, "pause-workflow"
                reasons.append("Workflow pause was requested")
            else:
                state, action = WorkflowState.blocked, "reject-workflow-pause"
                reasons.append("Workflow pause is disabled by policy")
        elif compensation_needed:
            if not policy.allow_compensation:
                state, action = WorkflowState.failed, "escalate-workflow-failure"
                reasons.append("Compensation is required but disabled")
            elif policy.require_compensation_for_completed_mutations and not compensation_contract_complete:
                state, action = WorkflowState.failed, "repair-compensation-contract"
                reasons.append("Completed mutating steps lack compensation handlers")
            elif compensation_complete and observation.rollback_chain_verified:
                state, action = WorkflowState.rolled_back, "accept-workflow-rollback"
                reasons.append("Workflow compensation and rollback chain completed")
            else:
                state, action = WorkflowState.compensating, "execute-reverse-compensation-chain"
                reasons.append("Workflow requires Saga compensation")
        elif retry_exhausted or timeout_failed:
            state, action = WorkflowState.failed, "escalate-terminal-step-failure"
            reasons.append("A workflow step exhausted retries or exceeded timeout")
        elif all_terminal_success:
            state, action = WorkflowState.completed, "complete-workflow"
            reasons.append("All workflow branches completed successfully")
        elif running_ids:
            state, action = WorkflowState.running, "continue-running-workflow"
            reasons.append("Workflow has active running steps")
        elif executable:
            state, action = WorkflowState.running, "dispatch-ready-workflow-steps"
            reasons.append("Dependency, condition and approval gates produced executable steps")
        elif approval_blocked:
            state, action = WorkflowState.waiting, "request-human-step-approval"
            reasons.append("Workflow is waiting for explicit human approval")
        elif observation.resume_requested and policy.allow_pause_resume:
            state, action = WorkflowState.running, "resume-workflow-from-checkpoint"
            reasons.append("Workflow resume was authorized from persisted checkpoint")
        else:
            state, action = WorkflowState.waiting, "wait-for-step-dependencies"
            reasons.append("Workflow is waiting for dependencies or external results")

        dispatchable = state == WorkflowState.running and bool(executable)
        graph_score = 100 if graph_safe else 0
        readiness_score = 100 if executable or all_terminal_success else 0
        checkpoint_score = 100 if context_safe and workflow_checkpoint_safe and not blocked else 0
        approval_score = 100 if not approval_blocked else 0
        compensation_score = 100 if not mutating_completed or compensation_contract_complete else 0
        confidence = round(
            (
                graph_score
                + readiness_score
                + checkpoint_score
                + approval_score
                + compensation_score
            )
            / 5
        )

        record = WorkflowAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            workflow_instance_id=payload.workflow_instance_id,
            workflow_key=definition.workflow_key,
            workflow_version=definition.version,
            state=state,
            dispatchable=dispatchable,
            executable_step_ids=executable,
            blocked_step_ids=blocked,
            compensation_step_ids=compensation_steps,
            recommended_action=action,
            scores=WorkflowScores(
                graph_integrity=graph_score,
                step_readiness=readiness_score,
                checkpoint_quality=checkpoint_score,
                approval_safety=approval_score,
                compensation_readiness=compensation_score,
                orchestration_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._workflow_instances.add(instance_key)
        self._workflow_versions.add(definition_key)
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                assessment_id=record.id,
                workflow_instance_id=payload.workflow_instance_id,
                actor_id=payload.actor_id,
                action=action,
            )
        )
        return record

    def list_assessments(self, workspace_id: str) -> list[WorkflowAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> WorkflowAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> WorkflowStatusResponse:
        records = self.list_assessments(workspace_id)
        return WorkflowStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            running=sum(record.state == WorkflowState.running for record in records),
            completed=sum(record.state == WorkflowState.completed for record in records),
            failed_or_rolled_back=sum(
                record.state in {WorkflowState.failed, WorkflowState.rolled_back}
                for record in records
            ),
            latest_state=records[-1].state if records else None,
        )


executive_workflow_orchestrator_service = ExecutiveWorkflowOrchestratorService()
