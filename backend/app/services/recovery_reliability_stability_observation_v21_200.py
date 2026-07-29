import hashlib
import json
from app.schemas.recovery_reliability_stability_observation_v21_200 import StabilityObservationRequest, StabilityObservationDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def evaluate_stability(req: StabilityObservationRequest, human_approved: bool = False) -> StabilityObservationDecision:
    reasons: list[str] = []
    expected = sorted(set(req.expected_consumers))
    by_consumer = {}

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'completed' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if not expected or len(expected) != len(req.expected_consumers):
        reasons.append('invalid-expected-consumers')

    for obs in req.observations:
        if obs.consumer_id in by_consumer:
            reasons.append('duplicate-consumer-observation')
        by_consumer[obs.consumer_id] = obs

    unexpected = sorted(set(by_consumer) - set(expected))
    if unexpected:
        reasons.append('unexpected-consumer-observation')

    scores: list[float] = []
    degraded: list[str] = []
    observed: list[str] = []
    for consumer_id in expected:
        obs = by_consumer.get(consumer_id)
        if obs is None:
            degraded.append(consumer_id)
            reasons.append(f'missing-observation:{consumer_id}')
            continue
        observed.append(consumer_id)
        age = (req.now - obs.observed_at).total_seconds()
        lineage_ok = obs.workspace_id == req.workspace_id and obs.baseline_id == req.baseline_id and obs.baseline_version == req.baseline_version and obs.baseline_digest == req.baseline_digest
        fresh = 0 <= age <= req.observation_ttl_seconds
        score = round((float(obs.healthy) + float(obs.dependency_satisfied) + obs.latency_quality + obs.error_quality + obs.confidence) / 5.0, 4)
        scores.append(score)
        if not lineage_ok:
            degraded.append(consumer_id); reasons.append(f'lineage-mismatch:{consumer_id}')
        if not fresh:
            degraded.append(consumer_id); reasons.append(f'stale-or-future-observation:{consumer_id}')
        if not obs.healthy:
            degraded.append(consumer_id); reasons.append(f'unhealthy:{consumer_id}')
        if not obs.dependency_satisfied:
            degraded.append(consumer_id); reasons.append(f'dependency-unsatisfied:{consumer_id}')

    stability_score = round(sum(scores) / len(expected), 4) if expected and len(scores) == len(expected) else 0.0
    residual_risk = round(1.0 - stability_score, 4)
    degraded = sorted(set(degraded))
    if stability_score < req.min_stability_score:
        reasons.append('stability-score-below-threshold')
    if residual_risk > req.max_residual_risk:
        reasons.append('residual-risk-limit-exceeded')

    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-expected-consumers','duplicate-consumer-observation','unexpected-consumer-observation'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif degraded or stability_score < req.min_stability_score or residual_risk > req.max_residual_risk:
        state = 'degraded'
    elif human_approved:
        state = 'closed'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'observed': observed, 'degraded': degraded, 'stability_score': stability_score, 'residual_risk': residual_risk, 'state': state, 'reasons': reasons}
    return StabilityObservationDecision(state=state, stability_score=stability_score, residual_risk=residual_risk, observed_consumers=observed, degraded_consumers=degraded, reasons=reasons, audit_digest=_digest(payload))

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
