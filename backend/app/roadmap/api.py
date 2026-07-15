from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .models import ReplanResponse, RiskReport, RoadmapCreate, RoadmapProgress, RoadmapRecord, TaskStatusUpdate, TodayPlan
from .service import RoadmapError, roadmap_service

router = APIRouter(prefix="/v1/roadmaps", tags=["roadmaps"])


@router.post("", response_model=RoadmapRecord)
def create_roadmap(payload: RoadmapCreate) -> RoadmapRecord:
    return roadmap_service.create(payload)


@router.get("/{roadmap_id}", response_model=RoadmapRecord)
def get_roadmap(roadmap_id: UUID) -> RoadmapRecord:
    try:
        return roadmap_service.get(roadmap_id)
    except RoadmapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{roadmap_id}/tasks/{task_id}", response_model=RoadmapRecord)
def update_task(roadmap_id: UUID, task_id: UUID, payload: TaskStatusUpdate) -> RoadmapRecord:
    try:
        return roadmap_service.update_task(roadmap_id, task_id, payload)
    except RoadmapError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{roadmap_id}/progress", response_model=RoadmapProgress)
def progress(roadmap_id: UUID) -> RoadmapProgress:
    try:
        return roadmap_service.progress(roadmap_id)
    except RoadmapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{roadmap_id}/today", response_model=TodayPlan)
def today(roadmap_id: UUID, capacity_hours: int = Query(default=8, ge=1, le=24)) -> TodayPlan:
    try:
        return roadmap_service.today(roadmap_id, capacity_hours)
    except RoadmapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{roadmap_id}/risks", response_model=RiskReport)
def risks(roadmap_id: UUID) -> RiskReport:
    try:
        return roadmap_service.risks(roadmap_id)
    except RoadmapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{roadmap_id}/replan", response_model=ReplanResponse)
def replan(roadmap_id: UUID) -> ReplanResponse:
    try:
        return roadmap_service.replan(roadmap_id)
    except RoadmapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
