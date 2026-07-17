from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ActionState, AuditRecord, FollowUpCreate, FollowUpRecord, IncidentCreate,
    IncidentMetrics, IncidentMutation, IncidentRecord, IncidentSeverity,
    IncidentState, IncidentStatus, PostmortemCreate, PostmortemRecord,
    PostmortemState, ResponderMutation, TimelineCreate, TimelineRecord,
)


class IncidentManagementService:
    def __init__(self) -> None:
        self.incidents: dict[UUID, IncidentRecord] = {}
        self.timeline: dict[UUID, TimelineRecord] = {}
        self.follow_ups: dict[UUID, FollowUpRecord] = {}
        self.postmortems: dict[UUID, PostmortemRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(
            workspace_id=workspace_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            details=details,
        ))

    def status(self) -> IncidentStatus:
        active_states = {
            IncidentState.DECLARED,
            IncidentState.INVESTIGATING,
            IncidentState.MITIGATING,
            IncidentState.MONITORING,
        }
        return IncidentStatus(
            incidents=len(self.incidents),
            active_incidents=sum(i.state in active_states for i in self.incidents.values()),
            postmortems=len(self.postmortems),
            open_follow_ups=sum(a.state in {ActionState.OPEN, ActionState.IN_PROGRESS, ActionState.BLOCKED} for a in self.follow_ups.values()),
        )

    def create_incident(self, payload: IncidentCreate) -> IncidentRecord:
        if any(
            i.workspace_id == payload.workspace_id
            and i.incident_key == payload.incident_key
            and i.state not in {IncidentState.CLOSED, IncidentState.CANCELLED}
            for i in self.incidents.values()
        ):
            raise ValueError("active incident key already exists")
        data = payload.model_dump(exclude={
            "human_approved", "automatic_declaration", "execute_mitigation", "notify_external"
        })
        incident = IncidentRecord(**data)
        self.incidents[incident.id] = incident
        self._audit(incident.workspace_id, "incident.declared", "incident", incident.id, incident.owner_id, severity=incident.severity.value)
        return incident

    def list_incidents(self, workspace_id: str, state: IncidentState | None = None) -> list[IncidentRecord]:
        return [
            i for i in self.incidents.values()
            if i.workspace_id == workspace_id and (state is None or i.state == state)
        ]

    def get_incident(self, incident_id: UUID, workspace_id: str) -> IncidentRecord | None:
        incident = self.incidents.get(incident_id)
        return incident if incident and incident.workspace_id == workspace_id else None

    def set_state(self, incident_id: UUID, workspace_id: str, payload: IncidentMutation, state: IncidentState) -> IncidentRecord | None:
        incident = self.incidents.get(incident_id)
        if not incident or incident.workspace_id != workspace_id or incident.owner_id != payload.requester_id:
            return None
        allowed = {
            IncidentState.INVESTIGATING: {IncidentState.DECLARED},
            IncidentState.MITIGATING: {IncidentState.DECLARED, IncidentState.INVESTIGATING},
            IncidentState.MONITORING: {IncidentState.MITIGATING},
            IncidentState.RESOLVED: {IncidentState.MITIGATING, IncidentState.MONITORING},
            IncidentState.CLOSED: {IncidentState.RESOLVED},
            IncidentState.CANCELLED: {IncidentState.DECLARED, IncidentState.INVESTIGATING},
        }
        if incident.state not in allowed.get(state, set()):
            raise ValueError("invalid incident state transition")
        if state == IncidentState.CLOSED:
            pending = [
                item for item in self.follow_ups.values()
                if item.incident_id == incident.id and item.state not in {ActionState.DONE, ActionState.CANCELLED}
            ]
            if pending:
                raise ValueError("incident cannot close with open follow-up actions")
            postmortem = next((p for p in self.postmortems.values() if p.incident_id == incident.id), None)
            if incident.severity in {IncidentSeverity.SEV1, IncidentSeverity.SEV2} and (
                postmortem is None or postmortem.state not in {PostmortemState.APPROVED, PostmortemState.PUBLISHED, PostmortemState.ARCHIVED}
            ):
                raise ValueError("sev1 and sev2 incidents require an approved postmortem before closure")
        now = datetime.now(timezone.utc)
        incident.state = state
        incident.updated_at = now
        if state == IncidentState.RESOLVED:
            incident.resolved_at = now
        if state == IncidentState.CLOSED:
            incident.closed_at = now
        self._audit(workspace_id, f"incident.{state.value}", "incident", incident.id, payload.requester_id, reason=payload.reason)
        return incident

    def add_responder(self, incident_id: UUID, workspace_id: str, payload: ResponderMutation) -> IncidentRecord | None:
        incident = self.incidents.get(incident_id)
        if not incident or incident.workspace_id != workspace_id or incident.commander_id != payload.requester_id:
            return None
        if payload.responder_id not in incident.responder_ids:
            incident.responder_ids.append(payload.responder_id)
            incident.updated_at = datetime.now(timezone.utc)
            self._audit(workspace_id, "incident.responder-added", "incident", incident.id, payload.requester_id, responder_id=payload.responder_id)
        return incident

    def add_timeline(self, payload: TimelineCreate) -> TimelineRecord:
        incident = self.incidents.get(payload.incident_id)
        if not incident or incident.workspace_id != payload.workspace_id:
            raise ValueError("workspace incident not found")
        if payload.requester_id not in {incident.owner_id, incident.commander_id, *incident.responder_ids}:
            raise ValueError("requester is not assigned to incident")
        data = payload.model_dump(exclude={"human_approved", "execute_action"})
        entry = TimelineRecord(**data)
        self.timeline[entry.id] = entry
        self._audit(entry.workspace_id, "timeline.added", "timeline", entry.id, entry.requester_id, incident_id=str(entry.incident_id), kind=entry.kind.value)
        return entry

    def list_timeline(self, workspace_id: str, incident_id: UUID) -> list[TimelineRecord]:
        return sorted(
            [e for e in self.timeline.values() if e.workspace_id == workspace_id and e.incident_id == incident_id],
            key=lambda e: (e.occurred_at, e.created_at),
        )

    def create_follow_up(self, payload: FollowUpCreate) -> FollowUpRecord:
        incident = self.incidents.get(payload.incident_id)
        if not incident or incident.workspace_id != payload.workspace_id or incident.owner_id != payload.requester_id:
            raise ValueError("owned workspace incident not found")
        data = payload.model_dump(exclude={"human_approved", "create_external_ticket", "execute_remediation"})
        item = FollowUpRecord(**data)
        self.follow_ups[item.id] = item
        self._audit(item.workspace_id, "follow-up.created", "follow-up", item.id, item.requester_id, incident_id=str(item.incident_id))
        return item

    def list_follow_ups(self, workspace_id: str, incident_id: UUID | None = None) -> list[FollowUpRecord]:
        return [
            a for a in self.follow_ups.values()
            if a.workspace_id == workspace_id and (incident_id is None or a.incident_id == incident_id)
        ]

    def set_follow_up_state(self, action_id: UUID, workspace_id: str, payload: IncidentMutation, state: ActionState) -> FollowUpRecord | None:
        item = self.follow_ups.get(action_id)
        incident = self.incidents.get(item.incident_id) if item else None
        if not item or item.workspace_id != workspace_id or not incident:
            return None
        if payload.requester_id not in {item.assignee_id, incident.owner_id}:
            return None
        if item.state in {ActionState.DONE, ActionState.CANCELLED}:
            raise ValueError("follow-up action is already terminal")
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        if state == ActionState.DONE:
            item.completed_at = item.updated_at
        self._audit(workspace_id, f"follow-up.{state.value}", "follow-up", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_postmortem(self, payload: PostmortemCreate) -> PostmortemRecord:
        incident = self.incidents.get(payload.incident_id)
        if not incident or incident.workspace_id != payload.workspace_id or incident.owner_id != payload.requester_id:
            raise ValueError("owned workspace incident not found")
        if incident.state not in {IncidentState.RESOLVED, IncidentState.CLOSED}:
            raise ValueError("postmortem requires a resolved incident")
        if any(p.incident_id == incident.id and p.state != PostmortemState.ARCHIVED for p in self.postmortems.values()):
            raise ValueError("active postmortem already exists")
        data = payload.model_dump(exclude={"human_approved", "automatic_publication", "submit_external"})
        item = PostmortemRecord(**data)
        self.postmortems[item.id] = item
        self._audit(item.workspace_id, "postmortem.created", "postmortem", item.id, item.requester_id, incident_id=str(item.incident_id))
        return item

    def list_postmortems(self, workspace_id: str, incident_id: UUID | None = None) -> list[PostmortemRecord]:
        return [
            p for p in self.postmortems.values()
            if p.workspace_id == workspace_id and (incident_id is None or p.incident_id == incident_id)
        ]

    def set_postmortem_state(self, postmortem_id: UUID, workspace_id: str, payload: IncidentMutation, state: PostmortemState) -> PostmortemRecord | None:
        item = self.postmortems.get(postmortem_id)
        incident = self.incidents.get(item.incident_id) if item else None
        if not item or item.workspace_id != workspace_id or not incident or incident.owner_id != payload.requester_id:
            return None
        allowed = {
            PostmortemState.REVIEW: {PostmortemState.DRAFT},
            PostmortemState.APPROVED: {PostmortemState.REVIEW},
            PostmortemState.PUBLISHED: {PostmortemState.APPROVED},
            PostmortemState.ARCHIVED: {PostmortemState.APPROVED, PostmortemState.PUBLISHED},
        }
        if item.state not in allowed.get(state, set()):
            raise ValueError("invalid postmortem state transition")
        now = datetime.now(timezone.utc)
        item.state = state
        item.updated_at = now
        if state == PostmortemState.APPROVED:
            item.approved_by = payload.requester_id
            item.approved_at = now
        if state == PostmortemState.PUBLISHED:
            item.published_at = now
        self._audit(workspace_id, f"postmortem.{state.value}", "postmortem", item.id, payload.requester_id, reason=payload.reason)
        return item

    def metrics(self, workspace_id: str) -> IncidentMetrics:
        incidents = [i for i in self.incidents.values() if i.workspace_id == workspace_id]
        active_states = {IncidentState.DECLARED, IncidentState.INVESTIGATING, IncidentState.MITIGATING, IncidentState.MONITORING}
        active = [i for i in incidents if i.state in active_states]
        actions = [a for a in self.follow_ups.values() if a.workspace_id == workspace_id]
        postmortems = [p for p in self.postmortems.values() if p.workspace_id == workspace_id]
        now = datetime.now(timezone.utc)
        return IncidentMetrics(
            workspace_id=workspace_id,
            incidents=len(incidents),
            active_incidents=len(active),
            resolved_incidents=sum(i.state == IncidentState.RESOLVED for i in incidents),
            closed_incidents=sum(i.state == IncidentState.CLOSED for i in incidents),
            sev1_open=sum(i.severity == IncidentSeverity.SEV1 for i in active),
            sev2_open=sum(i.severity == IncidentSeverity.SEV2 for i in active),
            timeline_entries=sum(e.workspace_id == workspace_id for e in self.timeline.values()),
            open_follow_ups=sum(a.state in {ActionState.OPEN, ActionState.IN_PROGRESS, ActionState.BLOCKED} for a in actions),
            overdue_follow_ups=sum(a.due_at is not None and a.due_at < now and a.state not in {ActionState.DONE, ActionState.CANCELLED} for a in actions),
            postmortems_pending=sum(p.state in {PostmortemState.DRAFT, PostmortemState.REVIEW} for p in postmortems),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self.audit if a.workspace_id == workspace_id]


incident_management_service = IncidentManagementService()
