import hashlib
import json
from app.schemas.recovery_reliability_adoption_consistency_v21_206 import AdoptionConsistencyRequest, AdoptionConsistencyDecision

_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def evaluate_adoption_consistency(req: AdoptionConsistencyRequest, human_approved: bool = False) -> AdoptionConsistencyDecision:
    drift_reasons: list[str] = []
    expected = sorted(set(req.expected_consumers))
    by_consumer = {}
    nonces: set[str] = set()

    if req.risk_brain_hard_block:
        drift_reasons.append('risk-brain-hard-block')
    if req.source_state != 'adopted' or not req.source_human_approved:
        drift_reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        drift_reasons.append('duplicate-source')
    if not expected or len(expected) != len(req.expected_consumers):
        drift_reasons.append('invalid-expected-consumers')

    for obs in req.observations:
        if obs.consumer_id in by_consumer:
            drift_reasons.append('duplicate-consumer-observation')
        by_consumer[obs.consumer_id] = obs
        if obs.receipt_nonce in nonces:
            drift_reasons.append('duplicate-observation-nonce')
        nonces.add(obs.receipt_nonce)

    if set(by_consumer) - set(expected):
        drift_reasons.append('unexpected-consumer-observation')

    consistent, drifted = [], []
    for cid in expected:
        obs = by_consumer.get(cid)
        reasons = []
        if obs is None:
            reasons.append('missing-observation')
        else:
            age = (req.now - obs.observed_at).total_seconds()
            lineage_ok = obs.workspace_id == req.workspace_id and obs.baseline_id == req.baseline_id and obs.baseline_version == req.baseline_version and obs.baseline_digest == req.baseline_digest
            if not lineage_ok: reasons.append('lineage-mismatch')
            if not (0 <= age <= req.observation_ttl_seconds): reasons.append('stale-or-future-observation')
            if not obs.adopted: reasons.append('not-adopted')
            if not obs.healthy: reasons.append('unhealthy')
            if obs.confidence < req.min_confidence: reasons.append('low-confidence')
        if reasons:
            drifted.append(cid)
            drift_reasons.extend(f'{r}:{cid}' for r in reasons)
        else:
            consistent.append(cid)

    score = round(len(consistent) / len(expected), 4) if expected else 0.0
    blocking = {'risk-brain-hard-block','invalid-source-admission','duplicate-source','invalid-expected-consumers','duplicate-consumer-observation','duplicate-observation-nonce','unexpected-consumer-observation'}
    if any(r in blocking for r in drift_reasons):
        state = 'blocked'
    elif drifted:
        state = 'drift-detected'
    elif human_approved:
        state = 'consistent'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'consistent': consistent, 'drifted': drifted, 'score': score, 'state': state, 'reasons': drift_reasons}
    return AdoptionConsistencyDecision(state=state, consistency_score=score, consistent_consumers=consistent, drifted_consumers=drifted, drift_reasons=drift_reasons, audit_digest=_digest(payload))

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
