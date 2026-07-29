import hashlib
import json
from app.schemas.recovery_reliability_outcome_learning_v21_201 import RecoveryOutcomeLearningRequest, RecoveryOutcomeLearningDecision

_seen_sources: set[str] = set()

MIN_STABILITY = 0.85
MIN_CONFIDENCE = 0.80
MIN_RECOVERY_QUALITY = 0.80
MAX_RESIDUAL_RISK = 0.25
MAX_ADJUSTMENT = 0.05

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_outcome_learning(req: RecoveryOutcomeLearningRequest, human_approved: bool = False) -> RecoveryOutcomeLearningDecision:
    reasons: list[str] = []

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'closed' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')

    if req.stability_score < MIN_STABILITY:
        reasons.append('weak-stability-evidence')
    if req.aggregate_confidence < MIN_CONFIDENCE:
        reasons.append('weak-confidence-evidence')
    if req.recovery_quality < MIN_RECOVERY_QUALITY:
        reasons.append('weak-recovery-quality')
    if req.residual_risk > MAX_RESIDUAL_RISK:
        reasons.append('residual-risk-too-high')
    if abs(req.proposed_feedback_adjustment) > MAX_ADJUSTMENT:
        reasons.append('feedback-adjustment-limit-exceeded')

    learning_score = round(max(0.0, min(1.0,
        0.30 * req.stability_score
        + 0.25 * req.aggregate_confidence
        + 0.25 * req.recovery_quality
        + 0.20 * (1.0 - req.residual_risk)
    )), 4)

    bounded_adjustment = round(max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, req.proposed_feedback_adjustment)), 4)

    blocking = {'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif reasons:
        state = 'review-required'
    elif human_approved:
        state = 'approved-feedback'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    payload = {
        'source_id': req.source_id,
        'workspace_id': req.workspace_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'learning_score': learning_score,
        'bounded_feedback_adjustment': bounded_adjustment,
        'state': state,
        'reasons': reasons,
    }
    return RecoveryOutcomeLearningDecision(
        state=state,
        learning_score=learning_score,
        bounded_feedback_adjustment=bounded_adjustment,
        reasons=reasons,
        audit_digest=_digest(payload),
    )

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
