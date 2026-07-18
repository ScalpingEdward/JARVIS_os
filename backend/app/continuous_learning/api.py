from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    DriftRecord,
    ExperienceCreate,
    ExperienceRecord,
    ImprovementCreate,
    ImprovementRecord,
    LearningRecommendation,
    LearningStatus,
    OutcomeCreate,
    OutcomeRecord,
    PatternRecord,
    RecommendationReview,
)
from .service import continuous_learning_service

router = APIRouter(prefix="/v1/learning", tags=["continuous-learning"])


@router.get("/status", response_model=LearningStatus)
def learning_status(workspace_id: str = Query(min_length=1, max_length=120)) -> LearningStatus:
    return continuous_learning_service.status(workspace_id)


@router.post("/experiences", response_model=ExperienceRecord, status_code=status.HTTP_201_CREATED)
def create_experience(payload: ExperienceCreate) -> ExperienceRecord:
    try:
        return continuous_learning_service.create_experience(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/experiences", response_model=list[ExperienceRecord])
def list_experiences(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ExperienceRecord]:
    return continuous_learning_service.list_experiences(workspace_id)


@router.get("/experiences/{experience_id}", response_model=ExperienceRecord)
def get_experience(
    experience_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> ExperienceRecord:
    record = continuous_learning_service.get_experience(workspace_id, experience_id)
    if record is None:
        raise HTTPException(status_code=404, detail="experience not found")
    return record


@router.post("/outcomes", response_model=OutcomeRecord, status_code=status.HTTP_201_CREATED)
def create_outcome(payload: OutcomeCreate) -> OutcomeRecord:
    try:
        return continuous_learning_service.create_outcome(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/outcomes", response_model=list[OutcomeRecord])
def list_outcomes(workspace_id: str = Query(min_length=1, max_length=120)) -> list[OutcomeRecord]:
    return continuous_learning_service.list_outcomes(workspace_id)


@router.get("/patterns", response_model=list[PatternRecord])
def list_patterns(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PatternRecord]:
    return continuous_learning_service.list_patterns(workspace_id)


@router.get("/recommendations", response_model=list[LearningRecommendation])
def list_recommendations(
    workspace_id: str = Query(min_length=1, max_length=120),
) -> list[LearningRecommendation]:
    return continuous_learning_service.list_recommendations(workspace_id)


@router.post("/recommendations/{recommendation_id}/review", response_model=LearningRecommendation)
def review_recommendation(
    recommendation_id: UUID,
    payload: RecommendationReview,
) -> LearningRecommendation:
    try:
        return continuous_learning_service.review_recommendation(recommendation_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/drift", response_model=list[DriftRecord])
def learning_drift(
    workspace_id: str = Query(min_length=1, max_length=120),
    minimum_samples: int = Query(default=4, ge=4, le=1000),
) -> list[DriftRecord]:
    return continuous_learning_service.drift(workspace_id, minimum_samples)


@router.post("/improvements", response_model=ImprovementRecord, status_code=status.HTTP_201_CREATED)
def create_improvement(payload: ImprovementCreate) -> ImprovementRecord:
    try:
        return continuous_learning_service.create_improvement(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/improvements", response_model=list[ImprovementRecord])
def list_improvements(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ImprovementRecord]:
    return continuous_learning_service.list_improvements(workspace_id)


@router.get("/audit", response_model=list[AuditRecord])
def learning_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return continuous_learning_service.audit(workspace_id)
