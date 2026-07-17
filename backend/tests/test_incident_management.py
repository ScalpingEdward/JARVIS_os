from datetime import datetime, timedelta, timezone

import pytest

from app.incident_management.models import (
    ActionState, FollowUpCreate, IncidentCreate, IncidentMutation,
    IncidentSeverity, IncidentState, PostmortemCreate, PostmortemState,
    ResponderMutation, TimelineCreate, TimelineKind,
)
from app.incident_management.service import IncidentManagementService


def _incident(severity: IncidentSeverity = IncidentSeverity.SEV2, workspace: str = "alpha") -> IncidentCreate:
    return IncidentCreate(
        workspace_id=workspace,
        owner_id="owner",
        incident_key=f"event-bus-outage-{workspace}",
        title="Event bus delivery outage",
        summary="Publishing is degraded",
        severity=severity,
        commander_id="commander",
        affected_services=["event-bus", "job-orchestrator"],
    )


def _resolve(service: IncidentManagementService, incident_id) -> None:
    mutation = IncidentMutation(requester_id="owner")
    service.set_state(incident_id, "alpha", mutation, IncidentState.INVESTIGATING)
    service.set_state(incident_id, "alpha", mutation, IncidentState.MITIGATING)
    service.set_state(incident_id, "alpha", mutation, IncidentState.MONITORING)
    service.set_state(incident_id, "alpha", mutation, IncidentState.RESOLVED)


def test_incident_lifecycle_timeline_and_isolation() -> None:
    service = IncidentManagementService()
    incident = service.create_incident(_incident())
    assert incident.state == IncidentState.DECLARED
    assert service.get_incident(incident.id, "beta") is None

    service.add_responder(
        incident.id,
        "alpha",
        ResponderMutation(requester_id="commander", responder_id="responder"),
    )
    entry = service.add_timeline(TimelineCreate(
        workspace_id="alpha",
        requester_id="responder",
        incident_id=incident.id,
        kind=TimelineKind.DIAGNOSIS,
        message="Delivery workers are saturated",
    ))
    assert entry.message.startswith("Delivery")
    assert len(service.list_timeline("alpha", incident.id)) == 1

    _resolve(service, incident.id)
    assert incident.state == IncidentState.RESOLVED
    assert incident.resolved_at is not None
    assert service.metrics("alpha").resolved_incidents == 1


def test_sev2_requires_postmortem_and_completed_followups_before_close() -> None:
    service = IncidentManagementService()
    incident = service.create_incident(_incident())
    _resolve(service, incident.id)

    action = service.create_follow_up(FollowUpCreate(
        workspace_id="alpha",
        requester_id="owner",
        incident_id=incident.id,
        title="Add saturation alert",
        assignee_id="engineer",
        due_at=datetime.now(timezone.utc) + timedelta(days=7),
    ))
    with pytest.raises(ValueError, match="open follow-up"):
        service.set_state(incident.id, "alpha", IncidentMutation(requester_id="owner"), IncidentState.CLOSED)

    service.set_follow_up_state(
        action.id,
        "alpha",
        IncidentMutation(requester_id="engineer"),
        ActionState.DONE,
    )
    with pytest.raises(ValueError, match="approved postmortem"):
        service.set_state(incident.id, "alpha", IncidentMutation(requester_id="owner"), IncidentState.CLOSED)

    postmortem = service.create_postmortem(PostmortemCreate(
        workspace_id="alpha",
        requester_id="owner",
        incident_id=incident.id,
        title="Event bus outage postmortem",
        impact="Event delivery was delayed for 18 minutes.",
        root_cause="Worker saturation exhausted available capacity.",
        lessons_learned=["Alert on queue growth earlier"],
    ))
    service.set_postmortem_state(postmortem.id, "alpha", IncidentMutation(requester_id="owner"), PostmortemState.REVIEW)
    service.set_postmortem_state(postmortem.id, "alpha", IncidentMutation(requester_id="owner"), PostmortemState.APPROVED)
    closed = service.set_state(incident.id, "alpha", IncidentMutation(requester_id="owner"), IncidentState.CLOSED)
    assert closed is not None and closed.state == IncidentState.CLOSED


def test_sev3_can_close_without_postmortem() -> None:
    service = IncidentManagementService()
    incident = service.create_incident(_incident(IncidentSeverity.SEV3))
    _resolve(service, incident.id)
    closed = service.set_state(incident.id, "alpha", IncidentMutation(requester_id="owner"), IncidentState.CLOSED)
    assert closed is not None and closed.closed_at is not None


def test_invalid_transitions_ownership_and_safety_guards() -> None:
    service = IncidentManagementService()
    incident = service.create_incident(_incident())

    with pytest.raises(ValueError, match="invalid incident state transition"):
        service.set_state(incident.id, "alpha", IncidentMutation(requester_id="owner"), IncidentState.RESOLVED)
    assert service.set_state(incident.id, "alpha", IncidentMutation(requester_id="other"), IncidentState.INVESTIGATING) is None

    with pytest.raises(ValueError, match="automatic incident declaration"):
        IncidentCreate(**{**_incident().model_dump(), "automatic_declaration": True})
    with pytest.raises(ValueError, match="never execute mitigation actions"):
        IncidentCreate(**{**_incident().model_dump(), "execute_mitigation": True})
    with pytest.raises(ValueError, match="external incident notification"):
        IncidentCreate(**{**_incident().model_dump(), "notify_external": True})

    _resolve(service, incident.id)
    with pytest.raises(ValueError, match="automatic postmortem publication"):
        PostmortemCreate(
            workspace_id="alpha",
            requester_id="owner",
            incident_id=incident.id,
            title="Unsafe postmortem",
            impact="Impact",
            root_cause="Cause",
            automatic_publication=True,
        )
