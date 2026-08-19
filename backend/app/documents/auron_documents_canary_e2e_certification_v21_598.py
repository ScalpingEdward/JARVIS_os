from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
from app.documents.auron_documents_readonly_canary_adapter_v21_597 import DocumentsReadonlyCanaryAdapter


class DocumentsCanaryE2ECertificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentsCanaryE2ERequest:
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
class DocumentsCanaryE2EResult:
    activation_id: str
    execution_id: str
    reconciliation_id: str
    certification_id: str
    execution_state: str
    reconciliation_state: str
    certification_outcome: str
    certified: bool
    read_only: bool
    mutation_enabled: bool
    delete_enabled: bool
    move_enabled: bool
    network_transport_enabled: bool
    production_transport_enabled: bool
    external_calls_made: int


class DocumentsCanaryE2ECertificationHarness:
    """G11 wires F1 -> F2 -> G10 -> F3 -> F4 for Files & Documents.

    Certification proves the complete provider-specific path while preserving the G10 invariant:
    metadata/version-preview only, zero content read, zero mutation and zero external transport.
    """

    def __init__(self, root: str | Path) -> None:
        root=Path(root); root.mkdir(parents=True,exist_ok=True)
        self.adapter=DocumentsReadonlyCanaryAdapter(root/'adapter.db')
        self.contract=ControlledProviderCanaryContract()
        self.executions=ControlledCanaryExecutionService(root/'executions.db',transport=self.adapter)
        self.reconciliation=CanaryReconciliationStopService(
            root/'reconciliation.db',self.executions,reader=self.adapter,stopper=self.adapter)
        self.certification=CanaryCertificationPromotionRollbackService(self.executions,self.reconciliation)

    def run(self, request: DocumentsCanaryE2ERequest) -> DocumentsCanaryE2EResult:
        descriptor=self.adapter.descriptor(); readiness=request.readiness_decision
        if getattr(readiness,'vertical',None) != descriptor.vertical:
            raise DocumentsCanaryE2ECertificationError('readiness vertical must match documents adapter')
        if getattr(readiness,'provider_id',None) != descriptor.provider_id:
            raise DocumentsCanaryE2ECertificationError('readiness provider must match documents adapter')
        if request.action_key not in descriptor.allowed_actions:
            raise DocumentsCanaryE2ECertificationError('action not allowed by documents canary adapter')
        if (not descriptor.read_only or descriptor.mutation_enabled or descriptor.delete_enabled or descriptor.move_enabled
                or descriptor.network_transport_enabled or descriptor.production_transport_enabled):
            raise DocumentsCanaryE2ECertificationError('G11 requires strict local readonly disabled-transport adapter')

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
            raise DocumentsCanaryE2ECertificationError('documents canary execution was not submitted')

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
        if preview.get('content_read') or preview.get('mutation_performed') or preview.get('external_calls_made') != 0:
            raise DocumentsCanaryE2ECertificationError('documents safety invariant violated by adapter preview')

        return DocumentsCanaryE2EResult(
            auth.activation_id,execution.execution_id,reconciliation.reconciliation_id,decision.certification_id,
            execution.state,reconciliation.state,decision.outcome,decision.certified,descriptor.read_only,
            descriptor.mutation_enabled,descriptor.delete_enabled,descriptor.move_enabled,
            descriptor.network_transport_enabled,descriptor.production_transport_enabled,
            preview.get('external_calls_made',0))
