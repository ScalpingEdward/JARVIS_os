from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, PipelineAssessment, PipelineAssessmentCreate, PipelineExecuteRequest, PipelineState, PipelineStatus


class EndToEndRuntimeValidationService:
    def __init__(self) -> None:
        self._records: dict[UUID, PipelineAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: PipelineAssessmentCreate) -> tuple[PipelineState, list[str]]:
        if payload.risk_brain_blocked:
            return PipelineState.BLOCKED, ["Risk Brain blocked production activation"]
        if not payload.strategy_runtime_active:
            return PipelineState.RUNTIME_REQUIRED, ["v18.94 strategy runtime is not active"]
        if not payload.dependencies_complete:
            return PipelineState.DEPENDENCY_MISSING, ["One or more pipeline dependencies are incomplete"]
        if payload.terminal_error:
            return PipelineState.FAILED, [payload.terminal_error]
        if payload.pause_requested:
            return PipelineState.PAUSED, ["Pipeline pause requested"]

        names = {component.name.lower(): component for component in payload.components}
        required = {"mt5", "market-data", "signal-provider", "event-bus", "database"}
        if not required.issubset(names):
            return PipelineState.DEPENDENCY_MISSING, ["Required runtime health components are missing"]

        stale = [c.name for c in payload.components if c.heartbeat_age_seconds > c.timeout_seconds]
        if stale:
            if not payload.recovery_plan_defined:
                return PipelineState.HEARTBEAT_STALE, [f"Stale heartbeat: {', '.join(stale)}"]
            return PipelineState.RECOVERY_REQUIRED, [f"Recovery required for stale components: {', '.join(stale)}"]

        state_by_component = {
            "mt5": PipelineState.MT5_UNHEALTHY,
            "market-data": PipelineState.MARKET_DATA_UNHEALTHY,
            "signal-provider": PipelineState.SIGNAL_PROVIDER_UNHEALTHY,
            "event-bus": PipelineState.EVENT_BUS_UNHEALTHY,
            "database": PipelineState.DATABASE_UNHEALTHY,
        }
        for name, state in state_by_component.items():
            if not names[name].healthy:
                if payload.recovery_plan_defined:
                    return PipelineState.RECOVERY_REQUIRED, [f"Recovery required for {name}"]
                return state, [f"{name} health check failed"]

        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return PipelineState.RISK_REJECTED, ["Account-risk and prop-rule approval are mandatory"]
        if not payload.human_approved:
            return PipelineState.APPROVAL_REQUIRED, ["Human production approval is required"]
        if not payload.activation_dispatched or not payload.activation_acknowledged:
            return PipelineState.ACTIVATION_PENDING, ["Production activation is not acknowledged"]
        if not payload.runtime_reconciled:
            return PipelineState.RECONCILIATION_REQUIRED, ["End-to-end runtime reconciliation is required"]
        return PipelineState.PIPELINE_ACTIVE, []

    def create(self, payload: PipelineAssessmentCreate) -> PipelineAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate source_key in workspace")
        state, reasons = self._evaluate(payload)
        record = PipelineAssessment(state=state, reasons=reasons, payload=payload)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="assessment-created", actor_id=payload.actor_id, record_id=record.id))
        return record

    def execute(self, record_id: UUID, workspace_id: str, request: PipelineExecuteRequest) -> PipelineAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("Pipeline assessment not found")
        updates = request.model_dump(exclude={"actor_id"}, exclude_none=True)
        payload = record.payload.model_copy(update=updates)
        state, reasons = self._evaluate(payload)
        updated = record.model_copy(update={"payload": payload, "state": state, "reasons": reasons, "updated_at": datetime.now(timezone.utc)})
        self._records[record_id] = updated
        self._audit.append(AuditRecord(workspace_id=workspace_id, action="pipeline-evaluated", actor_id=request.actor_id, record_id=record_id))
        return updated

    def get(self, record_id: UUID, workspace_id: str) -> PipelineAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.payload.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PipelineAssessment]:
        return [record for record in self._records.values() if record.payload.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PipelineStatus:
        records = self.list_records(workspace_id)
        return PipelineStatus(workspace_id=workspace_id, latest_state=records[-1].state if records else None, count=len(records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


end_to_end_runtime_validation_service = EndToEndRuntimeValidationService()
