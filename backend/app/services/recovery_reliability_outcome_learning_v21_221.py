import hashlib
import json
from app.schemas.recovery_reliability_outcome_learning_v21_221 import RecoveryOutcomeLearningRequest, RecoveryOutcomeLearningDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_outcome_learning(req: RecoveryOutcomeLearningRequest, human_approved: bool = False) -> RecoveryOutcomeLearningDecision:
    reasons: list[str] = []
    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'closed' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')

    learning_score = round(
        0.35 * req.stability_score
        + 0.20 * req.mean_confidence
        + 0.25 * req.mean_recovery_quality
        + 0.20 * (1.0 - req.residual_risk), 4
    )
    if learning_score < req.min_learning_score:
        reasons.append('learning-score-below-threshold')

    adjustment = round(req.requested_feedback_adjustment, 4)
    if abs(adjustment) > 0.05:
        reasons.append('feedback-adjustment-limit-exceeded')

    blocking = {'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source', 'feedback-adjustment-limit-exceeded'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif 'learning-score-below-threshold' in reasons or not human_approved:
        state = 'review-required'
    else:
        state = 'approved-feedback'
        _seen_sources.add(req.source_id)

    feedback_payload = {
        'workspace_id': req.workspace_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'recovery_sequence_digest': req.recovery_sequence_digest,
        'learning_score': learning_score,
        'feedback_adjustment': adjustment,
    }
    feedback_digest = _digest(feedback_payload)
    audit_digest = _digest({
        'source_id': req.source_id,
        'feedback_digest': feedback_digest,
        'state': state,
        'reasons': reasons,
    })
    return RecoveryOutcomeLearningDecision(
        state=state,
        learning_score=learning_score,
        approved_feedback_adjustment=adjustment if state == 'approved-feedback' else 0.0,
        reasons=reasons,
        feedback_digest=feedback_digest,
        audit_digest=audit_digest,
    )

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
