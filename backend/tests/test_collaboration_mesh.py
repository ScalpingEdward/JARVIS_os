from fastapi.testclient import TestClient

from app.collaboration_mesh.service import collaboration_mesh_service
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    collaboration_mesh_service.reset()


def register(name: str, role: str, capability: str) -> dict:
    response = client.post(
        "/v1/collaboration-mesh/agents",
        json={"name": name, "role": role, "capabilities": [capability], "confidence_weight": 1},
    )
    assert response.status_code == 201
    return response.json()


def test_routes_mission_to_matching_agents_and_reaches_consensus() -> None:
    analyst = register("ANALYST", "analyst", "market-analysis")
    guardian = register("GUARDIAN", "guardian", "market-analysis")
    mission = client.post(
        "/v1/collaboration-mesh/missions",
        json={
            "title": "Review XAUUSD thesis",
            "objective": "Produce a safe advisory recommendation",
            "required_capabilities": ["market-analysis"],
            "critical": False,
            "consensus_threshold": 0.67,
        },
    ).json()
    assert mission["state"] == "active"
    assert len(mission["assigned_agent_ids"]) == 2

    for agent in (analyst, guardian):
        response = client.post(
            f"/v1/collaboration-mesh/missions/{mission['id']}/contributions",
            json={
                "agent_id": agent["id"],
                "summary": "Market structure and safety reviewed",
                "confidence": 0.9,
                "evidence": ["H4 structure", "risk controls"],
                "recommendation": "Wait for human approval before any action",
            },
        )
        assert response.status_code == 200
        vote = client.post(
            f"/v1/collaboration-mesh/missions/{mission['id']}/votes",
            json={"agent_id": agent["id"], "decision": "approve", "confidence": 0.9, "rationale": "Evidence aligned"},
        )
        assert vote.status_code == 200

    result = client.get(f"/v1/collaboration-mesh/missions/{mission['id']}").json()
    assert result["state"] == "completed"
    assert result["consensus_score"] >= 0.67
    assert "human approval" in result["final_recommendation"].lower()


def test_critical_mission_never_auto_executes() -> None:
    register("GUARDIAN", "guardian", "safety")
    mission = client.post(
        "/v1/collaboration-mesh/missions",
        json={"title": "Critical review", "objective": "Review only", "required_capabilities": ["safety"], "critical": True},
    ).json()
    assert mission["human_approval_required"] is True
    status = client.get("/v1/collaboration-mesh/status").json()
    assert status["automatic_execution"] is False
    assert status["automatic_order_execution"] is False
    assert status["automatic_merge"] is False
