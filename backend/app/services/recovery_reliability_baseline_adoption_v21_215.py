import hashlib
import json
from app.schemas.recovery_reliability_baseline_adoption_v21_215 import BaselineAdoptionRequest, BaselineAdoptionDecision

_seen_source_consumers: set[tuple[str, str]] = set()
_seen_nonces: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def evaluate_baseline_adoption(req: BaselineAdoptionRequest, authorize: bool = False, human_approved: bool = False) -> BaselineAdoptionDecision:
    reasons: list[str] = []
    key = (req.source_id, req.target_consumer)
    receipt_fresh = False
    receipt_valid = False

    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'staged' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if key in _seen_source_consumers: reasons.append('duplicate-source-consumer')
    if not req.target_consumer: reasons.append('invalid-target-consumer')

    r = req.receipt
    if r is not None:
        age = (req.now - r.observed_at).total_seconds()
        receipt_fresh = 0 <= age <= req.receipt_ttl_seconds
        if r.nonce in _seen_nonces: reasons.append('duplicate-receipt-nonce')
        lineage_ok = (
            r.consumer_id == req.target_consumer and
            r.workspace_id == req.workspace_id and
            r.baseline_id == req.baseline_id and
            r.baseline_version == req.baseline_version and
            r.baseline_digest == req.baseline_digest and
            r.rollback_baseline_id == req.rollback_baseline_id and
            r.rollback_version == req.rollback_version
        )
        if not lineage_ok: reasons.append('receipt-lineage-mismatch')
        if not receipt_fresh: reasons.append('stale-or-future-receipt')
        if not r.adopted: reasons.append('receipt-not-adopted')
        if not r.healthy: reasons.append('receipt-unhealthy')
        if r.confidence < req.min_confidence: reasons.append('receipt-low-confidence')
        receipt_valid = lineage_ok and receipt_fresh and r.adopted and r.healthy and r.confidence >= req.min_confidence and r.nonce not in _seen_nonces

    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source-consumer','invalid-target-consumer','duplicate-receipt-nonce'}
    if any(x in blocking for x in reasons):
        state = 'blocked'
    elif not authorize:
        state = 'review-required'
    elif r is None:
        state = 'authorized'
    elif not receipt_valid:
        state = 'receipt-required'
    elif human_approved:
        state = 'adopted'
        _seen_source_consumers.add(key)
        _seen_nonces.add(r.nonce)
    else:
        state = 'receipt-required'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'rollback_baseline_id': req.rollback_baseline_id, 'rollback_version': req.rollback_version, 'target_consumer': req.target_consumer, 'receipt_fresh': receipt_fresh, 'receipt_valid': receipt_valid, 'state': state, 'reasons': reasons}
    return BaselineAdoptionDecision(state=state, target_consumer=req.target_consumer, receipt_fresh=receipt_fresh, receipt_valid=receipt_valid, reasons=reasons, audit_digest=_digest(payload))

def reset_seen_for_tests() -> None:
    _seen_source_consumers.clear()
    _seen_nonces.clear()
