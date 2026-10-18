from datetime import date, timedelta

from app.smartmoney.backtest import events, excess_returns, mark_clusters, role_of, summarize
from app.smartmoney.service import smart_money_service


def test_events_sum_a_filing_and_drop_small_buys_and_small_sales():
    subs = {"a1": {"ISSUERTRADINGSYMBOL": "nvda", "ISSUERNAME": "NVIDIA CORP", "FILING_DATE": "2025-03-03"},
            "a2": {"ISSUERTRADINGSYMBOL": "ORCL", "ISSUERNAME": "ORACLE", "FILING_DATE": "2025-03-04"},
            "a3": {"ISSUERTRADINGSYMBOL": "", "ISSUERNAME": "PRIVATE", "FILING_DATE": "2025-03-04"}}
    owners = {"a1": {"RPTOWNERNAME": "Huang", "RPTOWNER_RELATIONSHIP": "Director,Officer", "RPTOWNER_TITLE": "President and CEO"}}
    trans = [
        {"ACCESSION_NUMBER": "a1", "TRANS_CODE": "P", "TRANS_SHARES": "100", "TRANS_PRICEPERSHARE": "200"},
        {"ACCESSION_NUMBER": "a1", "TRANS_CODE": "P", "TRANS_SHARES": "100", "TRANS_PRICEPERSHARE": "200"},   # 40k together
        {"ACCESSION_NUMBER": "a1", "TRANS_CODE": "M", "TRANS_SHARES": "9999", "TRANS_PRICEPERSHARE": "1"},
        {"ACCESSION_NUMBER": "a2", "TRANS_CODE": "S", "TRANS_SHARES": "100", "TRANS_PRICEPERSHARE": "100"},   # sale too small
        {"ACCESSION_NUMBER": "a3", "TRANS_CODE": "P", "TRANS_SHARES": "1000", "TRANS_PRICEPERSHARE": "100"},  # no ticker
    ]
    e = events(subs, owners, trans)
    assert len(e) == 1
    assert (e[0]["ticker"], e[0]["value"], e[0]["role"], e[0]["code"]) == ("NVDA", 40000.0, "CEO/CFO", "P")


def test_roles():
    assert role_of("Director", "") == "Director"
    assert role_of("Officer", "Chief Financial Officer") == "CEO/CFO"
    assert role_of("Officer", "EVP Sales") == "Officer"
    assert role_of("TenPercentOwner", "") == "10%-Owner"


def test_excess_return_counts_from_the_first_close_after_filing_against_the_index():
    d0 = date(2025, 1, 1)
    days = [d0 + timedelta(days=i) for i in range(1, 200)]
    stock = [(d, 100 * (1.001 ** i)) for i, d in enumerate(days)]     # +0.1 % a day
    bench = {d: 1000.0 for d in days}                                    # flat market
    r = excess_returns("2025-01-01", stock, bench)
    assert round(r[5], 4) == round(1.001 ** 5 - 1, 4) and set(r) == {5, 20, 60, 120}
    assert excess_returns("2026-01-01", stock, bench) is None             # nothing after the filing


def test_clusters_and_summary():
    ev = [{"ticker": "X", "owner": "A", "code": "P", "filed": "2025-01-01", "value": 2e6, "role": "CEO/CFO", "ret": {5: 0.02, 60: 0.05}},
          {"ticker": "X", "owner": "B", "code": "P", "filed": "2025-01-08", "value": 5e4, "role": "Director", "ret": {5: -0.01, 60: 0.03}},
          {"ticker": "Y", "owner": "C", "code": "P", "filed": "2025-06-01", "value": 2e5, "role": "Director", "ret": {5: 0.0}},
          {"ticker": "Y", "owner": "D", "code": "S", "filed": "2025-06-01", "value": 5e6, "role": "Officer", "ret": {5: -0.03}}]
    mark_clusters(ev)
    assert [e.get("cluster") for e in ev[:3]] == [True, True, False]
    s = summarize(ev)
    assert s["overall"]["Käufe"]["5"] == {"n": 3, "avg": 0.0033, "median": 0.0, "hit": 0.333}
    assert s["by_cluster"]["Cluster"]["60"]["n"] == 2 and s["overall"]["Große Verkäufe"]["5"]["n"] == 1
    assert s["by_size"]["≥ 1 Mio $"]["60"]["avg"] == 0.05


