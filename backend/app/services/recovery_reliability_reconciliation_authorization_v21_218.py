import hashlib
import json
from app.schemas.recovery_reliability_reconciliation_authorization_v21_218 import ReconciliationAuthorizationRequest, ReconciliationAuthorizationDecision

_seen_sources: set[str] = set()

def _digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_recovery_authorization(req: ReconciliationAuthorizationRequest, authorize: bool = False) -> ReconciliationAuthorizationDecision:
    reasons: list[str] = []
    affected = sorted(set(req.affected_consumers))
    healthy = sorted(set(req.healthy_consumers))
    steps = sorted(req.recovery_steps, key=lambda s: s.order)

    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'reconciliation-ready' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')
    if not affected or len(affected) != len(req.affected_consumers): reasons.append('invalid-affected-consumers')
    if set(affected) & set(healthy): reasons.append('healthy-consumer-overlap')
    if req.blast_radius > req.max_blast_radius: reasons.append('blast-radius-limit-exceeded')
    if req.residual_risk > req.max_residual_risk: reasons.append('residual-risk-limit-exceeded')

    orders = [s.order for s in steps]
    ordered_consumers = [s.consumer_id for s in steps]
    if orders != list(range(1, len(steps) + 1)): reasons.append('non-contiguous-recovery-order')
    if sorted(ordered_consumers) != affected or len(ordered_consumers) != len(set(ordered_consumers)):
        reasons.append('recovery-sequence-coverage-mismatch')
    if set(ordered_consumers) & set(healthy): reasons.append('healthy-consumer-targeted')

    approved_steps = sum(1 for s in steps if s.approved)
    approved_orders = [s.order for s in steps if s.approved]
    if approved_orders and approved_orders != list(range(1, max(approved_orders) + 1)):
        reasons.append('out-of-order-step-approval')

    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-affected-consumers','healthy-consumer-overlap','non-contiguous-recovery-order','recovery-sequence-coverage-mismatch','healthy-consumer-targeted','out-of-order-step-approval'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif 'blast-radius-limit-exceeded' in reasons or 'residual-risk-limit-exceeded' in reasons:
        state = 'review-required'
    elif not authorize:
        state = 'review-required'
    elif approved_steps == 0:
        state = 'authorized'
    elif approved_steps < len(steps):
        state = 'staged'
    else:
        state = 'recovery-ready'
        _seen_sources.add(req.source_id)

    sequence_payload = [{'order': s.order, 'consumer_id': s.consumer_id, 'drift_reason': s.drift_reason, 'action': s.action} for s in steps]
    sequence_digest = _digest(sequence_payload)
    audit_digest = _digest({'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'sequence_digest': sequence_digest, 'approved_steps': approved_steps, 'state': state, 'reasons': reasons})
    return ReconciliationAuthorizationDecision(state=state, ordered_consumers=ordered_consumers, approved_steps=approved_steps, total_steps=len(steps), reasons=reasons, sequence_digest=sequence_digest, audit_digest=audit_digest)

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
