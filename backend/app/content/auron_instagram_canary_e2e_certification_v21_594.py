from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.content.auron_instagram_draft_preview_canary_adapter_v21_593 import InstagramDraftPreviewCanaryAdapter
from app.core.auron_canary_certification_promotion_rollback_v21_587 import (
    CanaryCertificationEvidence,
    CanaryCertificationPromotionRollbackService,
)
from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import CanaryReconciliationStopService
from app.core.auron_controlled_canary_execution_boundary_v21_585 import (
    CanaryExecutionRequest,
    ControlledCanaryExecutionService,
)
from app.core.auron_controlled_provider_canary_contract_v21_584 import (
    CanaryActivationRequest,
    ControlledProviderCanaryContract,
)


class InstagramCanaryE2ECertificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstagramCanaryE2ERequest:
    readiness_decision: object
    operator_id: str
    scope: str
    action_key: str
    payload: dict
    kill_switch_active: bool = True
    reconciliation_ready: bool = True
    stop_control_ready: bool = True
    provider_health_green: bool = True
    policy_green: bool = True
    operator_promotion_approved: bool = True


@dataclass(frozen=True)
class InstagramCanaryE2EResult:
    activation_id: str
    execution_id: str
    reconciliation_id: str
    certification_id: str
    execution_state: str
    reconciliation_state: str
    certification_outcome: str
    certified: bool
    provider_write_enabled: bool
    public_publish_enabled: bool
    network_transport_enabled: bool
    production_transport_enabled: bool


class InstagramCanaryE2ECertificationHarness:
    """G7 wires F1 -> F2 -> G6 -> F3 -> F4 for Instagram draft preview.

    Certification proves the provider-specific chain while preserving the G6 safety invariant:
    local side-effect-free preview only, with no public publish, provider write, network or
    production transport.
    """

    def __init__(self, root: str | Path) -> None:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self.adapter = InstagramDraftPreviewCanaryAdapter(root / 'adapter.db')
        self.contract = ControlledProviderCanaryContract()
        self.executions = ControlledCanaryExecutionService(root / 'executions.db', transport=self.adapter)
        self.reconciliation = CanaryReconciliationStopService(
            root / 'reconciliation.db', self.executions, reader=self.adapter, stopper=self.adapter
        )
        self.certification = CanaryCertificationPromotionRollbackService(self.executions, self.reconciliation)

    def run(self, request: InstagramCanaryE2ERequest) -> InstagramCanaryE2EResult:
        descriptor = self.adapter.descriptor()
        readiness = request.readiness_decision
        if getattr(readiness, 'vertical', None) != descriptor.vertical:
            raise InstagramCanaryE2ECertificationError('readiness vertical must match instagram adapter')
        if getattr(readiness, 'provider_id', None) != descriptor.provider_id:
            raise InstagramCanaryE2ECertificationError('readiness provider must match instagram adapter')
        if request.action_key not in descriptor.allowed_actions:
            raise InstagramCanaryE2ECertificationError('action not allowed by instagram canary adapter')
        if (
            not descriptor.side_effect_free
            or descriptor.provider_write_enabled
            or descriptor.public_publish_enabled
            or descriptor.network_transport_enabled
            or descriptor.production_transport_enabled
        ):
            raise InstagramCanaryE2ECertificationError('G7 requires local side-effect-free disabled-transport adapter')

        auth = self.contract.evaluate(
            CanaryActivationRequest(
                readiness_decision=readiness,
                operator_id=request.operator_id,
                requested_actions=1,
                scope=request.scope,
                kill_switch_active=request.kill_switch_active,
                reconciliation_ready=request.reconciliation_ready,
                stop_control_ready=request.stop_control_ready,
                transport_enabled_before_request=False,
            )
        )
        self.contract.require_authorized(auth)

        execution = self.executions.execute(
            CanaryExecutionRequest(
                authorization=auth,
                action_key=request.action_key,
                payload=request.payload,
                kill_switch_active=request.kill_switch_active,
                reconciliation_ready=request.reconciliation_ready,
                stop_control_ready=request.stop_control_ready,
            )
        )
        if execution.state != 'provider-submitted':
            raise InstagramCanaryE2ECertificationError('instagram canary execution was not submitted')

        reconciliation = self.reconciliation.reconcile(
            execution,
            kill_switch_active=request.kill_switch_active,
            reconciliation_ready=request.reconciliation_ready,
            stop_control_ready=request.stop_control_ready,
        )

        decision = self.certification.evaluate(
            CanaryCertificationEvidence(
                activation_id=auth.activation_id,
                vertical=auth.vertical,
                provider_id=auth.provider_id,
                operator_id=request.operator_id,
                all_submitted_actions_reconciled=reconciliation.progression_authorized,
                any_stop_required=reconciliation.stop_required,
                any_stop_failed=reconciliation.state == 'stop-failed',
                kill_switch_available=request.kill_switch_active,
                reconciliation_available=request.reconciliation_ready,
                rollback_control_available=request.stop_control_ready,
                provider_health_green=request.provider_health_green,
                policy_green=request.policy_green,
                operator_promotion_approved=request.operator_promotion_approved,
                requested_outcome='promote',
            )
        )

        return InstagramCanaryE2EResult(
            activation_id=auth.activation_id,
            execution_id=execution.execution_id,
            reconciliation_id=reconciliation.reconciliation_id,
            certification_id=decision.certification_id,
            execution_state=execution.state,
            reconciliation_state=reconciliation.state,
            certification_outcome=decision.outcome,
            certified=decision.certified,
            provider_write_enabled=descriptor.provider_write_enabled,
            public_publish_enabled=descriptor.public_publish_enabled,
            network_transport_enabled=descriptor.network_transport_enabled,
            production_transport_enabled=descriptor.production_transport_enabled,
        )
