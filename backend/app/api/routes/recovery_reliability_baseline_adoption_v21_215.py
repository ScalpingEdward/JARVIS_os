from fastapi import APIRouter
from app.schemas.recovery_reliability_baseline_adoption_v21_215 import BaselineAdoptionRequest, BaselineAdoptionDecision
from app.services.recovery_reliability_baseline_adoption_v21_215 import evaluate_baseline_adoption

router = APIRouter(prefix='/recovery-reliability/v21.215', tags=['recovery-reliability-v21.215'])

@router.post('/baseline-adoption/authorize', response_model=BaselineAdoptionDecision)
def baseline_adoption(req: BaselineAdoptionRequest, authorize: bool = False, human_approved: bool = False):
    return evaluate_baseline_adoption(req, authorize=authorize, human_approved=human_approved)
