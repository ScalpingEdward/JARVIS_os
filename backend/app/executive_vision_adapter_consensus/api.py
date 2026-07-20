from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ConsensusAssessment, ConsensusAssessmentCreate, ConsensusStatusResponse
from .service import executive_vision_adapter_consensus_service

router = APIRouter(tags=["executive-vision-adapter-consensus"])
BASE = "/v1/executive-vision-adapter-consensus"


@router.get(f"{BASE}/status", response_model=ConsensusStatusResponse)
def consensus_status(workspace_id: str = Query(min_length=1, max_length=100)) -> ConsensusStatusResponse:
    return executive_vision_adapter_consensus_service.status(workspace_id)


@router.post(f"{BASE}/assessments", response_model=ConsensusAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: ConsensusAssessmentCreate) -> ConsensusAssessment:
    try:
        return executive_vision_adapter_consensus_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/assessments", response_model=list[ConsensusAssessment])
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> list[ConsensusAssessment]:
    return executive_vision_adapter_consensus_service.list_assessments(workspace_id)


@router.get(f"{BASE}/assessments/{{assessment_id}}", response_model=ConsensusAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ConsensusAssessment:
    item = executive_vision_adapter_consensus_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vision consensus assessment not found")
    return item


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def consensus_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_vision_adapter_consensus_service.audit(workspace_id)
