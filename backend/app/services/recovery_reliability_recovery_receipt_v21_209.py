import hashlib
import json
from app.schemas.recovery_reliability_recovery_receipt_v21_209 import RecoveryReceiptReconciliationRequest, RecoveryReceiptReconciliationDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def reconcile_recovery_receipts(req: RecoveryReceiptReconciliationRequest, human_approved: bool = False) -> RecoveryReceiptReconciliationDecision:
    reasons: list[str] = []
    expected = list(req.expected_order)
    expected_set = set(req.expected_consumers)
    by_consumer = {}
    nonces: set[str] = set()

    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'recovery-ready' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')
    if not expected_set or set(expected) != expected_set or len(expected) != len(expected_set): reasons.append('invalid-expected-order')

    for receipt in req.receipts:
        if receipt.consumer_id in by_consumer: reasons.append('duplicate-consumer-receipt')
        by_consumer[receipt.consumer_id] = receipt
        if receipt.nonce in nonces: reasons.append('duplicate-receipt-nonce')
        nonces.add(receipt.nonce)

    if set(by_consumer) - expected_set: reasons.append('unexpected-consumer-receipt')

    completed, incomplete = [], []
    for idx, consumer_id in enumerate(expected, start=1):
        r = by_consumer.get(consumer_id)
        if r is None:
            incomplete.append(consumer_id)
            reasons.append(f'missing-receipt:{consumer_id}')
            continue
        age = (req.now - r.observed_at).total_seconds()
        lineage_ok = (
            r.workspace_id == req.workspace_id and
            r.baseline_id == req.baseline_id and
            r.baseline_version == req.baseline_version and
            r.baseline_digest == req.baseline_digest and
            r.recovery_sequence_digest == req.recovery_sequence_digest
        )
        fresh = 0 <= age <= req.receipt_ttl_seconds
        order_ok = r.step_order == idx
        quality_ok = r.recovery_quality >= req.min_recovery_quality
        if r.recovered and r.healthy and lineage_ok and fresh and order_ok and quality_ok:
            completed.append(consumer_id)
        else:
            incomplete.append(consumer_id)
            if not lineage_ok: reasons.append(f'lineage-mismatch:{consumer_id}')
            if not fresh: reasons.append(f'stale-or-future-receipt:{consumer_id}')
            if not order_ok: reasons.append(f'step-order-mismatch:{consumer_id}')
            if not r.recovered: reasons.append(f'not-recovered:{consumer_id}')
            if not r.healthy: reasons.append(f'unhealthy:{consumer_id}')
            if not quality_ok: reasons.append(f'low-recovery-quality:{consumer_id}')

    score = round(len(completed) / len(expected), 4) if expected else 0.0
    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-expected-order','duplicate-consumer-receipt','duplicate-receipt-nonce','unexpected-consumer-receipt'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif incomplete:
        state = 'incomplete'
    elif human_approved:
        state = 'completed'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'recovery_sequence_digest': req.recovery_sequence_digest, 'completed': completed, 'incomplete': incomplete, 'score': score, 'state': state, 'reasons': reasons}
    return RecoveryReceiptReconciliationDecision(state=state, completion_score=score, completed_consumers=completed, incomplete_consumers=incomplete, reasons=reasons, audit_digest=_digest(payload))

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
