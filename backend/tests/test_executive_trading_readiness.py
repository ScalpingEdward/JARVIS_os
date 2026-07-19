from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(source_key: str, **overrides):
    data = {
        "workspace_id": "ws-ready",
        "actor_id": "tester",
        "source_key": source_key,
        "symbol": "XAUUSD",
        "account_profile": "ftmo-100k",
        "market_regime_allowed": True,
        "evidence_score": 90,
        "strategy_score": 88,
        "portfolio_health": "strong",
        "risk_state": "normal",
        "trading_decision": "approve",
        "session_open": True,
        "killzone_active": True,
        "spread_score": 90,
        "volatility_score": 80,
        "news_risk": 10,
        "broker_state": "healthy",
        "feed_state": "healthy",
        "vps_state": "healthy",
        "symbol_available": True,
        "data_age_seconds": 1,
        "latency_ms": 20,
        "clock_drift_ms": 10,
    }
    data.update(overrides)
    return data


def test_ready_when_all_gates_pass():
    response = client.post("/v1/executive-trading-readiness/assessments", json=payload("ready-1"))
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "ready"
    assert body["trade_allowed"] is True
    assert body["detected_issues"] == []


def test_stale_data_blocks_and_reports_bug():
    response = client.post("/v1/executive-trading-readiness/assessments", json=payload("stale-1", data_age_seconds=90, max_data_age_seconds=30))
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "blocked"
    assert body["trade_allowed"] is False
    assert "STALE_MARKET_DATA" in {item["code"] for item in body["detected_issues"]}


def test_high_news_and_broker_failure_block():
    response = client.post("/v1/executive-trading-readiness/assessments", json=payload("infra-1", news_risk=95, broker_state="unavailable"))
    assert response.status_code == 201
    codes = {item["code"] for item in response.json()["detected_issues"]}
    assert {"HIGH_IMPACT_NEWS", "BROKER_DOWN"}.issubset(codes)
    assert response.json()["state"] == "blocked"


def test_warning_creates_conditional_state():
    response = client.post("/v1/executive-trading-readiness/assessments", json=payload("conditional-1", spread_score=60))
    assert response.status_code == 201
    assert response.json()["state"] == "conditional"
    assert response.json()["trade_allowed"] is True


def test_shadow_decision_waits_and_disallows_trade():
    response = client.post("/v1/executive-trading-readiness/assessments", json=payload("shadow-1", trading_decision="shadow"))
    assert response.status_code == 201
    assert response.json()["state"] == "wait"
    assert response.json()["trade_allowed"] is False


def test_workspace_isolation_and_duplicate_protection():
    first = client.post("/v1/executive-trading-readiness/assessments", json=payload("dup-1"))
    assert first.status_code == 201
    duplicate = client.post("/v1/executive-trading-readiness/assessments", json=payload("dup-1"))
    assert duplicate.status_code == 409
    foreign = client.get(f"/v1/executive-trading-readiness/assessments/{first.json()['id']}?workspace_id=other")
    assert foreign.status_code == 404


def test_manual_bug_signal_is_detected():
    response = client.post(
        "/v1/executive-trading-readiness/assessments",
        json=payload("bug-1", open_bug_signals=[{"code": "PARSER_STUCK", "component": "signal-parser", "severity": "critical", "message": "Parser heartbeat stopped", "blocking": True}]),
    )
    assert response.status_code == 201
    assert response.json()["state"] == "blocked"
    assert "PARSER_STUCK" in {item["code"] for item in response.json()["detected_issues"]}
