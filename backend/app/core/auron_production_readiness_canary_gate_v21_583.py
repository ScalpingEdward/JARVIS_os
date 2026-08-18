from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

Vertical = Literal['trading','instagram-content','communications','research','automation','files-documents']


class ProductionReadinessCanaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanaryReadinessEvidence:
    vertical: Vertical
    provider_id: str
    e1_governance_certified: bool
    e2_simulation_certified: bool
    e3_reconciliation_certified: bool
    provider_health_green: bool
    policy_gate_green: bool
    kill_switch_available: bool
    kill_switch_active: bool
    reconciliation_available: bool
    idempotency_available: bool
    operator_approved: bool
    canary_scope_explicit: bool
    max_canary_actions: int
    transport_configured: bool
    transport_enabled: bool
    rollback_or_stop_control_available: bool
    observed_at: str


@dataclass(frozen=True)
class CanaryReadinessDecision:
    decision_id: str
    vertical: Vertical
    provider_id: str
    ready_for_canary_activation: bool
    blockers: tuple[str, ...]
    max_canary_actions: int
    kill_switch_must_remain_available: bool
    live_transport_enabled_by_gate: bool
    decided_at: str
    evidence_hash: str


class ProductionReadinessCanaryGate:
    """E4 pre-activation gate.

    This gate only certifies whether a provider/vertical is eligible for a future controlled
    canary activation. It never enables transport itself. Transport must still be disabled
    while this decision is evaluated and any later activation must be explicit and separate.
    """

    ALLOWED_VERTICALS = frozenset({
        'trading','instagram-content','communications','research','automation','files-documents'
    })
    MAX_ACTIONS_LIMIT = 5

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def evaluate(self, evidence: CanaryReadinessEvidence, *, at: str | None = None) -> CanaryReadinessDecision:
        blockers: list[str] = []
        if evidence.vertical not in self.ALLOWED_VERTICALS:
            blockers.append('unknown-vertical')
        if not evidence.provider_id.strip():
            blockers.append('provider-id-required')
        if not evidence.e1_governance_certified:
            blockers.append('E1-governance-certification-required')
        if not evidence.e2_simulation_certified:
            blockers.append('E2-simulation-certification-required')
        if not evidence.e3_reconciliation_certified:
            blockers.append('E3-reconciliation-certification-required')
        if not evidence.provider_health_green:
            blockers.append('provider-health-not-green')
        if not evidence.policy_gate_green:
            blockers.append('policy-gate-not-green')
        if not evidence.kill_switch_available:
            blockers.append('kill-switch-required')
        if not evidence.kill_switch_active:
            blockers.append('kill-switch-must-be-active-before-canary-activation')
        if not evidence.reconciliation_available:
            blockers.append('reconciliation-required')
        if not evidence.idempotency_available:
            blockers.append('idempotency-required')
        if not evidence.operator_approved:
            blockers.append('explicit-operator-approval-required')
        if not evidence.canary_scope_explicit:
            blockers.append('explicit-canary-scope-required')
        if not 1 <= evidence.max_canary_actions <= self.MAX_ACTIONS_LIMIT:
            blockers.append('canary-action-limit-out-of-bounds')
        if not evidence.transport_configured:
            blockers.append('transport-configuration-required')
        if evidence.transport_enabled:
            blockers.append('transport-must-remain-disabled-during-E4-certification')
        if not evidence.rollback_or_stop_control_available:
            blockers.append('rollback-or-stop-control-required')

        canonical = {
            'vertical': evidence.vertical,
            'provider_id': evidence.provider_id.strip(),
            'e1': evidence.e1_governance_certified,
            'e2': evidence.e2_simulation_certified,
            'e3': evidence.e3_reconciliation_certified,
            'health': evidence.provider_health_green,
            'policy': evidence.policy_gate_green,
            'kill_switch_available': evidence.kill_switch_available,
            'kill_switch_active': evidence.kill_switch_active,
            'reconciliation': evidence.reconciliation_available,
            'idempotency': evidence.idempotency_available,
            'operator_approved': evidence.operator_approved,
            'scope_explicit': evidence.canary_scope_explicit,
            'max_canary_actions': evidence.max_canary_actions,
            'transport_configured': evidence.transport_configured,
            'transport_enabled': evidence.transport_enabled,
            'rollback_or_stop': evidence.rollback_or_stop_control_available,
            'observed_at': evidence.observed_at,
        }
        evidence_hash = self._hash(canonical)
        decision_id = 'canary-' + self._hash({'vertical': evidence.vertical,
                                               'provider_id': evidence.provider_id.strip(),
                                               'evidence_hash': evidence_hash})[:24]
        return CanaryReadinessDecision(
            decision_id=decision_id,
            vertical=evidence.vertical,
            provider_id=evidence.provider_id.strip(),
            ready_for_canary_activation=not blockers,
            blockers=tuple(blockers),
            max_canary_actions=evidence.max_canary_actions,
            kill_switch_must_remain_available=True,
            live_transport_enabled_by_gate=False,
            decided_at=at or self._now(),
            evidence_hash=evidence_hash,
        )

    def require_ready(self, decision: CanaryReadinessDecision) -> CanaryReadinessDecision:
        if not decision.ready_for_canary_activation:
            raise ProductionReadinessCanaryError('canary activation is not ready: ' + ';'.join(decision.blockers))
        if decision.live_transport_enabled_by_gate:
            raise ProductionReadinessCanaryError('E4 may not enable live transport')
        return decision
