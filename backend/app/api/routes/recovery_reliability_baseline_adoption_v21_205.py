from fastapi import APIRouter
from app.schemas.recovery_reliability_baseline_adoption_v21_205 import BaselineAdoptionRequest, BaselineAdoptionReceipt, BaselineAdoptionDecision
from app.services.recovery_reliability_baseline_adoption_v21_205 import evaluate_adoption

router = APIRouter(prefix='/recovery-reliability/v21.205', tags=['recovery-reliability-v21.205'])

@router.post('/baseline-adoption/evaluate', response_model=BaselineAdoptionDecision)
def baseline_adoption(req: BaselineAdoptionRequest, authorized: bool = False, receipt_human_approved: bool = False, receipt: BaselineAdoptionReceipt | None = None):
    return evaluate_adoption(req, authorized=authorized, receipt=receipt, receipt_human_approved=receipt_human_approved)
