import hashlib
import json
from app.schemas.recovery_reliability_baseline_rollout_v21_224 import BaselineRolloutRequest, BaselineRolloutDecision

_seen_sources: set[str] = set()

def _digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_rollout(req: BaselineRolloutRequest, human_approved: bool = False) -> BaselineRolloutDecision:
    reasons: list[str] = []
    candidate = sorted(set(req.candidate_consumers))
    stages = sorted(req.stages, key=lambda s: s.order)

    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'committed' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')
    if not candidate or len(candidate) != len(req.candidate_consumers): reasons.append('invalid-candidate-consumers')

    orders = [s.order for s in stages]
    if orders != list(range(1, len(stages) + 1)): reasons.append('non-contiguous-stage-order')

    flattened: list[str] = []
    for stage in stages:
        if not stage.consumers or len(stage.consumers) != len(set(stage.consumers)):
            reasons.append(f'invalid-stage-consumers:{stage.order}')
        if stage.exposure > req.max_stage_exposure:
            reasons.append(f'stage-exposure-limit-exceeded:{stage.order}')
        flattened.extend(stage.consumers)

    if sorted(flattened) != candidate or len(flattened) != len(set(flattened)):
        reasons.append('rollout-coverage-mismatch')

    approved_orders = [s.order for s in stages if s.approved]
    if approved_orders and approved_orders != list(range(1, max(approved_orders) + 1)):
        reasons.append('out-of-order-stage-approval')

    blocking_prefixes = ('invalid-stage-consumers:',)
    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-candidate-consumers','non-contiguous-stage-order','rollout-coverage-mismatch','out-of-order-stage-approval'}
    is_blocked = any(r in blocking or r.startswith(blocking_prefixes) for r in reasons)

    approved_stages = len(approved_orders)
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

    rollout_payload = [{'order': s.order, 'consumers': sorted(s.consumers), 'exposure': s.exposure} for s in stages]
    rollout_digest = _digest(rollout_payload)
    audit_digest = _digest({'source_id': req.source_id, 'workspace_id': req.workspace_id, 'candidate_baseline_id': req.candidate_baseline_id, 'candidate_version': req.candidate_version, 'candidate_digest': req.candidate_digest, 'rollback_baseline_id': req.rollback_baseline_id, 'rollback_version': req.rollback_version, 'rollback_digest': req.rollback_digest, 'recovery_sequence_digest': req.recovery_sequence_digest, 'rollout_digest': rollout_digest, 'state': state, 'reasons': reasons})
    return BaselineRolloutDecision(state=state, approved_stages=approved_stages, total_stages=len(stages), ordered_consumers=flattened, reasons=reasons, rollout_digest=rollout_digest, audit_digest=audit_digest)

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
