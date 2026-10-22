import pytest

from app.assistant import tools
from app.copier_status.models import CopierStatusIn
from app.copier_status.service import copier_status_service
from app.dashboard_layout import ui


def test_auron_opens_a_view_and_a_groups_chart_and_says_when_there_is_none():
    start = ui.since(0)["last"]
    out, failed = tools.run("dashboard_show", {"action": "open_view", "view": "Trading"})
    assert not failed and '"ok": true' in out
    assert [c["view"] for c in ui.since(start)["commands"]] == ["trading"]
    copier_status_service.reset()
    copier_status_service.push(CopierStatusIn.model_validate({
        "profile": "vip", "account_login": 1, "server": "x", "currency": "EUR", "balance": 1, "equity": 1,
        "captured_at": "2026-10-22T10:00:00+00:00",
        "open_positions": [{"ticket": 77, "symbol": "XAUUSD.s", "side": "sell", "volume": 0.05, "price_open": 4100,
                            "sl": 4110, "tp": 4080, "profit": 3, "group": "NINJA"}]}))
    out, _ = tools.run("dashboard_show", {"action": "show_chart", "group": "ninja"})
    assert '"ticket": 77' in out and ui.since(start)["commands"][-1] == {**ui.since(start)["commands"][-1], "do": "show_chart", "ticket": 77, "copier": "vip"}
    out, _ = tools.run("dashboard_show", {"action": "show_chart", "group": "ICT"})
    assert "keine offene Position" in out
    copier_status_service.reset()
