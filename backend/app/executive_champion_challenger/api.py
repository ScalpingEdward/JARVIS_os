from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    CandidateEvidenceUpdate,
    CandidateListResponse,
    ChampionChallengerStatusResponse,
    ComparisonCreate,
    ComparisonListResponse,
    PromotionResult,
    StrategyCandidate,
    StrategyCandidateCreate,
    StrategyComparison,
)
from .service import executive_champion_challenger_service

router = APIRouter(tags=["executive-champion-challenger"])


@router.get("/v1/executive-champion-challenger/status", response_model=ChampionChallengerStatusResponse)
def status_view(workspace_id: str = Query(min_length=1, max_length=100)) -> ChampionChallengerStatusResponse:
    return executive_champion_challenger_service.status(workspace_id)


@router.post("/v1/executive-champion-challenger/candidates", response_model=StrategyCandidate, status_code=status.HTTP_201_CREATED)
def create_candidate(payload: StrategyCandidateCreate) -> StrategyCandidate:
    try:
        return executive_champion_challenger_service.create_candidate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-champion-challenger/candidates", response_model=CandidateListResponse)
def list_candidates(workspace_id: str = Query(min_length=1, max_length=100), account_profile_id: str | None = None) -> CandidateListResponse:
    items = executive_champion_challenger_service.list_candidates(workspace_id, account_profile_id)
    return CandidateListResponse(items=items, count=len(items))


@router.get("/v1/executive-champion-challenger/candidates/{candidate_id}", response_model=StrategyCandidate)
def get_candidate(candidate_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyCandidate:
    item = executive_champion_challenger_service.get_candidate(candidate_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy candidate not found")
    return item


@router.post("/v1/executive-champion-challenger/candidates/{candidate_id}/evidence", response_model=StrategyCandidate)
def update_evidence(candidate_id: UUID, payload: CandidateEvidenceUpdate, workspace_id: str = Query(min_length=1, max_length=100)) -> StrategyCandidate:
    try:
        return executive_champion_challenger_service.update_evidence(candidate_id, workspace_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v1/executive-champion-challenger/comparisons", response_model=StrategyComparison, status_code=status.HTTP_201_CREATED)
def compare_candidates(payload: ComparisonCreate) -> StrategyComparison:
    try:
        return executive_champion_challenger_service.compare(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-champion-challenger/comparisons", response_model=ComparisonListResponse)
def list_comparisons(workspace_id: str = Query(min_length=1, max_length=100)) -> ComparisonListResponse:
    items = executive_champion_challenger_service.list_comparisons(workspace_id)
    return ComparisonListResponse(items=items, count=len(items))


@router.post("/v1/executive-champion-challenger/comparisons/{comparison_id}/promote", response_model=PromotionResult)
def promote_challenger(comparison_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> PromotionResult:
    try:
        return executive_champion_challenger_service.promote(workspace_id, comparison_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-champion-challenger/audit", response_model=list[AuditRecord])
def audit_view(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_champion_challenger_service.audit_records(workspace_id)
