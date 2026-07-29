from fastapi import APIRouter
from app.schemas.recovery_reliability_adoption_drift_escalation_v21_217 import AdoptionDriftEscalationRequest, AdoptionDriftEscalationDecision
from app.services.recovery_reliability_adoption_drift_escalation_v21_217 import evaluate_reconciliation_readiness

router = APIRouter(prefix='/recovery-reliability/v21.217', tags=['recovery-reliability-v21.217'])

@router.post('/adoption-drift/reconciliation-readiness', response_model=AdoptionDriftEscalationDecision)
def reconciliation_readiness(req: AdoptionDriftEscalationRequest, human_approved: bool = False):
    return evaluate_reconciliation_readiness(req, human_approved=human_approved)
