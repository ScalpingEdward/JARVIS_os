from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AlertCreate, AlertRecord, AuditRecord, ControlSwitchCreate, ControlSwitchRecord,
    IncidentCreate, IncidentRecord, IncidentState, MetricCreate, MetricRecord,
    ObservabilityStatus, OperatorMutation, SLOCreate, SLORecord, SwitchState,
    TraceCreate, TraceRecord,
)


class ObservabilityControlService:
    def __init__(self) -> None:
        self.metrics: list[MetricRecord] = []
        self.traces: list[TraceRecord] = []
        self.alerts: list[AlertRecord] = []
        self.incidents: list[IncidentRecord] = []
        self.slos: list[SLORecord] = []
        self.switches: list[ControlSwitchRecord] = []
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, actor: str, action: str, kind: str, object_id: UUID, **details: object) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor, action=action, object_type=kind, object_id=str(object_id), details=details))

    def status(self) -> ObservabilityStatus:
        return ObservabilityStatus(metrics=len(self.metrics), traces=len(self.traces), alerts=len(self.alerts), incidents=len(self.incidents), open_incidents=sum(i.state != IncidentState.RESOLVED for i in self.incidents), slos=len(self.slos), switches=len(self.switches))

    def add_metric(self, payload: MetricCreate) -> MetricRecord:
        item = MetricRecord(**payload.model_dump())
        self.metrics.append(item)
        return item

    def list_metrics(self, workspace_id: str, source_module: str | None = None) -> list[MetricRecord]:
        return [x for x in self.metrics if x.workspace_id == workspace_id and (source_module is None or x.source_module == source_module)]

    def add_trace(self, payload: TraceCreate) -> TraceRecord:
        if any(x.workspace_id == payload.workspace_id and x.span_id == payload.span_id for x in self.traces):
            raise ValueError("duplicate span_id in workspace")
        item = TraceRecord(**payload.model_dump())
        self.traces.append(item)
        return item

    def list_traces(self, workspace_id: str, trace_id: str | None = None) -> list[TraceRecord]:
        return [x for x in self.traces if x.workspace_id == workspace_id and (trace_id is None or x.trace_id == trace_id)]

    def create_alert(self, payload: AlertCreate) -> AlertRecord:
        item = AlertRecord(**payload.model_dump())
        self.alerts.append(item)
        self._audit(item.workspace_id, item.owner_id, "alert.created", "alert", item.id, severity=item.severity.value)
        return item

    def list_alerts(self, workspace_id: str) -> list[AlertRecord]:
        return [x for x in self.alerts if x.workspace_id == workspace_id]

    def create_incident(self, payload: IncidentCreate) -> IncidentRecord:
        item = IncidentRecord(**payload.model_dump())
        self.incidents.append(item)
        self._audit(item.workspace_id, item.owner_id, "incident.created", "incident", item.id, severity=item.severity.value)
        return item

    def list_incidents(self, workspace_id: str) -> list[IncidentRecord]:
        return [x for x in self.incidents if x.workspace_id == workspace_id]

    def mutate_incident(self, incident_id: UUID, workspace_id: str, payload: OperatorMutation, state: IncidentState) -> IncidentRecord | None:
        for item in self.incidents:
            if item.id == incident_id and item.workspace_id == workspace_id and item.owner_id == payload.requester_id:
                item.state = state
                item.updated_at = datetime.now(timezone.utc)
                if state == IncidentState.ACKNOWLEDGED:
                    item.acknowledged_by = payload.requester_id
                if state == IncidentState.RESOLVED:
                    item.resolved_by = payload.requester_id
                self._audit(workspace_id, payload.requester_id, f"incident.{state.value}", "incident", item.id, reason=payload.reason)
                return item
        return None

    def create_slo(self, payload: SLOCreate) -> SLORecord:
        if any(x.workspace_id == payload.workspace_id and x.module_key == payload.module_key and x.name == payload.name for x in self.slos):
            raise ValueError("duplicate SLO")
        item = SLORecord(**payload.model_dump())
        self.slos.append(item)
        self._audit(item.workspace_id, item.owner_id, "slo.created", "slo", item.id)
        return item

    def list_slos(self, workspace_id: str) -> list[SLORecord]:
        return [x for x in self.slos if x.workspace_id == workspace_id]

    def create_switch(self, payload: ControlSwitchCreate) -> ControlSwitchRecord:
        item = ControlSwitchRecord(**payload.model_dump())
        self.switches.append(item)
        self._audit(item.workspace_id, item.owner_id, "switch.planned", "control_switch", item.id, module=item.module_key)
        return item

    def set_switch(self, switch_id: UUID, workspace_id: str, payload: OperatorMutation, state: SwitchState) -> ControlSwitchRecord | None:
        for item in self.switches:
            if item.id == switch_id and item.workspace_id == workspace_id and item.owner_id == payload.requester_id:
                item.state = state
                item.applied = False
                self._audit(workspace_id, payload.requester_id, f"switch.{state.value}.planned", "control_switch", item.id, reason=payload.reason)
                return item
        return None

    def list_switches(self, workspace_id: str) -> list[ControlSwitchRecord]:
        return [x for x in self.switches if x.workspace_id == workspace_id]

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [x for x in self.audit if x.workspace_id == workspace_id]


observability_control_service = ObservabilityControlService()
