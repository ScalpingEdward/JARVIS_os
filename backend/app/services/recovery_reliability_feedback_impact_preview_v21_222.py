import hashlib
import json
from app.schemas.recovery_reliability_feedback_impact_preview_v21_222 import FeedbackImpactSimulationRequest, FeedbackImpactSimulationDecision

_seen_sources: set[str] = set()

def _clamp(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 4)

def _digest(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def simulate_feedback_impact(req: FeedbackImpactSimulationRequest, human_approved: bool = False) -> FeedbackImpactSimulationDecision:
    reasons: list[str] = []
    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'approved-feedback' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if req.blast_radius > req.max_blast_radius:
        reasons.append('blast-radius-limit-exceeded')
    if req.residual_risk > req.max_residual_risk:
        reasons.append('residual-risk-limit-exceeded')

    candidate_value = _clamp(req.current_value + req.feedback_adjustment)
    projected_score = _clamp(req.current_score + req.projected_score_delta)
    projected_rank = max(1, req.current_rank + req.projected_rank_delta)
    projected_failover = _clamp(req.current_failover_readiness + req.projected_failover_delta)
    projected_recovery = _clamp(req.current_recovery_readiness + req.projected_recovery_delta)

    blocking = {'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source'}
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
        'recovery_sequence_digest': req.recovery_sequence_digest,
        'candidate_value': candidate_value,
        'projected_score': projected_score,
        'projected_rank': projected_rank,
        'projected_failover_readiness': projected_failover,
        'projected_recovery_readiness': projected_recovery,
        'blast_radius': req.blast_radius,
        'residual_risk': req.residual_risk,
    }
    preview_digest = _digest(preview_payload)
    audit_digest = _digest({'source_id': req.source_id, 'state': state, 'reasons': reasons, 'preview_digest': preview_digest})
    return FeedbackImpactSimulationDecision(
        state=state,
        candidate_value=candidate_value,
        projected_score=projected_score,
        projected_rank=projected_rank,
        projected_failover_readiness=projected_failover,
        projected_recovery_readiness=projected_recovery,
        reasons=reasons,
        preview_digest=preview_digest,
        audit_digest=audit_digest,
    )

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
