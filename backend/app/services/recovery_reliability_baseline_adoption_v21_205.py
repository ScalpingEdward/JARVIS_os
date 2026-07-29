import hashlib
import json
from app.schemas.recovery_reliability_baseline_adoption_v21_205 import BaselineAdoptionRequest, BaselineAdoptionReceipt, BaselineAdoptionDecision

_seen_source_consumers: set[tuple[str, str]] = set()
_seen_nonces: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def evaluate_adoption(req: BaselineAdoptionRequest, authorized: bool = False, receipt: BaselineAdoptionReceipt | None = None, receipt_human_approved: bool = False) -> BaselineAdoptionDecision:
    reasons: list[str] = []
    key = (req.source_id, req.consumer_id)

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'staged' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if key in _seen_source_consumers:
        reasons.append('duplicate-source-consumer')

    blocking = {'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source-consumer'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif not authorized:
        state = 'review-required'
    elif receipt is None:
        state = 'receipt-required'
    else:
        age = (req.now - receipt.observed_at).total_seconds()
        lineage_ok = (
            receipt.consumer_id == req.consumer_id and
            receipt.workspace_id == req.workspace_id and
            receipt.baseline_id == req.baseline_id and
            receipt.baseline_version == req.baseline_version and
            receipt.baseline_digest == req.baseline_digest and
            receipt.rollback_version == req.rollback_version and
            abs(receipt.rollback_value - req.rollback_value) <= 1e-9
        )
        if receipt.nonce in _seen_nonces:
            reasons.append('replayed-receipt-nonce')
        if not lineage_ok:
            reasons.append('receipt-lineage-mismatch')
        if not (0 <= age <= req.receipt_ttl_seconds):
            reasons.append('stale-or-future-receipt')
        if not receipt.adopted:
            reasons.append('not-adopted')
        if not receipt.healthy:
            reasons.append('unhealthy')
        if receipt.confidence < req.min_confidence:
            reasons.append('low-confidence')

        if reasons:
            state = 'blocked'
        elif not receipt_human_approved:
            state = 'authorized'
        else:
            state = 'adopted'
            _seen_source_consumers.add(key)
            _seen_nonces.add(receipt.nonce)

    payload = {
        'source_id': req.source_id,
        'workspace_id': req.workspace_id,
        'consumer_id': req.consumer_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'rollback_version': req.rollback_version,
        'rollback_value': req.rollback_value,
        'state': state,
        'reasons': reasons,
    }
    return BaselineAdoptionDecision(state=state, consumer_id=req.consumer_id, reasons=reasons, audit_digest=_digest(payload))

def reset_seen_for_tests() -> None:
    _seen_source_consumers.clear()
    _seen_nonces.clear()
