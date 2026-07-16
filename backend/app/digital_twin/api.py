from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    ScenarioRequest,
    TwinFeedback,
    TwinFeedbackCreate,
    TwinProfile,
    TwinProfileCreate,
    TwinRecommendation,
    TwinStatus,
)
from .service import DigitalTwinError, digital_twin_service

router = APIRouter(prefix="/v1/digital-twin", tags=["digital-twin"])


@router.get("/status", response_model=TwinStatus)
def twin_status() -> TwinStatus:
    return digital_twin_service.status()


@router.put("/profile", response_model=TwinProfile)
def configure_profile(payload: TwinProfileCreate) -> TwinProfile:
    return digital_twin_service.configure(payload)


@router.get("/profile", response_model=TwinProfile)
def get_profile() -> TwinProfile:
    try:
        return digital_twin_service.profile()
    except DigitalTwinError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scenarios/evaluate", response_model=TwinRecommendation, status_code=status.HTTP_201_CREATED)
def evaluate_scenario(payload: ScenarioRequest) -> TwinRecommendation:
    try:
        return digital_twin_service.evaluate(payload)
    except DigitalTwinError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/recommendations", response_model=list[TwinRecommendation])
def list_recommendations() -> list[TwinRecommendation]:
    return digital_twin_service.list_recommendations()


@router.get("/recommendations/{recommendation_id}", response_model=TwinRecommendation)
def get_recommendation(recommendation_id: UUID) -> TwinRecommendation:
    record = digital_twin_service.recommendation(recommendation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return record


@router.post("/feedback", response_model=TwinFeedback, status_code=status.HTTP_201_CREATED)
def add_feedback(payload: TwinFeedbackCreate) -> TwinFeedback:
    try:
        return digital_twin_service.add_feedback(payload)
    except DigitalTwinError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback", response_model=list[TwinFeedback])
def list_feedback() -> list[TwinFeedback]:
    return digital_twin_service.feedback()
