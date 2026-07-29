import hashlib
import json
from app.schemas.recovery_reliability_reconciliation_authorization_v21_198 import ReconciliationAuthorizationRequest, ReconciliationAuthorizationDecision

_seen_sources: set[str] = set()

def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()
    return hashlib.sha256(raw).hexdigest()

def authorize_reconciliation(req: ReconciliationAuthorizationRequest, *, actor: str | None = None, human_authorized: bool = False) -> ReconciliationAuthorizationDecision:
    reasons: list[str] = []
    affected = sorted(set(req.affected_consumers))
    healthy = sorted(set(req.healthy_consumers))
    steps = sorted(req.recovery_steps, key=lambda s: s.order)
    orders = [s.order for s in steps]
    step_consumers = [s.consumer_id for s in steps]

    if req.source_state != 'reconciliation-ready' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if not affected:
        reasons.append('no-affected-consumers')
    if set(affected) & set(healthy):
        reasons.append('consumer-set-overlap')
    if len(step_consumers) != len(set(step_consumers)):
        reasons.append('duplicate-recovery-consumer')
    if set(step_consumers) != set(affected):
        reasons.append('recovery-sequence-coverage-mismatch')
    if orders != list(range(1, len(steps) + 1)):
        reasons.append('non-contiguous-recovery-order')
    if req.blast_radius > req.max_blast_radius:
        reasons.append('blast-radius-limit-exceeded')
    if req.residual_risk > req.max_residual_risk:
        reasons.append('residual-risk-limit-exceeded')

    blocking = {'invalid-source-admission','risk-brain-hard-block','duplicate-source','no-affected-consumers','consumer-set-overlap','duplicate-recovery-consumer','recovery-sequence-coverage-mismatch','non-contiguous-recovery-order'}
    approved_steps = [s.consumer_id for s in steps if s.approved]
    pending_steps = [s.consumer_id for s in steps if not s.approved]

    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif reasons:
        state = 'review-required'
    elif not human_authorized:
        state = 'review-required'
    elif pending_steps and approved_steps:
        first_pending = min(s.order for s in steps if not s.approved)
        if any(s.approved and s.order > first_pending for s in steps):
            state = 'blocked'
            reasons.append('out-of-order-step-approval')
        else:
            state = 'staged'
    elif pending_steps:
        state = 'authorized'
    else:
        state = 'recovery-ready'
        _seen_sources.add(req.source_id)

    sequence_digest = _digest([s.model_dump() for s in steps])
    audit_payload = {
        'source_id': req.source_id,
        'workspace_id': req.workspace_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'affected': affected,
        'healthy': healthy,
        'approved_steps': approved_steps,
        'pending_steps': pending_steps,
        'state': state,
        'reasons': reasons,
        'actor': actor if human_authorized else None,
        'sequence_digest': sequence_digest,
    }
    return ReconciliationAuthorizationDecision(
        state=state,
        authorized_by=actor if human_authorized else None,
        approved_steps=approved_steps,
        pending_steps=pending_steps,
        reasons=reasons,
        sequence_digest=sequence_digest,
        audit_digest=_digest(audit_payload),
    )

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
