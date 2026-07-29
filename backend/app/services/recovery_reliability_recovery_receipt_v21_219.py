import hashlib
import json
from app.schemas.recovery_reliability_recovery_receipt_v21_219 import RecoveryReceiptReconciliationRequest, RecoveryReceiptReconciliationDecision

_seen_sources: set[str] = set()
_seen_nonces: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def reconcile_recovery_receipts(req: RecoveryReceiptReconciliationRequest, human_approved: bool = False) -> RecoveryReceiptReconciliationDecision:
    reasons: list[str] = []
    expected = list(req.expected_consumers)
    expected_unique = list(dict.fromkeys(expected))
    by_consumer = {}
    request_nonces: set[str] = set()

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'recovery-ready' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if not expected or len(expected) != len(expected_unique):
        reasons.append('invalid-expected-consumers')

    for receipt in req.receipts:
        if receipt.consumer_id in by_consumer:
            reasons.append('duplicate-consumer-receipt')
        by_consumer[receipt.consumer_id] = receipt
        if receipt.nonce in request_nonces or receipt.nonce in _seen_nonces:
            reasons.append('replayed-receipt-nonce')
        request_nonces.add(receipt.nonce)

    if set(by_consumer) - set(expected_unique):
        reasons.append('unexpected-consumer-receipt')

    completed: list[str] = []
    incomplete: list[str] = []
    expected_order = {consumer_id: index + 1 for index, consumer_id in enumerate(expected_unique)}

    for consumer_id in expected_unique:
        receipt = by_consumer.get(consumer_id)
        if receipt is None:
            incomplete.append(consumer_id)
            reasons.append(f'missing-receipt:{consumer_id}')
            continue

        age = (req.now - receipt.observed_at).total_seconds()
        fresh = 0 <= age <= req.receipt_ttl_seconds
        lineage_ok = (
            receipt.workspace_id == req.workspace_id
            and receipt.baseline_id == req.baseline_id
            and receipt.baseline_version == req.baseline_version
            and receipt.baseline_digest == req.baseline_digest
            and receipt.sequence_digest == req.sequence_digest
        )
        order_ok = receipt.step_order == expected_order[consumer_id]
        quality_ok = receipt.recovery_quality >= req.min_recovery_quality

        if receipt.recovered and receipt.healthy and lineage_ok and order_ok and fresh and quality_ok:
            completed.append(consumer_id)
        else:
            incomplete.append(consumer_id)
            if not lineage_ok: reasons.append(f'lineage-or-sequence-mismatch:{consumer_id}')
            if not order_ok: reasons.append(f'step-order-mismatch:{consumer_id}')
            if not fresh: reasons.append(f'stale-or-future-receipt:{consumer_id}')
            if not receipt.recovered: reasons.append(f'not-recovered:{consumer_id}')
            if not receipt.healthy: reasons.append(f'unhealthy:{consumer_id}')
            if not quality_ok: reasons.append(f'low-recovery-quality:{consumer_id}')

    completion_score = round(len(completed) / len(expected_unique), 4) if expected_unique else 0.0
    blocking = {
        'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source',
        'invalid-expected-consumers', 'duplicate-consumer-receipt',
        'replayed-receipt-nonce', 'unexpected-consumer-receipt'
    }
    if any(reason in blocking for reason in reasons):
        state = 'blocked'
    elif incomplete:
        state = 'incomplete'
    elif human_approved:
        state = 'completed'
        _seen_sources.add(req.source_id)
        _seen_nonces.update(request_nonces)
    else:
        state = 'review-required'

    audit_digest = _digest({
        'source_id': req.source_id,
        'workspace_id': req.workspace_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'sequence_digest': req.sequence_digest,
        'completed': completed,
        'incomplete': incomplete,
        'completion_score': completion_score,
        'state': state,
        'reasons': reasons,
    })
    return RecoveryReceiptReconciliationDecision(
        state=state,
        completion_score=completion_score,
        completed_consumers=completed,
        incomplete_consumers=incomplete,
        reasons=reasons,
        audit_digest=audit_digest,
    )

def reset_replay_guards_for_tests() -> None:
    _seen_sources.clear()
    _seen_nonces.clear()
