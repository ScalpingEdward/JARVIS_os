from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.backup_recovery.models import (
    BackupKind, BackupPolicyCreate, ExerciseCreate, ExerciseResult, ExerciseState,
    Mutation, PlanState, PolicyApprovalCreate, PolicyState, RecoveryPlanCreate,
    RecoveryStep,
)
from app.backup_recovery.service import BackupRecoveryService


def policy(workspace: str = "ws", owner: str = "owner", key: str = "daily-db") -> BackupPolicyCreate:
    return BackupPolicyCreate(
        workspace_id=workspace,
        owner_id=owner,
        policy_key=key,
        name="Daily database backup",
        backup_kind=BackupKind.FULL,
        source_asset_ids=[uuid4()],
        storage_asset_id=uuid4(),
        schedule_expression="0 2 * * *",
        retention_days=30,
        rpo_minutes=60,
        rto_minutes=120,
    )


def test_policy_lifecycle_requires_independent_approval() -> None:
    service = BackupRecoveryService()
    item = service.create_policy(policy())
    owner = Mutation(requester_id="owner")
    assert service.set_policy_state(item.id, "ws", owner, PolicyState.REVIEW).state == PolicyState.REVIEW
    with pytest.raises(ValueError):
        service.approve_policy(PolicyApprovalCreate(workspace_id="ws", requester_id="owner", policy_id=item.id))
    service.approve_policy(PolicyApprovalCreate(workspace_id="ws", requester_id="reviewer", policy_id=item.id))
    assert service.set_policy_state(item.id, "ws", owner, PolicyState.APPROVED).state == PolicyState.APPROVED
    assert service.set_policy_state(item.id, "ws", owner, PolicyState.ACTIVE).state == PolicyState.ACTIVE


def test_recovery_plan_and_exercise_flow() -> None:
    service = BackupRecoveryService()
    backup = service.create_policy(policy())
    plan = service.create_plan(RecoveryPlanCreate(
        workspace_id="ws",
        owner_id="owner",
        plan_key="primary-recovery",
        name="Primary recovery",
        covered_asset_ids=[uuid4()],
        policy_ids=[backup.id],
        steps=[RecoveryStep(order=1, title="Validate backup", responsible_role="operator")],
        activation_criteria="Primary service unavailable",
    ))
    assert service.review_plan(plan.id, "ws", Mutation(requester_id="owner")).state == PlanState.REVIEW
    service.review_plan(plan.id, "ws", Mutation(requester_id="reviewer"))
    assert service.set_plan_state(plan.id, "ws", Mutation(requester_id="owner"), PlanState.APPROVED).state == PlanState.APPROVED
    assert service.set_plan_state(plan.id, "ws", Mutation(requester_id="owner"), PlanState.PUBLISHED).state == PlanState.PUBLISHED
    exercise = service.create_exercise(ExerciseCreate(
        workspace_id="ws",
        owner_id="owner",
        recovery_plan_id=plan.id,
        scheduled_at=datetime.now(timezone.utc),
        scenario="Database loss simulation",
    ))
    service.start_exercise(exercise.id, "ws", Mutation(requester_id="owner"))
    completed = service.complete_exercise(exercise.id, "ws", ExerciseResult(
        requester_id="owner",
        passed=True,
        achieved_rpo_minutes=20,
        achieved_rto_minutes=45,
        evidence_references=["evidence://restore-test/1"],
    ))
    assert completed.state == ExerciseState.PASSED
    assert service.metrics("ws").passed_exercises == 1


def test_workspace_isolation_and_duplicate_keys() -> None:
    service = BackupRecoveryService()
    first = service.create_policy(policy("a", key="shared"))
    service.create_policy(policy("b", key="shared"))
    assert service.get_policy(first.id, "b") is None
    with pytest.raises(ValueError):
        service.create_policy(policy("a", key="shared"))


def test_safety_controls() -> None:
    payload = policy()
    with pytest.raises(ValueError):
        BackupPolicyCreate.model_validate(payload.model_dump() | {"execute_backup": True})
    with pytest.raises(ValueError):
        BackupPolicyCreate.model_validate(payload.model_dump() | {"external_provider": True})
    with pytest.raises(ValueError):
        ExerciseCreate(
            workspace_id="ws",
            owner_id="owner",
            recovery_plan_id=uuid4(),
            scheduled_at=datetime.now(timezone.utc),
            scenario="unsafe",
            execute_restore=True,
        )
