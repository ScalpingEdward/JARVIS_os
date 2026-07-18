from datetime import datetime, timezone
from uuid import UUID

from .models import (
    BackupPolicyCreate, BackupPolicyRecord, BackupRecoveryStatus, ExerciseCreate,
    ExerciseRecord, ExerciseResult, ExerciseState, MetricsRecord, Mutation,
    PlanState, PolicyApprovalCreate, PolicyApprovalRecord, PolicyState,
    RecoveryPlanCreate, RecoveryPlanRecord,
)


class BackupRecoveryService:
    def __init__(self) -> None:
        self.policies: dict[UUID, BackupPolicyRecord] = {}
        self.policy_approvals: list[PolicyApprovalRecord] = []
        self.plans: dict[UUID, RecoveryPlanRecord] = {}
        self.plan_approvals: dict[UUID, set[str]] = {}
        self.exercises: dict[UUID, ExerciseRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> BackupRecoveryStatus:
        return BackupRecoveryStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id) if entity_id else None,
            "created_at": datetime.now(timezone.utc),
        })

    def create_policy(self, payload: BackupPolicyCreate) -> BackupPolicyRecord:
        if any(item.workspace_id == payload.workspace_id and item.policy_key == payload.policy_key for item in self.policies.values()):
            raise ValueError("backup policy key already exists in workspace")
        item = BackupPolicyRecord(**payload.model_dump())
        self.policies[item.id] = item
        self._audit(item.workspace_id, "policy.created", item.owner_id, item.id)
        return item

    def get_policy(self, policy_id: UUID, workspace_id: str) -> BackupPolicyRecord | None:
        item = self.policies.get(policy_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_policies(self, workspace_id: str, state: PolicyState | None = None) -> list[BackupPolicyRecord]:
        return [item for item in self.policies.values() if item.workspace_id == workspace_id and (state is None or item.state == state)]

    def set_policy_state(self, policy_id: UUID, workspace_id: str, payload: Mutation, target: PolicyState) -> BackupPolicyRecord | None:
        item = self.get_policy(policy_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        allowed = {
            PolicyState.DRAFT: {PolicyState.REVIEW, PolicyState.RETIRED},
            PolicyState.REVIEW: {PolicyState.APPROVED, PolicyState.DRAFT, PolicyState.RETIRED},
            PolicyState.APPROVED: {PolicyState.ACTIVE, PolicyState.RETIRED},
            PolicyState.ACTIVE: {PolicyState.PAUSED, PolicyState.RETIRED},
            PolicyState.PAUSED: {PolicyState.ACTIVE, PolicyState.RETIRED},
            PolicyState.RETIRED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid backup policy transition")
        if target == PolicyState.APPROVED and item.approval_count < item.required_approvals:
            raise ValueError("required approvals are missing")
        item.state = target
        item.revision += 1
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"policy.{target.value}", payload.requester_id, item.id)
        return item

    def approve_policy(self, payload: PolicyApprovalCreate) -> PolicyApprovalRecord:
        item = self.get_policy(payload.policy_id, payload.workspace_id)
        if item is None or item.state != PolicyState.REVIEW:
            raise ValueError("backup policy is not available for review")
        if item.owner_id == payload.requester_id:
            raise ValueError("owner self-approval is blocked")
        if any(x.policy_id == payload.policy_id and x.requester_id == payload.requester_id for x in self.policy_approvals):
            raise ValueError("reviewer already approved this policy")
        approval = PolicyApprovalRecord(**payload.model_dump())
        self.policy_approvals.append(approval)
        item.approval_count += 1
        self._audit(payload.workspace_id, "policy.approved-by-reviewer", payload.requester_id, item.id)
        return approval

    def create_plan(self, payload: RecoveryPlanCreate) -> RecoveryPlanRecord:
        if any(item.workspace_id == payload.workspace_id and item.plan_key == payload.plan_key for item in self.plans.values()):
            raise ValueError("recovery plan key already exists in workspace")
        for policy_id in payload.policy_ids:
            if self.get_policy(policy_id, payload.workspace_id) is None:
                raise ValueError("referenced backup policy not found in workspace")
        item = RecoveryPlanRecord(**payload.model_dump())
        self.plans[item.id] = item
        self.plan_approvals[item.id] = set()
        self._audit(item.workspace_id, "plan.created", item.owner_id, item.id)
        return item

    def get_plan(self, plan_id: UUID, workspace_id: str) -> RecoveryPlanRecord | None:
        item = self.plans.get(plan_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_plans(self, workspace_id: str, state: PlanState | None = None) -> list[RecoveryPlanRecord]:
        return [item for item in self.plans.values() if item.workspace_id == workspace_id and (state is None or item.state == state)]

    def review_plan(self, plan_id: UUID, workspace_id: str, payload: Mutation) -> RecoveryPlanRecord | None:
        item = self.get_plan(plan_id, workspace_id)
        if item is None:
            return None
        if item.state == PlanState.DRAFT:
            if item.owner_id != payload.requester_id:
                return None
            item.state = PlanState.REVIEW
        elif item.state == PlanState.REVIEW:
            if item.owner_id == payload.requester_id:
                raise ValueError("owner self-approval is blocked")
            reviewers = self.plan_approvals.setdefault(item.id, set())
            if payload.requester_id in reviewers:
                raise ValueError("reviewer already approved this plan")
            reviewers.add(payload.requester_id)
            item.approval_count = len(reviewers)
        else:
            raise ValueError("recovery plan is not available for review")
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "plan.review", payload.requester_id, item.id)
        return item

    def set_plan_state(self, plan_id: UUID, workspace_id: str, payload: Mutation, target: PlanState) -> RecoveryPlanRecord | None:
        item = self.get_plan(plan_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        allowed = {
            PlanState.DRAFT: {PlanState.RETIRED},
            PlanState.REVIEW: {PlanState.APPROVED, PlanState.DRAFT, PlanState.RETIRED},
            PlanState.APPROVED: {PlanState.PUBLISHED, PlanState.RETIRED},
            PlanState.PUBLISHED: {PlanState.RETIRED},
            PlanState.RETIRED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid recovery plan transition")
        if target == PlanState.APPROVED and item.approval_count < item.required_approvals:
            raise ValueError("required approvals are missing")
        item.state = target
        item.revision += 1
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"plan.{target.value}", payload.requester_id, item.id)
        return item

    def create_exercise(self, payload: ExerciseCreate) -> ExerciseRecord:
        plan = self.get_plan(payload.recovery_plan_id, payload.workspace_id)
        if plan is None or plan.state != PlanState.PUBLISHED:
            raise ValueError("published recovery plan is required")
        item = ExerciseRecord(**payload.model_dump())
        self.exercises[item.id] = item
        self._audit(item.workspace_id, "exercise.planned", item.owner_id, item.id)
        return item

    def list_exercises(self, workspace_id: str) -> list[ExerciseRecord]:
        return [item for item in self.exercises.values() if item.workspace_id == workspace_id]

    def start_exercise(self, exercise_id: UUID, workspace_id: str, payload: Mutation) -> ExerciseRecord | None:
        item = self.exercises.get(exercise_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        if item.state != ExerciseState.PLANNED:
            raise ValueError("only planned exercises can start")
        item.state = ExerciseState.IN_PROGRESS
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "exercise.started", payload.requester_id, item.id)
        return item

    def complete_exercise(self, exercise_id: UUID, workspace_id: str, payload: ExerciseResult) -> ExerciseRecord | None:
        item = self.exercises.get(exercise_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        if item.state != ExerciseState.IN_PROGRESS:
            raise ValueError("only in-progress exercises can complete")
        item.state = ExerciseState.PASSED if payload.passed else ExerciseState.FAILED
        item.achieved_rpo_minutes = payload.achieved_rpo_minutes
        item.achieved_rto_minutes = payload.achieved_rto_minutes
        item.evidence_references = payload.evidence_references
        item.notes = payload.notes
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"exercise.{item.state.value}", payload.requester_id, item.id)
        return item

    def cancel_exercise(self, exercise_id: UUID, workspace_id: str, payload: Mutation) -> ExerciseRecord | None:
        item = self.exercises.get(exercise_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        if item.state not in {ExerciseState.PLANNED, ExerciseState.IN_PROGRESS}:
            raise ValueError("completed exercise cannot be cancelled")
        item.state = ExerciseState.CANCELLED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "exercise.cancelled", payload.requester_id, item.id)
        return item

    def metrics(self, workspace_id: str) -> MetricsRecord:
        policies = self.list_policies(workspace_id)
        plans = self.list_plans(workspace_id)
        exercises = self.list_exercises(workspace_id)
        return MetricsRecord(
            workspace_id=workspace_id,
            policies=len(policies),
            active_policies=sum(item.state == PolicyState.ACTIVE for item in policies),
            recovery_plans=len(plans),
            published_plans=sum(item.state == PlanState.PUBLISHED for item in plans),
            exercises=len(exercises),
            passed_exercises=sum(item.state == ExerciseState.PASSED for item in exercises),
            failed_exercises=sum(item.state == ExerciseState.FAILED for item in exercises),
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [item for item in self.audit if item["workspace_id"] == workspace_id]


backup_recovery_service = BackupRecoveryService()
