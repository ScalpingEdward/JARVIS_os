from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalRequest,
    AuditRecord,
    CandidateListResponse,
    GovernanceStatus,
    OptimizationCandidate,
    OptimizationCandidateCreate,
    SimulationComparison,
)
from .service import optimization_governance_service

router = APIRouter(prefix="/v1/optimization-governance", tags=["optimization-governance"])


@router.get("/status", response_model=GovernanceStatus)
def governance_status(workspace_id: str = Query(min_length=1)) -> GovernanceStatus:
    return optimization_governance_service.status(workspace_id)


@router.post("/candidates", response_model=OptimizationCandidate, status_code=status.HTTP_201_CREATED)
def create_candidate(payload: OptimizationCandidateCreate) -> OptimizationCandidate:
    try:
        return optimization_governance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/candidates", response_model=CandidateListResponse)
def list_candidates(workspace_id: str = Query(min_length=1)) -> CandidateListResponse:
    items = optimization_governance_service.list_candidates(workspace_id)
    return CandidateListResponse(items=items, count=len(items))


@router.get("/candidates/{candidate_id}", response_model=OptimizationCandidate)
def get_candidate(candidate_id: UUID, workspace_id: str = Query(min_length=1)) -> OptimizationCandidate:
    candidate = optimization_governance_service.get(candidate_id, workspace_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Optimization candidate not found")
    return candidate


@router.post("/candidates/{candidate_id}/analyze", response_model=OptimizationCandidate)
def analyze_candidate(
    candidate_id: UUID,
    workspace_id: str = Query(min_length=1),
    actor_id: str = Query(min_length=1),
) -> OptimizationCandidate:
    try:
        return optimization_governance_service.analyze(candidate_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/candidates/{candidate_id}/compare", response_model=SimulationComparison)
def compare_variants(
    candidate_id: UUID,
    workspace_id: str = Query(min_length=1),
    control: str = Query(min_length=1),
    challenger: str = Query(min_length=1),
) -> SimulationComparison:
    try:
        return optimization_governance_service.compare(candidate_id, workspace_id, control, challenger)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/approval", response_model=OptimizationCandidate)
def approve_candidate(candidate_id: UUID, payload: ApprovalRequest) -> OptimizationCandidate:
    try:
        return optimization_governance_service.approve(candidate_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditRecord])
def governance_audit(workspace_id: str = Query(min_length=1)) -> list[AuditRecord]:
    return optimization_governance_service.audit(workspace_id)
