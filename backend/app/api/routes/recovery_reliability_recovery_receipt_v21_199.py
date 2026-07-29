from fastapi import APIRouter
from app.schemas.recovery_reliability_recovery_receipt_v21_199 import RecoveryReceiptReconciliationRequest, RecoveryReceiptReconciliationDecision
from app.services.recovery_reliability_recovery_receipt_v21_199 import reconcile_recovery_receipts

router = APIRouter(prefix='/recovery-reliability/v21.199', tags=['recovery-reliability-v21.199'])

@router.post('/recovery-receipts/reconcile', response_model=RecoveryReceiptReconciliationDecision)
def recovery_receipt_reconciliation(req: RecoveryReceiptReconciliationRequest, human_approved: bool = False):
    return reconcile_recovery_receipts(req, human_approved=human_approved)
