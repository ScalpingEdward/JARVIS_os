from fastapi.testclient import TestClient

from app.collaboration.service import collaboration_service
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    collaboration_service.reset()


def _session_payload() -> dict:
    return {
        "title": "Build Telegram parser",
        "objective": "Produce and review a safe implementation",
        "participants": [
            {"name": "Claude", "provider": "claude", "role": "architect"},
            {"name": "Codex", "provider": "codex", "role": "implementer"},
            {"name": "Gemini", "provider": "gemini", "role": "reviewer"},
        ],
        "required_reviews": 1,
    }


def test_collaboration_accepts_reviewed_contribution() -> None:
    created = client.post("/v1/collaboration/sessions", json=_session_payload())
    assert created.status_code == 200
    session_id = created.json()["id"]

    contribution = client.post(
        f"/v1/collaboration/sessions/{session_id}/contributions",
        json={"participant_name": "Codex", "content": "Implementation ready", "artifacts": ["pr/20"]},
    )
    assert contribution.status_code == 200
    contribution_id = contribution.json()["contributions"][0]["id"]

    reviewed = client.post(
        f"/v1/collaboration/sessions/{session_id}/contributions/{contribution_id}/reviews",
        json={"reviewer_name": "Gemini", "approved": True, "comments": "Tests pass"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "resolved"
    assert reviewed.json()["selected_contribution_id"] == contribution_id


def test_non_reviewer_cannot_review() -> None:
    session = client.post("/v1/collaboration/sessions", json=_session_payload()).json()
    session_id = session["id"]
    contribution = client.post(
        f"/v1/collaboration/sessions/{session_id}/contributions",
        json={"participant_name": "Codex", "content": "Candidate"},
    ).json()["contributions"][0]

    response = client.post(
        f"/v1/collaboration/sessions/{session_id}/contributions/{contribution['id']}/reviews",
        json={"reviewer_name": "Claude", "approved": True, "comments": "Looks good"},
    )
    assert response.status_code == 400
    assert "not allowed to review" in response.json()["detail"]


def test_rejection_escalates_conflict() -> None:
    session = client.post("/v1/collaboration/sessions", json=_session_payload()).json()
    session_id = session["id"]
    contribution = client.post(
        f"/v1/collaboration/sessions/{session_id}/contributions",
        json={"participant_name": "Codex", "content": "Candidate"},
    ).json()["contributions"][0]

    reviewed = client.post(
        f"/v1/collaboration/sessions/{session_id}/contributions/{contribution['id']}/reviews",
        json={"reviewer_name": "Gemini", "approved": False, "comments": "Security issue"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "escalated"
    assert reviewed.json()["conflict_reason"]
