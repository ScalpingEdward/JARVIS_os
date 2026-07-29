import hashlib
import json
from app.schemas.recovery_reliability_cross_consumer_adoption_consistency_v21_216 import CrossConsumerAdoptionConsistencyRequest, CrossConsumerAdoptionConsistencyDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def evaluate_adoption_consistency(req: CrossConsumerAdoptionConsistencyRequest, human_approved: bool = False) -> CrossConsumerAdoptionConsistencyDecision:
    reasons: list[str] = []
    expected = sorted(set(req.expected_consumers))
    by_consumer = {}
    receipt_nonces: set[str] = set()
    observation_nonces: set[str] = set()

    if req.risk_brain_hard_block: reasons.append('risk-brain-hard-block')
    if req.source_state != 'adopted' or not req.source_human_approved: reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources: reasons.append('duplicate-source')
    if not expected or len(expected) != len(req.expected_consumers): reasons.append('invalid-expected-consumers')

    for obs in req.observations:
        if obs.consumer_id in by_consumer: reasons.append('duplicate-consumer-observation')
        by_consumer[obs.consumer_id] = obs
        if obs.receipt_nonce in receipt_nonces: reasons.append('duplicate-receipt-nonce')
        receipt_nonces.add(obs.receipt_nonce)
        if obs.observation_nonce in observation_nonces: reasons.append('duplicate-observation-nonce')
        observation_nonces.add(obs.observation_nonce)

    if set(by_consumer) - set(expected): reasons.append('unexpected-consumer-observation')

    consistent, drifted = [], []
    for cid in expected:
        obs = by_consumer.get(cid)
        if obs is None:
            drifted.append(cid); reasons.append(f'missing-observation:{cid}'); continue
        age = (req.now - obs.observed_at).total_seconds()
        lineage_ok = obs.workspace_id == req.workspace_id and obs.baseline_id == req.baseline_id and obs.baseline_version == req.baseline_version and obs.baseline_digest == req.baseline_digest
        fresh = 0 <= age <= req.observation_ttl_seconds
        confidence_ok = obs.confidence >= req.min_confidence
        if obs.adopted and obs.healthy and lineage_ok and fresh and confidence_ok:
            consistent.append(cid)
        else:
            drifted.append(cid)
            if not lineage_ok: reasons.append(f'lineage-mismatch:{cid}')
            if not fresh: reasons.append(f'stale-or-future-observation:{cid}')
            if not obs.adopted: reasons.append(f'not-adopted:{cid}')
            if not obs.healthy: reasons.append(f'unhealthy:{cid}')
            if not confidence_ok: reasons.append(f'low-confidence:{cid}')

    score = round(len(consistent) / len(expected), 4) if expected else 0.0
    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-expected-consumers','duplicate-consumer-observation','duplicate-receipt-nonce','duplicate-observation-nonce','unexpected-consumer-observation'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif drifted:
        state = 'drift-detected'
    elif human_approved:
        state = 'consistent'; _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'consistent': consistent, 'drifted': drifted, 'score': score, 'state': state, 'reasons': reasons}
    return CrossConsumerAdoptionConsistencyDecision(state=state, consistency_score=score, consistent_consumers=consistent, drifted_consumers=drifted, drift_reasons=reasons, audit_digest=_digest(payload))

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
