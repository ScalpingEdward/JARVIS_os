from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    BackupPolicyCreate, BackupPolicyRecord, BackupRecoveryStatus, ExerciseCreate,
    ExerciseRecord, ExerciseResult, MetricsRecord, Mutation, PlanState,
    PolicyApprovalCreate, PolicyApprovalRecord, PolicyState, RecoveryPlanCreate,
    RecoveryPlanRecord,
)
from .service import backup_recovery_service as service

router = APIRouter(prefix="/v1/backup-recovery", tags=["backup-recovery"])


@router.get("/status", response_model=BackupRecoveryStatus)
def get_status() -> BackupRecoveryStatus:
    return service.status()


@router.post("/policies", response_model=BackupPolicyRecord, status_code=status.HTTP_201_CREATED)
def create_policy(payload: BackupPolicyCreate) -> BackupPolicyRecord:
    try:
        return service.create_policy(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/policies", response_model=list[BackupPolicyRecord])
def list_policies(workspace_id: str = Query(min_length=1, max_length=120), state: PolicyState | None = None) -> list[BackupPolicyRecord]:
    return service.list_policies(workspace_id, state)


@router.get("/policies/{policy_id}", response_model=BackupPolicyRecord)
def get_policy(policy_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> BackupPolicyRecord:
    item = service.get_policy(policy_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Backup policy not found")
    return item


def _set_policy(policy_id: UUID, workspace_id: str, payload: Mutation, target: PolicyState) -> BackupPolicyRecord:
    try:
        item = service.set_policy_state(policy_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned backup policy not found")
    return item


@router.post("/policies/{policy_id}/review", response_model=BackupPolicyRecord)
def review_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> BackupPolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.REVIEW)


@router.post("/policy-approvals", response_model=PolicyApprovalRecord, status_code=status.HTTP_201_CREATED)
def approve_policy(payload: PolicyApprovalCreate) -> PolicyApprovalRecord:
    try:
        return service.approve_policy(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/policies/{policy_id}/approve", response_model=BackupPolicyRecord)
def approve_policy_state(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> BackupPolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.APPROVED)


@router.post("/policies/{policy_id}/activate", response_model=BackupPolicyRecord)
def activate_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> BackupPolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.ACTIVE)


@router.post("/policies/{policy_id}/pause", response_model=BackupPolicyRecord)
def pause_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> BackupPolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.PAUSED)


@router.post("/policies/{policy_id}/retire", response_model=BackupPolicyRecord)
def retire_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> BackupPolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.RETIRED)


@router.post("/plans", response_model=RecoveryPlanRecord, status_code=status.HTTP_201_CREATED)
def create_plan(payload: RecoveryPlanCreate) -> RecoveryPlanRecord:
    try:
        return service.create_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/plans", response_model=list[RecoveryPlanRecord])
def list_plans(workspace_id: str = Query(min_length=1, max_length=120), state: PlanState | None = None) -> list[RecoveryPlanRecord]:
    return service.list_plans(workspace_id, state)


@router.get("/plans/{plan_id}", response_model=RecoveryPlanRecord)
def get_plan(plan_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> RecoveryPlanRecord:
    item = service.get_plan(plan_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Recovery plan not found")
    return item


@router.post("/plans/{plan_id}/review", response_model=RecoveryPlanRecord)
def review_plan(plan_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RecoveryPlanRecord:
    try:
        item = service.review_plan(plan_id, workspace_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Recovery plan not found")
    return item


def _set_plan(plan_id: UUID, workspace_id: str, payload: Mutation, target: PlanState) -> RecoveryPlanRecord:
    try:
        item = service.set_plan_state(plan_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned recovery plan not found")
    return item


@router.post("/plans/{plan_id}/approve", response_model=RecoveryPlanRecord)
def approve_plan(plan_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RecoveryPlanRecord:
    return _set_plan(plan_id, workspace_id, payload, PlanState.APPROVED)


@router.post("/plans/{plan_id}/publish", response_model=RecoveryPlanRecord)
def publish_plan(plan_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RecoveryPlanRecord:
    return _set_plan(plan_id, workspace_id, payload, PlanState.PUBLISHED)


@router.post("/plans/{plan_id}/retire", response_model=RecoveryPlanRecord)
def retire_plan(plan_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RecoveryPlanRecord:
    return _set_plan(plan_id, workspace_id, payload, PlanState.RETIRED)


@router.post("/exercises", response_model=ExerciseRecord, status_code=status.HTTP_201_CREATED)
def create_exercise(payload: ExerciseCreate) -> ExerciseRecord:
    try:
        return service.create_exercise(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/exercises", response_model=list[ExerciseRecord])
def list_exercises(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ExerciseRecord]:
    return service.list_exercises(workspace_id)


@router.post("/exercises/{exercise_id}/start", response_model=ExerciseRecord)
def start_exercise(exercise_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ExerciseRecord:
    try:
        item = service.start_exercise(exercise_id, workspace_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned recovery exercise not found")
    return item


@router.post("/exercises/{exercise_id}/complete", response_model=ExerciseRecord)
def complete_exercise(exercise_id: UUID, payload: ExerciseResult, workspace_id: str = Query(min_length=1, max_length=120)) -> ExerciseRecord:
    try:
        item = service.complete_exercise(exercise_id, workspace_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned recovery exercise not found")
    return item


@router.post("/exercises/{exercise_id}/cancel", response_model=ExerciseRecord)
def cancel_exercise(exercise_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ExerciseRecord:
    try:
        item = service.cancel_exercise(exercise_id, workspace_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned recovery exercise not found")
    return item


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
