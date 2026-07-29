import hashlib
import json
from app.schemas.recovery_reliability_baseline_commit_v21_203 import BaselineCommitRequest, BaselineCommitDecision

_seen_sources: set[str] = set()
_seen_previews: set[str] = set()

def _digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()

def evaluate_baseline_commit(req: BaselineCommitRequest, human_approved: bool = False) -> BaselineCommitDecision:
    reasons: list[str] = []
    candidate_delta = round(req.candidate_value - req.previous_value, 8)

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'approved-preview' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if req.preview_id in _seen_previews:
        reasons.append('duplicate-preview')
    if req.proposed_version != req.previous_version + 1:
        reasons.append('non-monotone-version')
    if abs(req.candidate_value - req.preview_candidate_value) > 1e-9:
        reasons.append('preview-candidate-mismatch')
    if abs(candidate_delta) > req.max_candidate_delta + 1e-12:
        reasons.append('candidate-delta-limit-exceeded')
    if req.rollback_version != req.previous_version:
        reasons.append('rollback-version-mismatch')
    if abs(req.rollback_value - req.previous_value) > 1e-9:
        reasons.append('rollback-value-mismatch')

    candidate_payload = {
        'workspace_id': req.workspace_id,
        'preview_id': req.preview_id,
        'baseline_id': req.baseline_id,
        'previous_version': req.previous_version,
        'proposed_version': req.proposed_version,
        'previous_value': req.previous_value,
        'candidate_value': req.candidate_value,
        'previous_baseline_digest': req.previous_baseline_digest,
        'preview_digest': req.preview_digest,
        'rollback_version': req.rollback_version,
        'rollback_value': req.rollback_value,
    }
    candidate_baseline_digest = _digest(candidate_payload)

    if reasons:
        state = 'blocked'
    elif human_approved:
        state = 'committed'
        _seen_sources.add(req.source_id)
        _seen_previews.add(req.preview_id)
    else:
        state = 'review-required'

    audit_payload = {
        **candidate_payload,
        'candidate_delta': candidate_delta,
        'candidate_baseline_digest': candidate_baseline_digest,
        'state': state,
        'reasons': reasons,
    }
    return BaselineCommitDecision(
        state=state,
        baseline_id=req.baseline_id,
        proposed_version=req.proposed_version,
        previous_value=req.previous_value,
        candidate_value=req.candidate_value,
        candidate_delta=candidate_delta,
        rollback_version=req.rollback_version,
        rollback_value=req.rollback_value,
        candidate_baseline_digest=candidate_baseline_digest,
        reasons=reasons,
        audit_digest=_digest(audit_payload),
    )

def reset_seen_for_tests() -> None:
    _seen_sources.clear()
    _seen_previews.clear()
