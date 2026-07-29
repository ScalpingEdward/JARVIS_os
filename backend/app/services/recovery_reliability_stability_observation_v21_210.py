import hashlib
import json
from app.schemas.recovery_reliability_stability_observation_v21_210 import StabilityObservationRequest, StabilityObservationDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def evaluate_stability(req: StabilityObservationRequest, human_approved: bool = False) -> StabilityObservationDecision:
    reasons: list[str] = []
    expected = sorted(set(req.expected_consumers))
    by_consumer = {}

    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'completed' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')
    if not expected or len(expected) != len(req.expected_consumers): reasons.append('invalid-expected-consumers')

    for obs in req.observations:
        if obs.consumer_id in by_consumer: reasons.append('duplicate-consumer-observation')
        by_consumer[obs.consumer_id] = obs
    if set(by_consumer) - set(expected): reasons.append('unexpected-consumer-observation')

    stable, degraded, scores = [], [], []
    for cid in expected:
        o = by_consumer.get(cid)
        if o is None:
            degraded.append(cid); reasons.append(f'missing-observation:{cid}'); continue
        lineage_ok = o.workspace_id == req.workspace_id and o.baseline_id == req.baseline_id and o.baseline_version == req.baseline_version and o.baseline_digest == req.baseline_digest
        age = (req.now - o.observed_at).total_seconds()
        fresh = 0 <= age <= req.observation_ttl_seconds
        score = round(0.35 * o.latency_quality + 0.30 * o.error_quality + 0.35 * o.confidence, 4)
        scores.append(score)
        hard_degraded = not o.healthy or not o.dependency_satisfied
        if lineage_ok and fresh and not hard_degraded and score >= req.min_stability_score:
            stable.append(cid)
        else:
            degraded.append(cid)
            if not lineage_ok: reasons.append(f'lineage-mismatch:{cid}')
            if not fresh: reasons.append(f'stale-or-future-observation:{cid}')
            if not o.healthy: reasons.append(f'unhealthy:{cid}')
            if not o.dependency_satisfied: reasons.append(f'dependency-unsatisfied:{cid}')
            if score < req.min_stability_score: reasons.append(f'low-stability-score:{cid}')

    stability_score = round(sum(scores) / len(expected), 4) if expected else 0.0
    residual_risk = round(1.0 - stability_score, 4)
    if residual_risk > req.max_residual_risk: reasons.append('residual-risk-limit-exceeded')

    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-expected-consumers','duplicate-consumer-observation','unexpected-consumer-observation'}
    if any(r in blocking for r in reasons): state = 'blocked'
    elif degraded or stability_score < req.min_stability_score or residual_risk > req.max_residual_risk: state = 'degraded'
    elif human_approved:
        state = 'closed'; _seen_sources.add(req.source_id)
    else: state = 'review-required'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'stable': stable, 'degraded': degraded, 'stability_score': stability_score, 'residual_risk': residual_risk, 'state': state, 'reasons': reasons}
    return StabilityObservationDecision(state=state, stability_score=stability_score, residual_risk=residual_risk, stable_consumers=stable, degraded_consumers=degraded, reasons=reasons, audit_digest=_digest(payload))

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
