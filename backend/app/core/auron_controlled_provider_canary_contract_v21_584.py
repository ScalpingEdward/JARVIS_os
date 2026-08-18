from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.core.auron_production_readiness_canary_gate_v21_583 import CanaryReadinessDecision


class ControlledProviderCanaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanaryActivationRequest:
    readiness_decision: CanaryReadinessDecision
    operator_id: str
    requested_actions: int
    scope: str
    kill_switch_active: bool
    reconciliation_ready: bool
    stop_control_ready: bool
    transport_enabled_before_request: bool = False


@dataclass(frozen=True)
class CanaryActivationDecision:
    activation_id: str
    decision_id: str
    vertical: str
    provider_id: str
    operator_id: str
    scope: str
    action_allowance: int
    activation_authorized: bool
    blockers: tuple[str, ...]
    live_transport_enabled_by_contract: bool
    request_hash: str


class ControlledProviderCanaryContract:
    """F1 authorization contract for one bounded provider canary.

    This module deliberately does not expose provider transport. A passing decision is only an
    authorization artifact for a later execution layer. It cannot switch a provider live.
    """

    @staticmethod
    def _hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def evaluate(self, request: CanaryActivationRequest) -> CanaryActivationDecision:
        d = request.readiness_decision
        blockers: list[str] = []
        if not d.ready_for_canary_activation:
            blockers.append('E4-readiness-required')
        if d.live_transport_enabled_by_gate:
            blockers.append('invalid-E4-transport-state')
        if not request.operator_id.strip():
            blockers.append('operator-id-required')
        if not request.scope.strip():
            blockers.append('explicit-scope-required')
        if not 1 <= request.requested_actions <= d.max_canary_actions:
            blockers.append('requested-actions-exceed-E4-bound')
        if not request.kill_switch_active:
            blockers.append('kill-switch-must-be-active')
        if not request.reconciliation_ready:
            blockers.append('reconciliation-must-be-ready')
        if not request.stop_control_ready:
            blockers.append('stop-control-must-be-ready')
        if request.transport_enabled_before_request:
            blockers.append('transport-must-be-disabled-before-explicit-activation')

        canonical = {
            'decision_id': d.decision_id,
            'vertical': d.vertical,
            'provider_id': d.provider_id,
            'operator_id': request.operator_id.strip(),
            'scope': request.scope.strip(),
            'requested_actions': request.requested_actions,
            'evidence_hash': d.evidence_hash,
        }
        request_hash = self._hash(canonical)
        activation_id = 'canary-auth-' + request_hash[:24]
        return CanaryActivationDecision(
            activation_id=activation_id,
            decision_id=d.decision_id,
            vertical=d.vertical,
            provider_id=d.provider_id,
            operator_id=request.operator_id.strip(),
            scope=request.scope.strip(),
            action_allowance=request.requested_actions,
            activation_authorized=not blockers,
            blockers=tuple(blockers),
            live_transport_enabled_by_contract=False,
            request_hash=request_hash,
        )

    def require_authorized(self, decision: CanaryActivationDecision) -> CanaryActivationDecision:
        if not decision.activation_authorized:
            raise ControlledProviderCanaryError('canary activation is not authorized: ' + ';'.join(decision.blockers))
        if decision.live_transport_enabled_by_contract:
            raise ControlledProviderCanaryError('F1 contract may not enable live transport')
        return decision
