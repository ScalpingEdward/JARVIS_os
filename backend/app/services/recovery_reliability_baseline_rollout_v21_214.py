import hashlib
import json
from app.schemas.recovery_reliability_baseline_rollout_v21_214 import BaselineRolloutRequest, BaselineRolloutDecision

_seen_sources: set[str] = set()

def _digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_rollout(req: BaselineRolloutRequest, human_approved: bool = False) -> BaselineRolloutDecision:
    reasons: list[str] = []
    consumers = sorted(set(req.candidate_consumers))
    stages = sorted(req.stages, key=lambda s: s.order)

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'committed' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if not consumers or len(consumers) != len(req.candidate_consumers):
        reasons.append('invalid-candidate-consumers')

    orders = [s.order for s in stages]
    if orders != list(range(1, len(stages) + 1)):
        reasons.append('non-contiguous-stage-order')

    seen: set[str] = set()
    staged_consumers: list[str] = []
    for stage in stages:
        unique = set(stage.consumer_ids)
        if not unique or len(unique) != len(stage.consumer_ids):
            reasons.append(f'invalid-stage-consumers:{stage.order}')
        if seen & unique:
            reasons.append(f'overlapping-stage-consumers:{stage.order}')
        seen |= unique
        staged_consumers.extend(stage.consumer_ids)
        total = len(consumers) or 1
        exposure = len(unique) / total
        if exposure > stage.max_exposure:
            reasons.append(f'stage-exposure-limit-exceeded:{stage.order}')

    if seen != set(consumers):
        reasons.append('stage-coverage-mismatch')

    approved_stages = sum(1 for s in stages if s.approved)
    approved_orders = [s.order for s in stages if s.approved]
    if approved_orders and approved_orders != list(range(1, max(approved_orders) + 1)):
        reasons.append('out-of-order-stage-approval')

    blocking_prefixes = ('invalid-stage-consumers:', 'overlapping-stage-consumers:')
    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-candidate-consumers','non-contiguous-stage-order','stage-coverage-mismatch','out-of-order-stage-approval'}
    is_blocked = any(r in blocking or r.startswith(blocking_prefixes) for r in reasons)

    if is_blocked:
        state = 'blocked'
    elif any(r.startswith('stage-exposure-limit-exceeded:') for r in reasons):
        state = 'review-required'
    elif not human_approved:
        state = 'review-required'
    elif approved_stages < len(stages):
        state = 'eligible'
    else:
        state = 'staged'
        _seen_sources.add(req.source_id)

    rollout_digest = _digest([{'order': s.order, 'consumer_ids': sorted(s.consumer_ids), 'max_exposure': s.max_exposure} for s in stages])
    audit_digest = _digest({'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'rollback_baseline_id': req.rollback_baseline_id, 'rollback_version': req.rollback_version, 'rollout_digest': rollout_digest, 'approved_stages': approved_stages, 'state': state, 'reasons': reasons})
    return BaselineRolloutDecision(state=state, eligible_consumers=consumers, approved_stages=approved_stages, total_stages=len(stages), reasons=reasons, rollout_digest=rollout_digest, audit_digest=audit_digest)

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
