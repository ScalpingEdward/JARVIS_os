import hashlib
import json
from app.schemas.recovery_reliability_adoption_drift_escalation_v21_197 import AdoptionDriftEscalationRequest, AdoptionDriftEscalationDecision

_SEVERITY_RISK = {'low': 0.15, 'medium': 0.35, 'high': 0.65, 'critical': 1.0}
_seen_sources: set[str] = set()

def _digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()

def evaluate_reconciliation_readiness(req: AdoptionDriftEscalationRequest, human_approved: bool = False) -> AdoptionDriftEscalationDecision:
    reasons: list[str] = []
    affected = sorted({c.consumer_id for c in req.affected_consumers})
    healthy = sorted(set(req.healthy_consumers))
    total = len(set(affected + healthy))
    blast_radius = round(len(affected) / total, 4) if total else 1.0

    if req.risk_brain_hard_block:
        reasons.append('risk-brain-hard-block')
    if req.source_state != 'drift-detected' or not req.source_human_approved:
        reasons.append('invalid-source-admission')
    if req.source_id in _seen_sources:
        reasons.append('duplicate-source')
    if not affected:
        reasons.append('no-affected-consumers')
    if set(affected) & set(healthy):
        reasons.append('consumer-set-overlap')
    if blast_radius > req.max_blast_radius:
        reasons.append('blast-radius-limit-exceeded')

    weighted = []
    for c in req.affected_consumers:
        weighted.append(_SEVERITY_RISK[c.severity] * (0.5 + 0.5 * c.confidence))
    residual_risk = round(sum(weighted) / max(len(weighted), 1), 4)
    if residual_risk > req.max_residual_risk:
        reasons.append('residual-risk-limit-exceeded')

    readiness_score = round(max(0.0, 1.0 - (0.55 * residual_risk + 0.45 * blast_radius)), 4)
    blocking = {'risk-brain-hard-block', 'invalid-source-admission', 'duplicate-source', 'no-affected-consumers', 'consumer-set-overlap'}
    if any(r in blocking for r in reasons):
        state = 'blocked'
    elif reasons:
        state = 'review-required'
    elif human_approved:
        state = 'reconciliation-ready'
        _seen_sources.add(req.source_id)
    else:
        state = 'review-required'

    payload = {'source_id': req.source_id, 'workspace_id': req.workspace_id, 'baseline_id': req.baseline_id, 'baseline_version': req.baseline_version, 'baseline_digest': req.baseline_digest, 'affected': affected, 'healthy': healthy, 'readiness_score': readiness_score, 'blast_radius': blast_radius, 'residual_risk': residual_risk, 'state': state, 'reasons': reasons}
    return AdoptionDriftEscalationDecision(state=state, readiness_score=readiness_score, blast_radius=blast_radius, residual_risk=residual_risk, affected_consumers=affected, healthy_consumers=healthy, reasons=reasons, audit_digest=_digest(payload))

def reset_seen_sources_for_tests() -> None:
    _seen_sources.clear()
