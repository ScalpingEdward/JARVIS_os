import hashlib
import json
from app.schemas.recovery_reliability_outcome_learning_v21_211 import OutcomeLearningRequest, OutcomeLearningDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def evaluate_outcome_learning(req: OutcomeLearningRequest, human_approved: bool = False) -> OutcomeLearningDecision:
    reasons: list[str] = []
    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'closed' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')

    learning_score = round(
        0.30 * req.stability_score
        + 0.25 * req.aggregate_confidence
        + 0.30 * req.recovery_quality
        + 0.15 * (1.0 - req.residual_risk),
        4,
    )

    if learning_score < req.min_learning_score:
        reasons.append('weak-learning-evidence')
    if req.residual_risk > req.max_residual_risk:
        reasons.append('residual-risk-limit-exceeded')

    centered = (learning_score - 0.5) * 0.10
    feedback_adjustment = round(max(-req.max_feedback_adjustment, min(req.max_feedback_adjustment, centered)), 4)
    candidate_feedback_value = round(req.current_baseline_value + feedback_adjustment, 4)
    if not 0.0 <= candidate_feedback_value <= 1.0:
        reasons.append('candidate-feedback-out-of-range')

    blocking = {'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source', 'candidate-feedback-out-of-range'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif reasons:
        state = 'review-required'
    elif human_approved:
        state = 'approved-feedback'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    feedback_payload = {
        'workspace_id': req.workspace_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'learning_score': learning_score,
        'feedback_adjustment': feedback_adjustment,
        'candidate_feedback_value': candidate_feedback_value,
    }
    feedback_digest = _digest(feedback_payload)
    audit_digest = _digest({'source_id': req.source_id, 'feedback_digest': feedback_digest, 'state': state, 'reasons': reasons})
    return OutcomeLearningDecision(
        state=state,
        learning_score=learning_score,
        feedback_adjustment=feedback_adjustment,
        candidate_feedback_value=candidate_feedback_value,
        reasons=reasons,
        feedback_digest=feedback_digest,
        audit_digest=audit_digest,
    )

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
