from fastapi.testclient import TestClient

from app.main import app
from app.simulation_engine.service import simulation_service

client = TestClient(app)


def setup_function() -> None:
    simulation_service.reset()


def test_trading_monte_carlo_is_isolated() -> None:
    created = client.post(
        "/v1/simulations",
        json={
            "title": "XAUUSD risk test",
            "kind": "monte_carlo",
            "iterations": 200,
            "seed": 7,
            "trading": {
                "instrument": "XAUUSD",
                "entry": 2400,
                "stop_loss": 2390,
                "take_profit": 2430,
                "risk_percent": 1,
                "starting_balance": 100000,
                "win_probability": 0.45,
                "trades": 50
            }
        },
    )
    assert created.status_code == 201
    simulation_id = created.json()["id"]
    result = client.post(f"/v1/simulations/{simulation_id}/run")
    assert result.status_code == 200
    payload = result.json()
    assert payload["state"] == "completed"
    assert payload["live_environment_modified"] is False
    assert payload["automatic_order_execution"] is False
    assert "risk_of_ruin" in payload["result"]


def test_what_if_recommends_best_supplied_scenario() -> None:
    created = client.post(
        "/v1/simulations",
        json={
            "title": "CI outage response",
            "kind": "what_if",
            "scenarios": [
                {"name": "wait", "probability": 0.8, "impact": -20, "risk": 40},
                {"name": "failover", "probability": 0.7, "impact": 45, "risk": 15, "cost": 100}
            ]
        },
    )
    simulation_id = created.json()["id"]
    result = client.post(f"/v1/simulations/{simulation_id}/run").json()
    assert result["result"]["recommended_scenario"] == "failover"
    status = client.get("/v1/simulations/status").json()
    assert status["sandbox_isolated"] is True
    assert status["automatic_merge"] is False
