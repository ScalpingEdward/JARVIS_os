import hashlib
import json
from app.schemas.recovery_reliability_baseline_commit_v21_223 import BaselineCommitRequest, BaselineCommitDecision

_seen_sources: set[str] = set()
_seen_candidates: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_baseline_commit(req: BaselineCommitRequest, human_approved: bool = False) -> BaselineCommitDecision:
    reasons: list[str] = []
    delta = round(req.candidate_value - req.previous_value, 6)

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'approved-preview' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if req.candidate_baseline_id in _seen_candidates:
        reasons.append('candidate-id-reuse')
    if req.candidate_baseline_id == req.previous_baseline_id:
        reasons.append('candidate-id-must-differ')
    if req.candidate_baseline_version != req.previous_baseline_version + 1:
        reasons.append('non-monotonic-version')
    if abs(delta) > req.max_candidate_delta + 1e-9:
        reasons.append('candidate-delta-limit-exceeded')
    if req.rollback_baseline_id != req.previous_baseline_id or req.rollback_baseline_version != req.previous_baseline_version or req.rollback_baseline_digest != req.previous_baseline_digest:
        reasons.append('rollback-lineage-mismatch')
    if not req.preview_digest:
        reasons.append('missing-preview-digest')
    if not req.recovery_sequence_digest:
        reasons.append('missing-recovery-sequence-digest')

    candidate_payload = {
        'workspace_id': req.workspace_id,
        'candidate_baseline_id': req.candidate_baseline_id,
        'candidate_baseline_version': req.candidate_baseline_version,
        'candidate_value': req.candidate_value,
        'previous_baseline_id': req.previous_baseline_id,
        'previous_baseline_version': req.previous_baseline_version,
        'previous_baseline_digest': req.previous_baseline_digest,
        'preview_digest': req.preview_digest,
        'rollback_baseline_id': req.rollback_baseline_id,
        'rollback_baseline_version': req.rollback_baseline_version,
        'rollback_baseline_digest': req.rollback_baseline_digest,
        'recovery_sequence_digest': req.recovery_sequence_digest,
    }
    candidate_digest = _digest(candidate_payload)

    blocking = {
        'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source', 'candidate-id-reuse',
        'candidate-id-must-differ', 'non-monotonic-version', 'rollback-lineage-mismatch',
        'missing-preview-digest', 'missing-recovery-sequence-digest'
    }
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif 'candidate-delta-limit-exceeded' in reasons:
        state = 'review-required'
    elif human_approved:
        state = 'committed'
        _seen_sources.add(req.source_id)
        _seen_candidates.add(req.candidate_baseline_id)
    else:
        state = 'review-required'

    audit_digest = _digest({
        'source_id': req.source_id,
        'workspace_id': req.workspace_id,
        'candidate_digest': candidate_digest,
        'candidate_delta': delta,
        'state': state,
        'reasons': reasons,
    })
    return BaselineCommitDecision(
        state=state,
        candidate_baseline_id=req.candidate_baseline_id,
        candidate_baseline_version=req.candidate_baseline_version,
        candidate_value=req.candidate_value,
        candidate_delta=delta,
        candidate_digest=candidate_digest,
        reasons=reasons,
        audit_digest=audit_digest,
    )

def reset_seen_for_tests() -> None:
    _seen_sources.clear()
    _seen_candidates.clear()
