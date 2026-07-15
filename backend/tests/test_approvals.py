from fastapi.testclient import TestClient

from app.approvals.service import approval_service
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    approval_service.reset()


def _request() -> dict:
    response = client.post(
        "/v1/approvals",
        json={
            "action": "deployment.production",
            "arguments": {"version": "1.0.0"},
            "requested_by": "worker-a",
            "requester_role": "operator",
            "risk": "critical",
            "reason": "Release approved build",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_approval_requires_authorized_second_actor_and_single_use_token() -> None:
    approval = _request()

    self_approval = client.post(
        f"/v1/approvals/{approval['id']}/approve",
        json={"actor": "worker-a", "role": "approver"},
    )
    assert self_approval.status_code == 400

    approved = client.post(
        f"/v1/approvals/{approval['id']}/approve",
        json={"actor": "owner", "role": "admin", "note": "Approved"},
    )
    assert approved.status_code == 200
    token = approved.json()["confirmation_token"]
    assert len(token) >= 20

    wrong = client.post(
        f"/v1/approvals/{approval['id']}/consume",
        json={"confirmation_token": "x" * 32, "actor": "executor"},
    )
    assert wrong.status_code == 400

    consumed = client.post(
        f"/v1/approvals/{approval['id']}/consume",
        json={"confirmation_token": token, "actor": "executor"},
    )
    assert consumed.status_code == 200
    assert consumed.json()["status"] == "consumed"

    replay = client.post(
        f"/v1/approvals/{approval['id']}/consume",
        json={"confirmation_token": token, "actor": "executor"},
    )
    assert replay.status_code == 400


def test_viewer_cannot_request_and_forbidden_action_is_blocked() -> None:
    viewer = client.post(
        "/v1/approvals",
        json={
            "action": "task.create",
            "requested_by": "viewer-user",
            "requester_role": "viewer",
            "risk": "high",
            "reason": "No permission",
        },
    )
    assert viewer.status_code == 400

    blocked = client.post(
        "/v1/approvals",
        json={
            "action": "database.drop",
            "requested_by": "operator-user",
            "requester_role": "operator",
            "risk": "critical",
            "reason": "Unsafe request",
        },
    )
    assert blocked.status_code == 400


def test_rejection_and_audit_log() -> None:
    approval = _request()
    rejected = client.post(
        f"/v1/approvals/{approval['id']}/reject",
        json={"actor": "reviewer", "role": "approver", "note": "Not safe"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    audit = client.get("/v1/approvals/audit/events")
    assert audit.status_code == 200
    event_types = {item["event_type"] for item in audit.json()["items"]}
    assert "approval_requested" in event_types
    assert "approval_rejected" in event_types
