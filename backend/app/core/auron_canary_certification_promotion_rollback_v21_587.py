from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import CanaryReconciliationStopService
from app.core.auron_controlled_canary_execution_boundary_v21_585 import ControlledCanaryExecutionService

CanaryOutcome = Literal['promote','rollback','hold']


class CanaryCertificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanaryCertificationEvidence:
    activation_id: str
    vertical: str
    provider_id: str
    operator_id: str
    all_submitted_actions_reconciled: bool
    any_stop_required: bool
    any_stop_failed: bool
    kill_switch_available: bool
    reconciliation_available: bool
    rollback_control_available: bool
    provider_health_green: bool
    policy_green: bool
    operator_promotion_approved: bool
    requested_outcome: CanaryOutcome


@dataclass(frozen=True)
class CanaryCertificationDecision:
    certification_id: str
    activation_id: str
    vertical: str
    provider_id: str
    outcome: CanaryOutcome
    certified: bool
    blockers: tuple[str, ...]
    unrestricted_production_enabled_by_decision: bool
    rollback_required: bool
    evidence_hash: str


class CanaryCertificationPromotionRollbackService:
    """F4 certification and promotion/rollback decision.

    Promotion is an authorization artifact only. This layer never enables unrestricted production
    transport. Any stop, failed stop, unreconciled action, health/policy drift or missing safety
    controls forces rollback/hold semantics.
    """

    def __init__(self, executions: ControlledCanaryExecutionService,
                 reconciliation: CanaryReconciliationStopService) -> None:
        self.executions = executions
        self.reconciliation = reconciliation

    @staticmethod
    def _hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def evaluate(self, evidence: CanaryCertificationEvidence) -> CanaryCertificationDecision:
        if evidence.requested_outcome not in {'promote','rollback','hold'}:
            raise CanaryCertificationError('invalid canary outcome')
        blockers: list[str] = []
        executions = self.executions.list_for_activation(evidence.activation_id)
        submitted = tuple(e for e in executions if e.state == 'provider-submitted')
        if not submitted:
            blockers.append('submitted-canary-actions-required')
        actual_all_reconciled = bool(submitted) and all(
            (r := self.reconciliation.get_by_execution(e.execution_id)) is not None and r.progression_authorized
            for e in submitted
        )
        actual_any_stop = any(
            (r := self.reconciliation.get_by_execution(e.execution_id)) is not None and r.stop_required
            for e in submitted
        )
        actual_any_stop_failed = any(
            (r := self.reconciliation.get_by_execution(e.execution_id)) is not None and r.state == 'stop-failed'
            for e in submitted
        )

        if evidence.all_submitted_actions_reconciled != actual_all_reconciled:
            blockers.append('reconciliation-evidence-mismatch')
        if evidence.any_stop_required != actual_any_stop:
            blockers.append('stop-evidence-mismatch')
        if evidence.any_stop_failed != actual_any_stop_failed:
            blockers.append('stop-failure-evidence-mismatch')
        if not actual_all_reconciled:
            blockers.append('all-submitted-actions-must-reconcile')
        if actual_any_stop:
            blockers.append('canary-stop-occurred')
        if actual_any_stop_failed:
            blockers.append('canary-stop-failed')
        if not evidence.kill_switch_available:
            blockers.append('kill-switch-required')
        if not evidence.reconciliation_available:
            blockers.append('reconciliation-required')
        if not evidence.rollback_control_available:
            blockers.append('rollback-control-required')
        if not evidence.provider_health_green:
            blockers.append('provider-health-not-green')
        if not evidence.policy_green:
            blockers.append('policy-not-green')
        if evidence.requested_outcome == 'promote' and not evidence.operator_promotion_approved:
            blockers.append('explicit-promotion-approval-required')

        forced_rollback = actual_any_stop or actual_any_stop_failed or not actual_all_reconciled
        if forced_rollback:
            outcome: CanaryOutcome = 'rollback'
        elif evidence.requested_outcome == 'promote' and not blockers:
            outcome = 'promote'
        elif evidence.requested_outcome == 'rollback':
            outcome = 'rollback'
        else:
            outcome = 'hold'

        canonical = {
            'activation_id': evidence.activation_id,
            'vertical': evidence.vertical,
            'provider_id': evidence.provider_id,
            'operator_id': evidence.operator_id,
            'submitted_execution_ids': [e.execution_id for e in submitted],
            'actual_all_reconciled': actual_all_reconciled,
            'actual_any_stop': actual_any_stop,
            'actual_any_stop_failed': actual_any_stop_failed,
            'kill_switch_available': evidence.kill_switch_available,
            'reconciliation_available': evidence.reconciliation_available,
            'rollback_control_available': evidence.rollback_control_available,
            'provider_health_green': evidence.provider_health_green,
            'policy_green': evidence.policy_green,
            'operator_promotion_approved': evidence.operator_promotion_approved,
            'requested_outcome': evidence.requested_outcome,
        }
        evidence_hash = self._hash(canonical)
        certification_id = 'canary-cert-' + self._hash({'activation_id': evidence.activation_id, 'evidence_hash': evidence_hash})[:24]
        certified = outcome in {'promote','rollback'} and (not blockers or outcome == 'rollback')
        return CanaryCertificationDecision(
            certification_id=certification_id,
            activation_id=evidence.activation_id,
            vertical=evidence.vertical,
            provider_id=evidence.provider_id,
            outcome=outcome,
            certified=certified,
            blockers=tuple(dict.fromkeys(blockers)),
            unrestricted_production_enabled_by_decision=False,
            rollback_required=(outcome == 'rollback'),
            evidence_hash=evidence_hash,
        )

    def require_promotion_authorized(self, decision: CanaryCertificationDecision) -> CanaryCertificationDecision:
        if not decision.certified or decision.outcome != 'promote':
            raise CanaryCertificationError('canary is not certified for promotion')
        if decision.unrestricted_production_enabled_by_decision:
            raise CanaryCertificationError('F4 may not enable unrestricted production transport')
        return decision
