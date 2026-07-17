from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalCreate, ApprovalRecord, ConfigEntryCreate, ConfigEntryRecord, ConfigFeatureStatus,
    ConfigState, Environment, EvaluationRequest, EvaluationResult, FeatureFlagCreate,
    FeatureFlagRecord, FlagState, MetricsRecord, Mutation,
)
from .service import config_feature_service as service

router = APIRouter(prefix="/v1/config-feature-flags", tags=["config-feature-flags"])


@router.get("/status", response_model=ConfigFeatureStatus)
def get_status() -> ConfigFeatureStatus:
    return service.status()


@router.post("/flags", response_model=FeatureFlagRecord, status_code=status.HTTP_201_CREATED)
def create_flag(payload: FeatureFlagCreate) -> FeatureFlagRecord:
    try:
        return service.create_flag(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/flags", response_model=list[FeatureFlagRecord])
def list_flags(workspace_id: str = Query(min_length=1, max_length=120), state: FlagState | None = None) -> list[FeatureFlagRecord]:
    return service.list_flags(workspace_id, state)


@router.get("/flags/{flag_id}", response_model=FeatureFlagRecord)
def get_flag(flag_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> FeatureFlagRecord:
    item = service.get_flag(flag_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    return item


def _set_flag(flag_id: UUID, workspace_id: str, payload: Mutation, state: FlagState) -> FeatureFlagRecord:
    try:
        item = service.set_flag_state(flag_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned feature flag not found")
    return item


@router.post("/flags/{flag_id}/review", response_model=FeatureFlagRecord)
def review_flag(flag_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FeatureFlagRecord:
    return _set_flag(flag_id, workspace_id, payload, FlagState.REVIEW)


@router.post("/flags/approvals", response_model=ApprovalRecord, status_code=status.HTTP_201_CREATED)
def approve_flag(payload: ApprovalCreate) -> ApprovalRecord:
    try:
        return service.approve_flag(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/flags/{flag_id}/approved", response_model=FeatureFlagRecord)
def approve_state(flag_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FeatureFlagRecord:
    return _set_flag(flag_id, workspace_id, payload, FlagState.APPROVED)


@router.post("/flags/{flag_id}/activate", response_model=FeatureFlagRecord)
def activate_flag(flag_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FeatureFlagRecord:
    return _set_flag(flag_id, workspace_id, payload, FlagState.ACTIVE)


@router.post("/flags/{flag_id}/disable", response_model=FeatureFlagRecord)
def disable_flag(flag_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FeatureFlagRecord:
    return _set_flag(flag_id, workspace_id, payload, FlagState.DISABLED)


@router.post("/flags/{flag_id}/archive", response_model=FeatureFlagRecord)
def archive_flag(flag_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FeatureFlagRecord:
    return _set_flag(flag_id, workspace_id, payload, FlagState.ARCHIVED)


@router.post("/flags/evaluate", response_model=EvaluationResult)
def evaluate_flag(payload: EvaluationRequest) -> EvaluationResult:
    try:
        return service.evaluate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/configs", response_model=ConfigEntryRecord, status_code=status.HTTP_201_CREATED)
def create_config(payload: ConfigEntryCreate) -> ConfigEntryRecord:
    return service.create_config(payload)


@router.get("/configs", response_model=list[ConfigEntryRecord])
def list_configs(workspace_id: str = Query(min_length=1, max_length=120), environment: Environment | None = None) -> list[ConfigEntryRecord]:
    return service.list_configs(workspace_id, environment)


def _set_config(config_id: UUID, workspace_id: str, payload: Mutation, state: ConfigState) -> ConfigEntryRecord:
    try:
        item = service.set_config_state(config_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned configuration not found")
    return item


@router.post("/configs/{config_id}/review", response_model=ConfigEntryRecord)
def review_config(config_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ConfigEntryRecord:
    return _set_config(config_id, workspace_id, payload, ConfigState.REVIEW)


@router.post("/configs/{config_id}/approved", response_model=ConfigEntryRecord)
def approve_config(config_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ConfigEntryRecord:
    return _set_config(config_id, workspace_id, payload, ConfigState.APPROVED)


@router.post("/configs/{config_id}/activate", response_model=ConfigEntryRecord)
def activate_config(config_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ConfigEntryRecord:
    return _set_config(config_id, workspace_id, payload, ConfigState.ACTIVE)


@router.post("/configs/{config_id}/retire", response_model=ConfigEntryRecord)
def retire_config(config_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ConfigEntryRecord:
    return _set_config(config_id, workspace_id, payload, ConfigState.RETIRED)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
