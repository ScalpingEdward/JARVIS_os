import hashlib
import json
from app.schemas.recovery_reliability_baseline_rollout_v21_204 import BaselineRolloutRequest, BaselineRolloutDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_rollout(req: BaselineRolloutRequest, eligibility_approved: bool = False, approved_stage_indices: list[int] | None = None) -> BaselineRolloutDecision:
    approved_stage_indices = sorted(set(approved_stage_indices or []))
    reasons: list[str] = []
    candidates = sorted(set(req.candidate_consumers))

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'committed' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if not candidates or len(candidates) != len(req.candidate_consumers):
        reasons.append('invalid-candidate-consumers')

    ordered = sorted(req.stages, key=lambda s: s.stage_index)
    expected_indices = list(range(1, len(ordered) + 1))
    actual_indices = [s.stage_index for s in ordered]
    if actual_indices != expected_indices or not ordered:
        reasons.append('invalid-stage-order')

    seen: set[str] = set()
    covered: list[str] = []
    total = max(len(candidates), 1)
    for stage in ordered:
        stage_ids = stage.consumer_ids
        if not stage_ids or len(set(stage_ids)) != len(stage_ids):
            reasons.append(f'invalid-stage-consumers:{stage.stage_index}')
        if seen.intersection(stage_ids):
            reasons.append(f'overlapping-stage-consumers:{stage.stage_index}')
        seen.update(stage_ids)
        covered.extend(stage_ids)
        exposure = len(stage_ids) / total
        if exposure > stage.max_stage_exposure:
            reasons.append(f'stage-exposure-limit-exceeded:{stage.stage_index}')

    if sorted(set(covered)) != candidates:
        reasons.append('incomplete-candidate-coverage')
    if any(i not in expected_indices for i in approved_stage_indices):
        reasons.append('invalid-stage-approval')

    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-candidate-consumers','invalid-stage-order','incomplete-candidate-coverage','invalid-stage-approval'}
    blocking_now = any(r in blocking or r.startswith('invalid-stage-consumers:') or r.startswith('overlapping-stage-consumers:') for r in reasons)
    if blocking_now:
        state = 'blocked'
    elif reasons:
        state = 'review-required'
    elif not eligibility_approved:
        state = 'review-required'
    elif approved_stage_indices == expected_indices:
        state = 'staged'
        _seen_sources.add(req.source_id)
    else:
        state = 'eligible'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'rollback_version': req.rollback_version, 'rollback_value': req.rollback_value, 'candidates': candidates, 'stages': [s.model_dump() for s in ordered], 'approved_stage_indices': approved_stage_indices, 'state': state, 'reasons': reasons}
    return BaselineRolloutDecision(state=state, stage_count=len(ordered), eligible_consumers=candidates, approved_stage_indices=approved_stage_indices, reasons=reasons, audit_digest=_digest(payload))

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
