from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ActivationRequest,
    ActivationStatusResponse,
    AuditRecord,
    LiveAdapterActivationCreate,
    LiveAdapterActivationRecord,
    LiveAdapterActivationState,
)


class ExecutiveLiveAdapterActivationService:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._records: dict[UUID, LiveAdapterActivationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._deployment_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: LiveAdapterActivationCreate) -> tuple[LiveAdapterActivationState, list[str]]:
        o = payload.observation
        reasons: list[str] = []
        if not payload.risk_brain_clear:
            return LiveAdapterActivationState.blocked, ["Risk Brain blocked activation"]
        if o.continuity_state not in {"continuity-ready", "failed-over", "recovered"}:
            return LiveAdapterActivationState.continuity_required, ["Operational continuity is not ready"]
        if not all([o.deployment_package_signed, o.artifact_checksum_verified, o.dependency_lock_verified, o.migration_plan_verified, o.rollback_package_verified]):
            return LiveAdapterActivationState.package_invalid, ["Deployment package or rollback evidence is incomplete"]
        if o.raw_secrets_present or not o.secret_references_resolved:
            return LiveAdapterActivationState.secrets_required, ["Secret references are unresolved or raw secrets are present"]
        if not all([o.adapter_health_verified, o.broker_session_ready, o.market_data_ready, o.executor_transport_ready, o.health_probe_registered, o.rollback_probe_registered]):
            return LiveAdapterActivationState.adapter_unhealthy, ["Adapter runtime health is incomplete"]
        if not o.dry_run_completed or o.dry_run_order_count < 1 or o.dry_run_errors > 0 or not o.dry_run_reconciliation_verified:
            return LiveAdapterActivationState.dry_run_required, ["Successful reconciled dry run is required"]
        if not o.human_approval_verified:
            return LiveAdapterActivationState.approval_required, ["Human activation approval is required"]
        if not o.activation_dispatched or not o.activation_acknowledged:
            return LiveAdapterActivationState.activation_pending, ["Activation dispatch acknowledgement is pending"]
        if not all([o.live_session_identity_verified, o.live_positions_reconciled, o.live_pending_orders_reconciled]):
            return LiveAdapterActivationState.reconciliation_required, ["Live runtime reconciliation is incomplete"]
        return LiveAdapterActivationState.production_ready, reasons

    def assess(self, payload: LiveAdapterActivationCreate) -> LiveAdapterActivationRecord:
        source_key = (payload.workspace_id, payload.source_key)
        deployment_key = (payload.workspace_id, payload.deployment_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate source key")
        if deployment_key in self._deployment_ids:
            raise ValueError("Duplicate deployment id")
        state, reasons = self._evaluate(payload)
        record = LiveAdapterActivationRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            deployment_id=payload.deployment_id,
            environment=payload.environment,
            adapter_reference=payload.adapter_reference,
            state=state,
            reasons=reasons,
            production_actions_enabled=state == LiveAdapterActivationState.production_ready,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._deployment_ids.add(deployment_key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="assessed", actor_id=payload.actor_id, deployment_id=record.deployment_id, state=record.state))
        return record

    def activate(self, request: ActivationRequest) -> LiveAdapterActivationRecord:
        record = next((item for item in self._records.values() if item.workspace_id == request.workspace_id and item.deployment_id == request.deployment_id), None)
        if record is None:
            raise KeyError("Deployment not found")
        if not request.human_approval_verified:
            raise ValueError("Human approval required")
        if not request.activation_dispatched or not request.activation_acknowledged:
            record.state = LiveAdapterActivationState.activation_pending
        elif not all([request.live_session_identity_verified, request.live_positions_reconciled, request.live_pending_orders_reconciled]):
            record.state = LiveAdapterActivationState.reconciliation_required
        else:
            record.state = LiveAdapterActivationState.production_ready
        record.production_actions_enabled = record.state == LiveAdapterActivationState.production_ready
        record.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="activated", actor_id=request.actor_id, deployment_id=record.deployment_id, state=record.state))
        return record

    def get(self, record_id: UUID, workspace_id: str) -> LiveAdapterActivationRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[LiveAdapterActivationRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ActivationStatusResponse:
        records = self.list_records(workspace_id)
        return ActivationStatusResponse(workspace_id=workspace_id, records=len(records), production_ready=sum(r.state == LiveAdapterActivationState.production_ready for r in records), blocked=sum(r.state == LiveAdapterActivationState.blocked for r in records))

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_live_adapter_activation_service = ExecutiveLiveAdapterActivationService()
