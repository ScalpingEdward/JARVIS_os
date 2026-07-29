import hashlib
import json

from app.schemas.recovery_reliability_stability_observation_v21_220 import (
    StabilityObservationDecision,
    StabilityObservationRequest,
)

_seen_sources: set[str] = set()


def _digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def evaluate_episode_stability(
    req: StabilityObservationRequest,
    human_approved: bool = False,
) -> StabilityObservationDecision:
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

    stable: list[str] = []
    degraded: list[str] = []
    scores: list[float] = []

    for consumer_id in expected:
        obs = by_consumer.get(consumer_id)
        if obs is None:
            degraded.append(consumer_id)
            reasons.append(f'missing-observation:{consumer_id}')
            continue

        lineage_ok = (
            obs.workspace_id == req.workspace_id
            and obs.baseline_id == req.baseline_id
            and obs.baseline_version == req.baseline_version
            and obs.baseline_digest == req.baseline_digest
            and obs.recovery_sequence_digest == req.recovery_sequence_digest
        )
        age = (req.now - obs.observed_at).total_seconds()
        fresh = 0 <= age <= req.observation_ttl_seconds
        score = round(
            0.25 * obs.latency_quality
            + 0.25 * obs.error_quality
            + 0.25 * obs.recovery_quality
            + 0.25 * obs.confidence,
            4,
        )
        scores.append(score)

        hard_degraded = not obs.healthy or not obs.dependency_satisfied
        if lineage_ok and fresh and not hard_degraded and score >= req.min_consumer_stability_score:
            stable.append(consumer_id)
        else:
            degraded.append(consumer_id)
            if not lineage_ok:
                reasons.append(f'lineage-or-sequence-mismatch:{consumer_id}')
            if not fresh:
                reasons.append(f'stale-or-future-observation:{consumer_id}')
            if not obs.healthy:
                reasons.append(f'unhealthy:{consumer_id}')
            if not obs.dependency_satisfied:
                reasons.append(f'dependency-unsatisfied:{consumer_id}')
            if score < req.min_consumer_stability_score:
                reasons.append(f'low-consumer-stability-score:{consumer_id}')

    episode_score = round(sum(scores) / len(expected), 4) if expected else 0.0
    residual_risk = round(1.0 - episode_score, 4)

    if episode_score < req.min_episode_stability_score:
        reasons.append('episode-stability-below-threshold')
    if residual_risk > req.max_residual_risk:
        reasons.append('residual-risk-limit-exceeded')

    blocking = {
        'risk-brain-hard-block',
        'invalid-source-admission',
        'duplicate-source',
        'invalid-expected-consumers',
        'duplicate-consumer-observation',
        'unexpected-consumer-observation',
    }
    if any(reason in blocking for reason in reasons):
        state = 'blocked'
    elif degraded or episode_score < req.min_episode_stability_score or residual_risk > req.max_residual_risk:
        state = 'degraded'
    elif human_approved:
        state = 'closed'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    payload = {
        'source_id': req.source_id,
        'workspace_id': req.workspace_id,
        'baseline_id': req.baseline_id,
        'baseline_version': req.baseline_version,
        'baseline_digest': req.baseline_digest,
        'recovery_sequence_digest': req.recovery_sequence_digest,
        'stable': stable,
        'degraded': degraded,
        'episode_stability_score': episode_score,
        'residual_risk': residual_risk,
        'state': state,
        'reasons': reasons,
    }
    return StabilityObservationDecision(
        state=state,
        episode_stability_score=episode_score,
        residual_risk=residual_risk,
        stable_consumers=stable,
        degraded_consumers=degraded,
        reasons=reasons,
        audit_digest=_digest(payload),
    )


def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
