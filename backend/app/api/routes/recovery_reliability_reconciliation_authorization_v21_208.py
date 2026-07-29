from fastapi import APIRouter
from app.schemas.recovery_reliability_reconciliation_authorization_v21_208 import ReconciliationAuthorizationRequest, ReconciliationAuthorizationDecision
from app.services.recovery_reliability_reconciliation_authorization_v21_208 import evaluate_recovery_authorization

router = APIRouter(prefix='/recovery-reliability/v21.208', tags=['recovery-reliability-v21.208'])

@router.post('/reconciliation/authorize', response_model=ReconciliationAuthorizationDecision)
def reconciliation_authorization(req: ReconciliationAuthorizationRequest, authorize: bool = False):
    return evaluate_recovery_authorization(req, authorize=authorize)
