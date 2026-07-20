from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = "/v1/executive-telegram-chart-vision-signal-intelligence"


def payload(source_key: str = "tg-vision-1", workspace_id: str = "ws-vision") -> dict:
    return {
        "workspace_id": workspace_id,
        "source_key": source_key,
        "actor_id": "master-brano",
        "telegram_chat_id": "ict-signals",
        "telegram_message_id": source_key,
        "image_sha256": (source_key * 8)[:32],
        "market_context_confirmed": True,
        "risk_brain_clear": True,
        "human_approved": True,
        "extraction": {
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "direction": "long",
            "entry_price": 2400,
            "stop_loss": 2395,
            "take_profit": 2412,
            "ocr_confidence": 92,
            "visual_confidence": 90,
            "chart_quality_score": 88,
            "ict": {
                "fair_value_gap": True,
                "order_block": True,
                "liquidity_sweep": True,
                "break_of_structure": True
            }
        }
    }


def test_validated_chart_becomes_risk_eligible_candidate() -> None:
    response = client.post(f"{BASE}/assessments", json=payload())
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "risk-eligible"
    assert data["trade_candidate"] is True
    assert data["risk_reward"] == 2.4


def test_low_confidence_requires_review() -> None:
    item = payload("tg-vision-2")
    item["extraction"]["visual_confidence"] = 50
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "needs-review"


def test_missing_context_is_requested() -> None:
    item = payload("tg-vision-3")
    item["extraction"]["timeframe"] = None
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "context-required"


def test_inconsistent_levels_are_rejected() -> None:
    item = payload("tg-vision-4")
    item["extraction"]["stop_loss"] = 2405
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "rejected"


def test_risk_brain_blocks_signal() -> None:
    item = payload("tg-vision-5")
    item["risk_brain_clear"] = False
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "rejected"


def test_human_approval_is_required_for_trade_candidate() -> None:
    item = payload("tg-vision-6")
    item["human_approved"] = False
    response = client.post(f"{BASE}/assessments", json=item)
    assert response.status_code == 201
    assert response.json()["state"] == "risk-eligible"
    assert response.json()["trade_candidate"] is False


def test_duplicate_source_and_image_are_blocked() -> None:
    item = payload("tg-vision-7")
    assert client.post(f"{BASE}/assessments", json=item).status_code == 201
    assert client.post(f"{BASE}/assessments", json=item).status_code == 409


def test_workspace_isolation_and_audit() -> None:
    item = payload("tg-vision-8", "ws-isolated")
    created = client.post(f"{BASE}/assessments", json=item)
    assert created.status_code == 201
    assert client.get(f"{BASE}/assessments", params={"workspace_id": "other"}).json() == []
    audit = client.get(f"{BASE}/audit", params={"workspace_id": "ws-isolated"})
    assert audit.status_code == 200
    assert len(audit.json()) == 1
