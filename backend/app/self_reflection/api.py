from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ExperimentCreate,
    ExperimentRecord,
    ImprovementProposal,
    ReflectionStatus,
    ReviewCreate,
    ReviewDomain,
    ReviewRecord,
)
from .service import reflection_service

router = APIRouter(prefix="/v1/reflection", tags=["self-reflection"])


@router.get("/status", response_model=ReflectionStatus)
def status_view() -> ReflectionStatus:
    return reflection_service.status()


@router.post("/reviews", response_model=ReviewRecord, status_code=status.HTTP_201_CREATED)
def create_review(payload: ReviewCreate) -> ReviewRecord:
    return reflection_service.add_review(payload)


@router.get("/reviews", response_model=list[ReviewRecord])
def list_reviews(domain: ReviewDomain | None = None) -> list[ReviewRecord]:
    return reflection_service.list_reviews(domain)


@router.get("/patterns")
def patterns(minimum_occurrences: int = Query(default=2, ge=2, le=100)) -> list[dict[str, object]]:
    return reflection_service.discover_patterns(minimum_occurrences)


@router.post("/proposals/generate", response_model=list[ImprovementProposal])
def generate_proposals() -> list[ImprovementProposal]:
    return reflection_service.propose_improvements()


@router.get("/proposals", response_model=list[ImprovementProposal])
def list_proposals() -> list[ImprovementProposal]:
    return reflection_service.list_proposals()


@router.post("/proposals/{proposal_id}/approve", response_model=ImprovementProposal)
def approve_proposal(proposal_id: UUID) -> ImprovementProposal:
    proposal = reflection_service.approve_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.post("/experiments", response_model=ExperimentRecord, status_code=status.HTTP_201_CREATED)
def create_experiment(payload: ExperimentCreate) -> ExperimentRecord:
    try:
        return reflection_service.create_experiment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/experiments", response_model=list[ExperimentRecord])
def list_experiments() -> list[ExperimentRecord]:
    return reflection_service.list_experiments()


@router.get("/lessons")
def lessons() -> dict[str, object]:
    return reflection_service.lessons()
