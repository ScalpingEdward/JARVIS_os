from fastapi import APIRouter
from app.schemas.recovery_reliability_adoption_consistency_v21_206 import AdoptionConsistencyRequest, AdoptionConsistencyDecision
from app.services.recovery_reliability_adoption_consistency_v21_206 import evaluate_adoption_consistency

router = APIRouter(prefix='/recovery-reliability/v21.206', tags=['recovery-reliability-v21.206'])

@router.post('/adoption-consistency/evaluate', response_model=AdoptionConsistencyDecision)
def adoption_consistency(req: AdoptionConsistencyRequest, human_approved: bool = False):
    return evaluate_adoption_consistency(req, human_approved=human_approved)
