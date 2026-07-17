from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalCreate, ApprovalRecord, AuditRecord, MetricsRecord, Mutation, RunbookCreate,
    RunbookRecord, RunbookState, RunbookStatus, RunCreate, RunRecord, RunState,
    StepResultCreate, StepResultRecord, StepState,
)


class RunbookService:
    def __init__(self) -> None:
        self.runbooks: dict[UUID, RunbookRecord] = {}
        self.approvals: dict[UUID, ApprovalRecord] = {}
        self.runs: dict[UUID, RunRecord] = {}
        self.step_results: dict[UUID, StepResultRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details))

    def status(self) -> RunbookStatus:
        return RunbookStatus(runbooks=len(self.runbooks), runs=len(self.runs), step_results=len(self.step_results))

    def create_runbook(self, payload: RunbookCreate) -> RunbookRecord:
        if any(item.workspace_id == payload.workspace_id and item.runbook_key == payload.runbook_key and item.state != RunbookState.RETIRED for item in self.runbooks.values()):
            raise ValueError("active runbook key already exists")
        data = payload.model_dump(exclude={"human_approved", "automatic_publish", "execute_steps", "external_runner"})
        item = RunbookRecord(**data)
        self.runbooks[item.id] = item
        self._audit(item.workspace_id, "runbook.created", "runbook", item.id, item.owner_id)
        return item

    def list_runbooks(self, workspace_id: str, state: RunbookState | None = None) -> list[RunbookRecord]:
        return [item for item in self.runbooks.values() if item.workspace_id == workspace_id and (state is None or item.state == state)]

    def get_runbook(self, runbook_id: UUID, workspace_id: str) -> RunbookRecord | None:
        item = self.runbooks.get(runbook_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_state(self, runbook_id: UUID, workspace_id: str, payload: Mutation, state: RunbookState) -> RunbookRecord | None:
        item = self.runbooks.get(runbook_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        allowed = {
            RunbookState.REVIEW: {RunbookState.DRAFT},
            RunbookState.PUBLISHED: {RunbookState.APPROVED},
            RunbookState.RETIRED: {RunbookState.PUBLISHED, RunbookState.APPROVED},
        }
        if state not in allowed or item.state not in allowed[state]:
            raise ValueError("invalid runbook state transition")
        if state == RunbookState.PUBLISHED and item.approval_count < item.required_approvals:
            raise ValueError("required runbook approvals are missing")
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"runbook.{state.value}", "runbook", item.id, payload.requester_id, reason=payload.reason)
        return item

    def approve(self, payload: ApprovalCreate) -> ApprovalRecord:
        item = self.runbooks.get(payload.runbook_id)
        if not item or item.workspace_id != payload.workspace_id:
            raise ValueError("runbook not found")
        if item.state != RunbookState.REVIEW:
            raise ValueError("runbook is not in review")
        if item.owner_id == payload.requester_id:
            raise ValueError("runbook owner cannot self-approve")
        if any(record.runbook_id == item.id and record.requester_id == payload.requester_id for record in self.approvals.values()):
            raise ValueError("reviewer already approved this runbook")
        data = payload.model_dump(exclude={"human_approved", "automatic_decision"})
        record = ApprovalRecord(**data)
        self.approvals[record.id] = record
        item.approval_count += 1
        if item.approval_count >= item.required_approvals:
            item.state = RunbookState.APPROVED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(item.workspace_id, "runbook.approved", "runbook", item.id, payload.requester_id, approval_count=item.approval_count)
        return record

    def create_run(self, payload: RunCreate) -> RunRecord:
        item = self.runbooks.get(payload.runbook_id)
        if not item or item.workspace_id != payload.workspace_id:
            raise ValueError("runbook not found")
        if item.state != RunbookState.PUBLISHED:
            raise ValueError("only published runbooks can create runs")
        data = payload.model_dump(exclude={"human_approved", "execute_steps"})
        run = RunRecord(**data, runbook_version=item.version)
        self.runs[run.id] = run
        self._audit(run.workspace_id, "run.planned", "run", run.id, payload.requester_id, dry_run=run.dry_run)
        return run

    def set_run_state(self, run_id: UUID, workspace_id: str, payload: Mutation, state: RunState) -> RunRecord | None:
        run = self.runs.get(run_id)
        if not run or run.workspace_id != workspace_id or run.operator_id != payload.requester_id:
            return None
        allowed = {
            RunState.IN_PROGRESS: {RunState.PLANNED, RunState.BLOCKED},
            RunState.CANCELLED: {RunState.PLANNED, RunState.IN_PROGRESS, RunState.BLOCKED},
        }
        if state not in allowed or run.state not in allowed[state]:
            raise ValueError("invalid run state transition")
        run.state = state
        run.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"run.{state.value}", "run", run.id, payload.requester_id, reason=payload.reason)
        return run

    def record_step(self, payload: StepResultCreate) -> StepResultRecord:
        run = self.runs.get(payload.run_id)
        if not run or run.workspace_id != payload.workspace_id:
            raise ValueError("run not found")
        if run.operator_id != payload.requester_id:
            raise ValueError("only the assigned operator can record step results")
        if run.state != RunState.IN_PROGRESS:
            raise ValueError("run is not in progress")
        runbook = self.runbooks[run.runbook_id]
        step_map = {step.step_key: step for step in runbook.steps}
        step = step_map.get(payload.step_key)
        if step is None:
            raise ValueError("runbook step not found")
        if any(result.run_id == run.id and result.step_key == payload.step_key for result in self.step_results.values()):
            raise ValueError("step result already recorded")
        if payload.state == StepState.COMPLETED and step.required_evidence and not payload.evidence_references:
            raise ValueError("required step evidence is missing")
        if payload.state == StepState.SKIPPED and not step.optional:
            raise ValueError("required step cannot be skipped")
        data = payload.model_dump(exclude={"human_approved"})
        result = StepResultRecord(**data)
        self.step_results[result.id] = result
        ordered = runbook.steps
        completed_keys = {record.step_key for record in self.step_results.values() if record.run_id == run.id and record.state in {StepState.COMPLETED, StepState.SKIPPED}}
        failed = any(record.run_id == run.id and record.state == StepState.FAILED for record in self.step_results.values())
        if failed:
            run.state = RunState.FAILED
        elif all(step_item.step_key in completed_keys for step_item in ordered):
            run.state = RunState.COMPLETED
            run.current_step_index = len(ordered)
        else:
            for index, step_item in enumerate(ordered):
                if step_item.step_key not in completed_keys:
                    run.current_step_index = index
                    break
        run.updated_at = datetime.now(timezone.utc)
        self._audit(run.workspace_id, f"step.{payload.state.value}", "run", run.id, payload.requester_id, step_key=payload.step_key)
        return result

    def list_runs(self, workspace_id: str, runbook_id: UUID | None = None) -> list[RunRecord]:
        return [run for run in self.runs.values() if run.workspace_id == workspace_id and (runbook_id is None or run.runbook_id == runbook_id)]

    def list_step_results(self, workspace_id: str, run_id: UUID) -> list[StepResultRecord]:
        return [item for item in self.step_results.values() if item.workspace_id == workspace_id and item.run_id == run_id]

    def metrics(self, workspace_id: str) -> MetricsRecord:
        runbooks = [item for item in self.runbooks.values() if item.workspace_id == workspace_id]
        runs = [item for item in self.runs.values() if item.workspace_id == workspace_id]
        return MetricsRecord(
            workspace_id=workspace_id,
            runbooks=len(runbooks),
            published_runbooks=sum(item.state == RunbookState.PUBLISHED for item in runbooks),
            active_runs=sum(item.state in {RunState.PLANNED, RunState.IN_PROGRESS} for item in runs),
            completed_runs=sum(item.state == RunState.COMPLETED for item in runs),
            failed_runs=sum(item.state == RunState.FAILED for item in runs),
            blocked_runs=sum(item.state == RunState.BLOCKED for item in runs),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


runbook_service = RunbookService()
