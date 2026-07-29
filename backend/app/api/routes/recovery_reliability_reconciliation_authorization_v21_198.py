from fastapi import APIRouter
from app.schemas.recovery_reliability_reconciliation_authorization_v21_198 import ReconciliationAuthorizationRequest, ReconciliationAuthorizationDecision
from app.services.recovery_reliability_reconciliation_authorization_v21_198 import authorize_reconciliation

router = APIRouter(prefix='/recovery-reliability/v21.198', tags=['recovery-reliability-v21.198'])

@router.post('/reconciliation/authorize', response_model=ReconciliationAuthorizationDecision)
def authorize(req: ReconciliationAuthorizationRequest, actor: str | None = None, human_authorized: bool = False):
    return authorize_reconciliation(req, actor=actor, human_authorized=human_authorized)
