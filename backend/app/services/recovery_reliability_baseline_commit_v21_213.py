import hashlib
import json
from app.schemas.recovery_reliability_baseline_commit_v21_213 import BaselineCommitRequest, BaselineCommitDecision

_seen_sources: set[str] = set()
_seen_previews: set[str] = set()

def _digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_baseline_commit(req: BaselineCommitRequest, human_approved: bool = False) -> BaselineCommitDecision:
    reasons: list[str] = []
    delta = round(req.candidate_value - req.previous_value, 6)

    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'approved-preview' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')
    if req.preview_id in _seen_previews: reasons.append('duplicate-preview')
    if req.candidate_version != req.previous_version + 1: reasons.append('non-monotonic-version')
    if req.rollback_version != req.previous_version or req.rollback_value != req.previous_value: reasons.append('rollback-lineage-mismatch')
    if abs(delta) > req.max_delta: reasons.append('candidate-delta-limit-exceeded')
    if req.candidate_baseline_id == req.previous_baseline_id: reasons.append('candidate-id-reuse')

    candidate_payload = {
        'workspace_id': req.workspace_id,
        'preview_id': req.preview_id,
        'previous_baseline_id': req.previous_baseline_id,
        'previous_version': req.previous_version,
        'previous_value': req.previous_value,
        'previous_digest': req.previous_digest,
        'candidate_baseline_id': req.candidate_baseline_id,
        'candidate_version': req.candidate_version,
        'candidate_value': req.candidate_value,
        'candidate_preview_digest': req.candidate_preview_digest,
        'rollback_version': req.rollback_version,
        'rollback_value': req.rollback_value,
    }
    candidate_digest = _digest(candidate_payload)

    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','duplicate-preview','non-monotonic-version','rollback-lineage-mismatch','candidate-delta-limit-exceeded','candidate-id-reuse'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif human_approved:
        state = 'committed'
        _seen_sources.add(req.source_id)
        _seen_previews.add(req.preview_id)
    else:
        state = 'review-required'

    audit_digest = _digest({'source_id': req.source_id, 'candidate_digest': candidate_digest, 'delta': delta, 'state': state, 'reasons': reasons})
    return BaselineCommitDecision(state=state, candidate_delta=delta, candidate_digest=candidate_digest, reasons=reasons, audit_digest=audit_digest)

def reset_seen_for_tests() -> None:
    _seen_sources.clear(); _seen_previews.clear()