def test_track_record_sentence_needs_three_cases():
    smart_money_service.reset()
    smart_money_service.save_backtest({"generated_at": "2026-10-17T12:00:00+00:00", "events": [], "summary": {
        "by_ticker": {"ORCL": {"60": {"n": 4, "avg": 0.031, "median": 0.02, "hit": 0.75}}},
        "by_role": {"Director": {"60": {"n": 2, "avg": 0.1, "median": 0.1, "hit": 1}}},
        "by_cluster": {}, "overall": {}, "by_size": {}, "events": 0, "buys": 0, "with_prices": 0}})
    s = smart_money_service.track_record("ORCL", "Director")
    assert "ORCL: +3.1 %" in s and "75 %" in s and "Director" not in s   # 2 cases are not enough to quote


def test_by_insider_rates_buys_and_sales_and_needs_three_trades():
    from app.smartmoney.backtest import by_insider
    mk = lambda o, code, r: {"owner": o, "ticker": "T", "code": code, "role": "Director", "ret": {"60": r}}  # noqa: E731
    ev = [mk("Good", "P", .05), mk("Good", "P", .04), mk("Good", "P", .02),        # buys, all right
          mk("Bad", "P", -.05), mk("Bad", "P", .04), mk("Bad", "P", -.01),         # buys, mostly wrong
          mk("Seller", "S", -.05), mk("Seller", "S", -.03), mk("Seller", "S", .01),  # sales that warned
          mk("Few", "P", .5), mk("Few", "S", -.5), mk("Few", "S", -.5)]           # two and two: no record
    res = {(x["owner"], x["side"]): x for x in by_insider(ev)}
    assert set(res) == {("Good", "buy"), ("Bad", "buy"), ("Seller", "sell")}
    assert res[("Good", "buy")]["verdict"] == "folgen" and res[("Good", "buy")]["right"] == 1.0
    assert res[("Bad", "buy")]["verdict"] == "aussortieren"
    assert res[("Seller", "sell")]["verdict"] == "warnung" and res[("Seller", "sell")]["edge"] > 0


def _sig(owner, code, stock, filed, market=0.0):
    return {"owner": owner, "ticker": "T", "code": code, "role": "Director", "filed": filed,
            "move": {"60": {"stock": stock, "market": market}}}


def test_a_sale_is_a_short_and_costs_are_paid():
    from app.smartmoney.backtest import signal_profit
    assert signal_profit(_sig("A", "P", 0.10, "2025-01-01")) == 0.09     # long +10 % minus 1 % costs
    assert signal_profit(_sig("A", "S", -0.10, "2025-01-01")) == 0.09    # short, stock fell 10 %
    assert signal_profit(_sig("A", "S", 0.05, "2025-01-01")) == -0.06


def test_signalers_are_judged_on_all_their_positions():
    from app.smartmoney.backtest import by_signaler
    ev = [_sig("Pro", "P", .1, "2024-01-01"), _sig("Pro", "S", -.08, "2024-02-01"), _sig("Pro", "P", .05, "2024-03-01"),
          _sig("Bad", "P", -.1, "2024-01-01"), _sig("Bad", "S", .1, "2024-02-01"), _sig("Bad", "P", .2, "2024-03-01")]
    r = {x["owner"]: x for x in by_signaler(ev, codes=("P", "S"))}
    assert r["Pro"]["verdict"] == "profi" and r["Pro"]["hit"] == 1.0 and r["Pro"]["n"] == 3
    assert r["Bad"]["verdict"] == "weg"


def test_walk_forward_only_follows_insiders_who_proved_themselves_before():
    from app.smartmoney.backtest import walk_forward
    ev = [_sig("Pro", "P", .1, "2024-01-01"), _sig("Pro", "P", .1, "2024-02-01"), _sig("Pro", "P", .1, "2024-03-01"),
          _sig("Pro", "P", .1, "2024-04-01"),     # results of the first three not known yet (90 days) -> not followed
          _sig("Pro", "P", -.2, "2024-08-01")]    # by now three are known and good -> followed, and it loses
    w = walk_forward(ev)
    assert w["followed"]["n"] == 1 and w["followed"]["avg"] == -0.21 and w["all_signals"]["n"] == 5


def test_filing_before_price_history_gets_no_move():
    from datetime import date, timedelta

    from app.smartmoney.backtest import position_returns
    days = [date(2021, 1, 4) + timedelta(days=i) for i in range(200)]
    closes = [(d, 100.0 + i) for i, d in enumerate(days)]
    bench = {d: 100.0 for d in days}
    assert position_returns("2020-03-30", closes, bench) is None
    assert position_returns("2021-01-03", closes, bench) is not None
