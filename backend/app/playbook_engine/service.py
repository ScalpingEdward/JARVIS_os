from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ActorAction,
    DryRunCreate,
    DryRunRecord,
    ExecutionState,
    PlaybookCreate,
    PlaybookEngineStatus,
    PlaybookMetrics,
    PlaybookRecord,
    PlaybookState,
    StepSimulation,
    StepState,
    StepType,
)


class PlaybookEngineService:
    def __init__(self) -> None:
        self.playbooks: dict[UUID, PlaybookRecord] = {}
        self.dry_runs: dict[UUID, DryRunRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> PlaybookEngineStatus:
        return PlaybookEngineStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id),
            "created_at": datetime.now(timezone.utc),
        })

    def create(self, payload: PlaybookCreate) -> PlaybookRecord:
        if any(item.workspace_id == payload.workspace_id and item.key == payload.key for item in self.playbooks.values()):
            raise ValueError("playbook key already exists in workspace")
        item = PlaybookRecord(**payload.model_dump())
        self.playbooks[item.id] = item
        self._audit(item.workspace_id, "playbook.created", item.owner_id, item.id)
        return item

    def get(self, playbook_id: UUID, workspace_id: str) -> PlaybookRecord | None:
        item = self.playbooks.get(playbook_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_all(self, workspace_id: str) -> list[PlaybookRecord]:
        return sorted(
            [item for item in self.playbooks.values() if item.workspace_id == workspace_id],
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def submit_review(self, playbook_id: UUID, workspace_id: str, action: ActorAction) -> PlaybookRecord:
        item = self._require(playbook_id, workspace_id)
        if item.owner_id != action.actor_id:
            raise ValueError("only the owner can submit a playbook for review")
        if item.state != PlaybookState.DRAFT:
            raise ValueError("only draft playbooks can enter review")
        item.state = PlaybookState.REVIEW
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "playbook.review-requested", action.actor_id, item.id)
        return item

    def approve(self, playbook_id: UUID, workspace_id: str, action: ActorAction) -> PlaybookRecord:
        item = self._require(playbook_id, workspace_id)
        if item.state not in {PlaybookState.REVIEW, PlaybookState.APPROVED}:
            raise ValueError("playbook is not in review")
        if action.actor_id == item.owner_id:
            raise ValueError("owners cannot approve their own playbooks")
        if action.actor_id in item.approved_by:
            raise ValueError("reviewer already approved this playbook")
        item.reviewers.append(action.actor_id)
        item.approved_by.append(action.actor_id)
        if len(item.approved_by) >= item.required_approvals:
            item.state = PlaybookState.APPROVED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "playbook.approved", action.actor_id, item.id)
        return item

    def publish(self, playbook_id: UUID, workspace_id: str, action: ActorAction) -> PlaybookRecord:
        item = self._require(playbook_id, workspace_id)
        if item.state != PlaybookState.APPROVED:
            raise ValueError("only approved playbooks can be published")
        if action.actor_id == item.owner_id:
            raise ValueError("owners cannot publish their own playbooks")
        item.state = PlaybookState.PUBLISHED
        item.published_by = action.actor_id
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "playbook.published", action.actor_id, item.id)
        return item

    def retire(self, playbook_id: UUID, workspace_id: str, action: ActorAction) -> PlaybookRecord:
        item = self._require(playbook_id, workspace_id)
        if action.actor_id not in {item.owner_id, item.published_by}:
            raise ValueError("actor cannot retire this playbook")
        item.state = PlaybookState.RETIRED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "playbook.retired", action.actor_id, item.id)
        return item

    def dry_run(self, playbook_id: UUID, payload: DryRunCreate) -> DryRunRecord:
        item = self._require(playbook_id, payload.workspace_id)
        if item.state != PlaybookState.PUBLISHED:
            raise ValueError("only published playbooks can be simulated")
        simulations: list[StepSimulation] = []
        waiting = False
        for step in item.steps:
            if step.step_type == StepType.HUMAN_APPROVAL or step.requires_human_approval:
                simulations.append(StepSimulation(
                    step_key=step.key,
                    state=StepState.WAITING_APPROVAL,
                    message="Human approval gate reached; no action executed.",
                ))
                waiting = True
            else:
                simulations.append(StepSimulation(
                    step_key=step.key,
                    state=StepState.SIMULATED,
                    message="Step validated in dry-run mode; no action executed.",
                ))
        run = DryRunRecord(
            playbook_id=item.id,
            playbook_version=item.version,
            workspace_id=item.workspace_id,
            requester_id=payload.requester_id,
            state=ExecutionState.WAITING_APPROVAL if waiting else ExecutionState.COMPLETED,
            input_data=payload.input_data,
            steps=simulations,
            completed_at=None if waiting else datetime.now(timezone.utc),
        )
        self.dry_runs[run.id] = run
        self._audit(item.workspace_id, "playbook.dry-run-created", payload.requester_id, run.id)
        return run

    def list_dry_runs(self, workspace_id: str) -> list[DryRunRecord]:
        return sorted(
            [item for item in self.dry_runs.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def metrics(self, workspace_id: str) -> PlaybookMetrics:
        playbooks = self.list_all(workspace_id)
        runs = self.list_dry_runs(workspace_id)
        return PlaybookMetrics(
            workspace_id=workspace_id,
            total_playbooks=len(playbooks),
            published_playbooks=sum(item.state == PlaybookState.PUBLISHED for item in playbooks),
            total_dry_runs=len(runs),
            waiting_approval_steps=sum(
                step.state == StepState.WAITING_APPROVAL for run in runs for step in run.steps
            ),
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [item for item in self.audit if item["workspace_id"] == workspace_id]

    def _require(self, playbook_id: UUID, workspace_id: str) -> PlaybookRecord:
        item = self.get(playbook_id, workspace_id)
        if item is None:
            raise KeyError("playbook not found")
        return item


playbook_engine_service = PlaybookEngineService()
