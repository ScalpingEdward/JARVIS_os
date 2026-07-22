from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List

from .models import (
    AuditEvent,
    OrchestrationAction,
    OrchestrationCommand,
    OrchestrationCreate,
    OrchestrationPlan,
    OrchestrationRecord,
    OrchestrationState,
    WorkflowStep,
)


class OrchestrationError(ValueError):
    pass


class GovernedOrchestrationService:
    def __init__(self) -> None:
        self._records: Dict[str, OrchestrationRecord] = {}
        self._audit: List[AuditEvent] = []
        self._source_keys: Dict[str, set[str]] = defaultdict(set)
        self._approval_tokens: set[str] = set()
        self._dispatch_receipts: set[str] = set()
        self._completion_receipts: set[str] = set()
        self._lock = RLock()

    def create(self, payload: OrchestrationCreate, actor: str = "system") -> OrchestrationRecord:
        with self._lock:
            if payload.source_key in self._source_keys[payload.workspace_id]:
                raise OrchestrationError("duplicate source_key in workspace")

            if payload.risk_brain_blocked:
                state = OrchestrationState.BLOCKED
                plan = None
            elif not payload.upstream_evidence_verified or not payload.active_policy_verified:
                state = OrchestrationState.EVIDENCE_REQUIRED
                plan = None
            else:
                plan = self._build_plan(payload.steps, payload.max_parallel_steps)
                state = OrchestrationState.HUMAN_REVIEW_REQUIRED

            record = OrchestrationRecord(
                workspace_id=payload.workspace_id,
                source_key=payload.source_key,
                strategy_policy_record_id=payload.strategy_policy_record_id,
                workflow_name=payload.workflow_name,
                steps=payload.steps,
                max_parallel_steps=payload.max_parallel_steps,
                state=state,
                plan=plan,
            )
            self._records[record.id] = record
            self._source_keys[payload.workspace_id].add(payload.source_key)
            self._append_audit(record, "created", actor, None, state)
            return record.model_copy(deep=True)

    def get(self, workspace_id: str, record_id: str) -> OrchestrationRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise OrchestrationError("record not found")
            return record.model_copy(deep=True)

    def list(self, workspace_id: str) -> List[OrchestrationRecord]:
        with self._lock:
            return [r.model_copy(deep=True) for r in self._records.values() if r.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> List[AuditEvent]:
        with self._lock:
            return [e.model_copy(deep=True) for e in self._audit if e.workspace_id == workspace_id]

    def act(self, workspace_id: str, record_id: str, action: OrchestrationAction) -> OrchestrationRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise OrchestrationError("record not found")

            previous = record.state
            if action.command == OrchestrationCommand.APPROVE:
                if previous != OrchestrationState.HUMAN_REVIEW_REQUIRED:
                    raise OrchestrationError("workflow is not approvable")
                if not action.approval_token:
                    raise OrchestrationError("approval token required")
                if action.approval_token in self._approval_tokens:
                    raise OrchestrationError("approval token replay detected")
                self._approval_tokens.add(action.approval_token)
                record.approval_token = action.approval_token
                record.state = OrchestrationState.APPROVED

            elif action.command == OrchestrationCommand.DISPATCH:
                if previous != OrchestrationState.APPROVED:
                    raise OrchestrationError("workflow must be approved before dispatch")
                if not action.dispatch_receipt:
                    raise OrchestrationError("dispatch receipt required")
                if action.dispatch_receipt in self._dispatch_receipts:
                    raise OrchestrationError("dispatch receipt replay detected")
                self._dispatch_receipts.add(action.dispatch_receipt)
                record.dispatch_receipt = action.dispatch_receipt
                record.state = OrchestrationState.DISPATCHED

            elif action.command == OrchestrationCommand.COMPLETE:
                if previous != OrchestrationState.DISPATCHED:
                    raise OrchestrationError("workflow must be dispatched before completion")
                if not action.completion_receipt:
                    raise OrchestrationError("completion receipt required")
                if action.completion_receipt in self._completion_receipts:
                    raise OrchestrationError("completion receipt replay detected")
                self._completion_receipts.add(action.completion_receipt)
                record.completion_receipt = action.completion_receipt
                record.state = OrchestrationState.COMPLETED

            elif action.command == OrchestrationCommand.FAIL:
                if previous != OrchestrationState.DISPATCHED:
                    raise OrchestrationError("only dispatched workflows can fail")
                record.state = OrchestrationState.FAILED
            elif action.command == OrchestrationCommand.CANCEL:
                if previous in {OrchestrationState.COMPLETED, OrchestrationState.ARCHIVED}:
                    raise OrchestrationError("terminal workflow cannot be cancelled")
                record.state = OrchestrationState.CANCELLED
            elif action.command == OrchestrationCommand.ARCHIVE:
                if previous not in {OrchestrationState.COMPLETED, OrchestrationState.FAILED, OrchestrationState.CANCELLED}:
                    raise OrchestrationError("only terminal workflows can be archived")
                record.state = OrchestrationState.ARCHIVED
            else:
                raise OrchestrationError("unsupported command")

            record.updated_at = datetime.now(timezone.utc)
            details = {"reason": action.reason} if action.reason else {}
            self._append_audit(record, action.command.value, action.actor, previous, record.state, details)
            return record.model_copy(deep=True)

    @staticmethod
    def _build_plan(steps: List[WorkflowStep], max_parallel_steps: int) -> OrchestrationPlan:
        by_id = {step.step_id: step for step in steps}
        if len(by_id) != len(steps):
            raise OrchestrationError("step_id values must be unique")

        indegree = {step.step_id: 0 for step in steps}
        children: Dict[str, List[str]] = defaultdict(list)
        for step in steps:
            for dependency in step.depends_on:
                if dependency not in by_id:
                    raise OrchestrationError(f"unknown dependency: {dependency}")
                if dependency == step.step_id:
                    raise OrchestrationError("step cannot depend on itself")
                indegree[step.step_id] += 1
                children[dependency].append(step.step_id)

        ready = deque(sorted(step_id for step_id, degree in indegree.items() if degree == 0))
        ordered: List[str] = []
        batches: List[List[str]] = []
        while ready:
            batch: List[str] = []
            for _ in range(min(max_parallel_steps, len(ready))):
                batch.append(ready.popleft())
            batches.append(batch)
            for step_id in batch:
                ordered.append(step_id)
                for child in sorted(children[step_id]):
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        ready.append(child)

        if len(ordered) != len(steps):
            raise OrchestrationError("workflow contains a dependency cycle")

        warnings: List[str] = []
        if any(step.retry_limit > 3 for step in steps):
            warnings.append("high-retry-limit")
        if sum(step.timeout_seconds for step in steps) > 3600:
            warnings.append("long-workflow-timeout")

        return OrchestrationPlan(
            ordered_step_ids=ordered,
            execution_batches=batches,
            approval_required_steps=[step.step_id for step in steps if step.requires_human_approval],
            total_timeout_seconds=sum(step.timeout_seconds for step in steps),
            warnings=warnings,
        )

    def _append_audit(
        self,
        record: OrchestrationRecord,
        action: str,
        actor: str,
        from_state: OrchestrationState | None,
        to_state: OrchestrationState,
        details: Dict[str, object] | None = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
                details=details or {},
            )
        )
