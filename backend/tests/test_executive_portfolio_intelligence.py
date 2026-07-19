from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _payload(workspace_id: str = "ws-portfolio") -> dict:
    return {
        "workspace_id": workspace_id,
        "account_profile_id": "ftmo-100k",
        "actor_id": "master-brano",
        "candidates": [
            {
                "strategy_id": "ict-trend",
                "strategy_version": "3.1",
                "symbol": "XAUUSD",
                "market_regime": "strong_trend",
                "asset_cluster": "metals",
                "direction_cluster": "usd-short",
                "adaptive_score": 91,
                "confidence": 0.83,
                "proposed_weight": 0.35,
                "expected_drawdown_pct": 4.0,
                "risk_contribution_pct": 2.0,
            },
            {
                "strategy_id": "breakout",
                "strategy_version": "2.0",
                "symbol": "NAS100",
                "market_regime": "expansion",
                "asset_cluster": "indices",
                "direction_cluster": "risk-on",
                "adaptive_score": 84,
                "confidence": 0.75,
                "proposed_weight": 0.30,
                "expected_drawdown_pct": 5.0,
                "risk_contribution_pct": 2.2,
            },
            {
                "strategy_id": "mean-reversion",
                "strategy_version": "1.4",
                "symbol": "XAUUSD",
                "market_regime": "range",
                "asset_cluster": "metals",
                "direction_cluster": "usd-short",
                "adaptive_score": 67,
                "confidence": 0.62,
                "proposed_weight": 0.30,
                "expected_drawdown_pct": 6.0,
                "risk_contribution_pct": 2.5,
            },
        ],
        "correlations": [
            {"strategy_a": "ict-trend", "strategy_b": "mean-reversion", "correlation": 0.82},
            {"strategy_a": "ict-trend", "strategy_b": "breakout", "correlation": 0.25},
        ],
        "policy": {
            "max_strategy_weight": 0.35,
            "max_symbol_weight": 0.50,
            "max_cluster_weight": 0.60,
            "max_total_risk_pct": 6.0,
            "max_expected_drawdown_pct": 10.0,
            "high_correlation_threshold": 0.75,
            "minimum_adaptive_score": 60,
            "minimum_confidence": 0.55,
        },
    }


def test_portfolio_run_ranks_and_reduces_correlated_strategy() -> None:
    response = client.post("/v1/executive-portfolio-intelligence/runs", json=_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["results"][0]["strategy_id"] == "ict-trend"
    mean_reversion = next(item for item in body["results"] if item["strategy_id"] == "mean-reversion")
    assert mean_reversion["decision"] in {"reduced_weight", "excluded"}
    assert body["metrics"]["portfolio_score"] >= 0


def test_low_confidence_strategy_is_shadow_only() -> None:
    payload = _payload("ws-low-confidence")
    payload["candidates"][1]["confidence"] = 0.20
    response = client.post("/v1/executive-portfolio-intelligence/runs", json=payload)
    assert response.status_code == 201
    breakout = next(item for item in response.json()["results"] if item["strategy_id"] == "breakout")
    assert breakout["decision"] == "shadow_only"
    assert breakout["recommended_weight"] == 0


def test_workspace_isolation_and_audit() -> None:
    created = client.post("/v1/executive-portfolio-intelligence/runs", json=_payload("ws-a"))
    assert created.status_code == 201
    run_id = created.json()["id"]

    hidden = client.get(
        f"/v1/executive-portfolio-intelligence/runs/{run_id}",
        params={"workspace_id": "ws-b"},
    )
    assert hidden.status_code == 404

    audit = client.get(
        "/v1/executive-portfolio-intelligence/audit",
        params={"workspace_id": "ws-a"},
    )
    assert audit.status_code == 200
    assert any(item["action"] == "portfolio_run_created" for item in audit.json())


def test_duplicate_strategy_is_rejected() -> None:
    payload = _payload("ws-duplicate")
    payload["candidates"].append(payload["candidates"][0].copy())
    response = client.post("/v1/executive-portfolio-intelligence/runs", json=payload)
    assert response.status_code == 422
