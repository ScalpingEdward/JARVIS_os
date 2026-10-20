from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.copier_status import commands
from app.db import SessionLocal
from app.db_models import CopierCommandRow
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    with SessionLocal() as s:
        s.query(CopierCommandRow).delete()
        s.commit()
    sent = []
    monkeypatch.setattr(commands, "_telegram", lambda text, keyboard=None: sent.append((text, keyboard)))
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    return sent


def test_pause_is_handed_to_the_copier_until_acked(clean):
    c = commands.create("vip_demo", "pause", "auron")
    assert c["status"] == "pending" and clean == []
    assert commands.pending_for("vip_demo") == [{"id": c["id"], "action": "pause"}]
    assert commands.pending_for("other") == []
    commands.done(c["id"], True, "paused")
    assert commands.pending_for("vip_demo") == []


def test_close_all_waits_for_brano_and_telegram_confirms(clean):
    c = commands.create("vip_demo", "close_all", "auron", label="VIP")
    assert c["status"] == "awaiting_confirmation" and commands.pending_for("vip_demo") == []
    text, kb = clean[-1]
    assert "VIP" in text and kb[0][0]["callback_data"] == f"cmd:z:{c['id']}"
    with pytest.raises(commands.CommandError):    # someone else's chat
        commands.handle_tap({"callback_query": {"data": f"cmd:z:{c['id']}", "message": {"chat": {"id": 7}}}})
    assert commands.pending_for("vip_demo") == []
    commands.handle_tap({"callback_query": {"data": f"cmd:z:{c['id']}", "message": {"chat": {"id": 42}}}})
    assert commands.pending_for("vip_demo") == [{"id": c["id"], "action": "close_all"}]


def test_unconfirmed_close_all_expires(clean):
    c = commands.create("vip_demo", "close_all", "auron")
    with SessionLocal() as s:
        s.get(CopierCommandRow, c["id"]).created_at = datetime.now(timezone.utc) - timedelta(minutes=11)
        s.commit()
    with pytest.raises(commands.CommandError, match="expired"):
        commands.confirm(c["id"])


def test_status_push_answers_with_commands_and_the_dashboard_can_confirm_itself(clean):
    r = client.post("/v1/copier/commands", json={"profile": "p1", "action": "close_all", "confirmed": True})
    assert r.json()["status"] == "pending"
    push = {"profile": "p1", "account_login": 1, "server": "Demo", "currency": "EUR", "balance": 1, "equity": 1,
            "captured_at": datetime.now(timezone.utc).isoformat()}
    assert client.post("/v1/copier/status", json=push).json()["commands"][0]["action"] == "close_all"
    assert client.post("/v1/copier/commands", json={"profile": "p1", "action": "rm -rf"}).status_code == 422


def test_assistant_tool_cannot_confirm(clean, monkeypatch):
    from app.assistant import tools
    from types import SimpleNamespace
    from app.copier_status import service
    monkeypatch.setattr(service.copier_status_service, "overview",
                        lambda: SimpleNamespace(accounts=[SimpleNamespace(profile="vip_demo", label="VIP SIGNALS")]))
    out = tools._copier_command("vip", "close_all")
    assert out["commands"][0]["status"] == "awaiting_confirmation" and "Bestätigung" in out["note"]


def test_offline_copier_is_reported_once_and_its_return_too(monkeypatch):
    from types import SimpleNamespace
    from app.copier_status import watch
    from app.copier_status.models import CopierState
    from datetime import datetime, timezone
    sent = []
    monkeypatch.setattr(watch, "_telegram", sent.append)
    state = {"s": CopierState.offline}
    monkeypatch.setattr(watch.copier_status_service, "list", lambda: [SimpleNamespace(
        profile="vip_demo", label="VIP", state=state["s"], received_at=datetime(2026, 10, 17, 15, 40, tzinfo=timezone.utc))])
    w = watch.CopierWatch()
    assert len(w.check()) == 1 and "VIP ist offline" in sent[0] and "15:40" in sent[0]
    assert w.check() == []
    state["s"] = CopierState.live
    assert w.check() == ["✅ VIP läuft wieder."]


def test_closing_one_position_takes_a_ticket_and_waits_for_confirmation_unless_given(clean):
    from app.copier_status import commands
    assert commands.create("demo", "close:123456789", "auron")["status"] == "awaiting_confirmation"
    assert commands.create("demo", "close:123456789", "dashboard", confirmed=True)["status"] == "pending"
    with pytest.raises(commands.CommandError):
        commands.create("demo", "close:abc", "dashboard", confirmed=True)
