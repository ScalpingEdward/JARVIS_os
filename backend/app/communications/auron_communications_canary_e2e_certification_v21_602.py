from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.communications.auron_communications_draft_canary_adapter_v21_601 import CommunicationsDraftCanaryAdapter
from app.core.auron_canary_certification_promotion_rollback_v21_587 import (
    CanaryCertificationEvidence, CanaryCertificationPromotionRollbackService,
)
from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import CanaryReconciliationStopService
from app.core.auron_controlled_canary_execution_boundary_v21_585 import (
    CanaryExecutionRequest, ControlledCanaryExecutionService,
)
from app.core.auron_controlled_provider_canary_contract_v21_584 import (
    CanaryActivationRequest, ControlledProviderCanaryContract,
)


class CommunicationsCanaryE2ECertificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsCanaryE2ERequest:
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
class CommunicationsCanaryE2EResult:
    activation_id: str
    execution_id: str
    reconciliation_id: str
    certification_id: str
    execution_state: str
    reconciliation_state: str
    certification_outcome: str
    certified: bool
    outbound_send_enabled: bool
    provider_write_enabled: bool
    network_transport_enabled: bool
    production_transport_enabled: bool
    network_calls_made: int


class CommunicationsCanaryE2ECertificationHarness:
    """G15 wires F1 -> F2 -> G14 -> F3 -> F4 for Communications.

    Certification proves provider/action binding, idempotency and immediate reconciliation while
    preserving the zero-send local-draft invariant. A passing F4 artifact still cannot send a
    message or enable provider/network/production transport.
    """

    def __init__(self, root: str | Path) -> None:
        root=Path(root); root.mkdir(parents=True,exist_ok=True)
        self.adapter=CommunicationsDraftCanaryAdapter(root/'adapter.db')
        self.contract=ControlledProviderCanaryContract()
        self.executions=ControlledCanaryExecutionService(root/'executions.db',transport=self.adapter)
        self.reconciliation=CanaryReconciliationStopService(
            root/'reconciliation.db',self.executions,reader=self.adapter,stopper=self.adapter)
        self.certification=CanaryCertificationPromotionRollbackService(self.executions,self.reconciliation)

    def run(self, request: CommunicationsCanaryE2ERequest) -> CommunicationsCanaryE2EResult:
        descriptor=self.adapter.descriptor(); readiness=request.readiness_decision
        if getattr(readiness,'vertical',None) != descriptor.vertical:
            raise CommunicationsCanaryE2ECertificationError('readiness vertical must match communications adapter')
        if getattr(readiness,'provider_id',None) != descriptor.provider_id:
            raise CommunicationsCanaryE2ECertificationError('readiness provider must match communications adapter')
        if request.action_key not in descriptor.allowed_actions:
            raise CommunicationsCanaryE2ECertificationError('action not allowed by communications canary adapter')
        if (not descriptor.side_effect_free or descriptor.outbound_send_enabled or descriptor.provider_write_enabled
                or descriptor.network_transport_enabled or descriptor.production_transport_enabled):
            raise CommunicationsCanaryE2ECertificationError('G15 requires strict local zero-send disabled-transport adapter')

        auth=self.contract.evaluate(CanaryActivationRequest(
            readiness_decision=readiness,operator_id=request.operator_id,requested_actions=1,scope=request.scope,
            kill_switch_active=request.kill_switch_active,reconciliation_ready=request.reconciliation_ready,
            stop_control_ready=request.stop_control_ready,transport_enabled_before_request=False))
        self.contract.require_authorized(auth)

        execution=self.executions.execute(CanaryExecutionRequest(
            authorization=auth,action_key=request.action_key,payload=request.payload,
            kill_switch_active=request.kill_switch_active,reconciliation_ready=request.reconciliation_ready,
            stop_control_ready=request.stop_control_ready))
        if execution.state != 'provider-submitted':
            raise CommunicationsCanaryE2ECertificationError('communications canary execution was not submitted')

        reconciliation=self.reconciliation.reconcile(
            execution,kill_switch_active=request.kill_switch_active,
            reconciliation_ready=request.reconciliation_ready,stop_control_ready=request.stop_control_ready)

        decision=self.certification.evaluate(CanaryCertificationEvidence(
            activation_id=auth.activation_id,vertical=auth.vertical,provider_id=auth.provider_id,
            operator_id=request.operator_id,all_submitted_actions_reconciled=reconciliation.progression_authorized,
            any_stop_required=reconciliation.stop_required,any_stop_failed=reconciliation.state=='stop-failed',
            kill_switch_available=request.kill_switch_active,reconciliation_available=request.reconciliation_ready,
            rollback_control_available=request.stop_control_ready,provider_health_green=request.provider_health_green,
            policy_green=request.policy_green,operator_promotion_approved=request.operator_promotion_approved,
            requested_outcome='promote'))

        preview=self.adapter.preview(execution.provider_ref)
        if preview.get('outbound_send_performed') or preview.get('provider_write_performed') or preview.get('network_calls_made') != 0:
            raise CommunicationsCanaryE2ECertificationError('communications zero-send safety invariant violated')

        return CommunicationsCanaryE2EResult(
            auth.activation_id,execution.execution_id,reconciliation.reconciliation_id,decision.certification_id,
            execution.state,reconciliation.state,decision.outcome,decision.certified,
            descriptor.outbound_send_enabled,descriptor.provider_write_enabled,descriptor.network_transport_enabled,
            descriptor.production_transport_enabled,preview.get('network_calls_made',0))
