import hashlib
import json
from app.schemas.recovery_reliability_feedback_impact_preview_v21_212 import FeedbackImpactPreviewRequest, FeedbackImpactPreviewDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def simulate_feedback_impact(req: FeedbackImpactPreviewRequest, human_approved: bool = False) -> FeedbackImpactPreviewDecision:
    reasons: list[str] = []
    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'approved-feedback' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')

    candidate = round(req.current_value + req.feedback_adjustment, 6)
    if not 0.0 <= candidate <= 1.0: reasons.append('candidate-out-of-range')
    if abs(req.feedback_adjustment) > 0.05: reasons.append('feedback-adjustment-limit-exceeded')
    if req.blast_radius > req.max_blast_radius: reasons.append('blast-radius-limit-exceeded')
    if req.residual_risk > req.max_residual_risk: reasons.append('residual-risk-limit-exceeded')

    impacts = [req.score_impact, req.rank_impact, req.failover_impact, req.recovery_readiness_impact]
    aggregate_impact = round(sum(impacts) / len(impacts), 4)

    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','candidate-out-of-range','feedback-adjustment-limit-exceeded'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif reasons:
        state = 'review-required'
    elif human_approved:
        state = 'approved-preview'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    preview_payload = {
        'workspace_id': req.workspace_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'current_value': req.current_value,
        'feedback_adjustment': req.feedback_adjustment,
        'candidate_value': candidate,
        'score_impact': req.score_impact,
        'rank_impact': req.rank_impact,
        'failover_impact': req.failover_impact,
        'recovery_readiness_impact': req.recovery_readiness_impact,
        'blast_radius': req.blast_radius,
        'residual_risk': req.residual_risk,
    }
    preview_digest = _digest(preview_payload)
    audit_digest = _digest({'source_id': req.source_id, 'preview_digest': preview_digest, 'aggregate_impact': aggregate_impact, 'state': state, 'reasons': reasons})
    return FeedbackImpactPreviewDecision(state=state, candidate_value=candidate, aggregate_impact=aggregate_impact, reasons=reasons, preview_digest=preview_digest, audit_digest=audit_digest)

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
