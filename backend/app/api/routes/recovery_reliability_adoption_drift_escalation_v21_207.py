from fastapi import APIRouter
from app.schemas.recovery_reliability_adoption_drift_escalation_v21_207 import DriftEscalationRequest, DriftEscalationDecision
from app.services.recovery_reliability_adoption_drift_escalation_v21_207 import evaluate

router=APIRouter(prefix='/recovery-reliability/v21.207',tags=['recovery-reliability-v21.207'])

@router.post('/adoption-drift/reconciliation-readiness',response_model=DriftEscalationDecision)
def reconciliation_readiness(req:DriftEscalationRequest,human_approved:bool=False):
    return evaluate(req,human_approved=human_approved)
