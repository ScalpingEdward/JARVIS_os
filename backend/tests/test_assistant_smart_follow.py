from app.assistant import tools
from app.smartmoney.service import smart_money_service as sm

SIG = [{"owner": "Johnson Kathleen E", "verdict": "profi", "n": 4, "hit": .75, "avg": .94, "tickers": ["LUMN"]},
       {"owner": "Taylor David S", "verdict": "profi", "n": 7, "hit": .86, "avg": .26, "tickers": ["DAL"]},
       {"owner": "Loser Larry", "verdict": "weg", "n": 5, "hit": .2, "avg": -.1, "tickers": ["XYZ"]}]


def test_auron_stars_all_profis_one_by_name_and_removes_them(monkeypatch):
    monkeypatch.setattr(sm, "backtest", lambda: {"summary": {"by_signaler": SIG}})
    for f in sm.follows():
        sm.unfollow(f["owner"])
    out, failed = tools.run("smart_money_follow", {"action": "follow_all_profi"})
    assert not failed and '"added": 2' in out
    assert {f["owner"] for f in sm.follows()} == {"Johnson Kathleen E", "Taylor David S"}
    tools.run("smart_money_follow", {"action": "unfollow", "owner": "taylor"})
    tools.run("smart_money_follow", {"action": "follow", "owner": "Loser"})
    assert {f["owner"] for f in sm.follows()} == {"Johnson Kathleen E", "Loser Larry"}
    out, _ = tools.run("smart_money_follow", {"action": "follow", "owner": "a"})   # matches several
    assert "Insider passen" in out
    out, _ = tools.run("smart_money_follow", {"action": "unfollow_all"})
    assert '"removed": 2' in out and sm.follows() == []
