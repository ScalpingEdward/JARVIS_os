from datetime import datetime, timezone

import pytest

from app.copier_status import group_names
from app.copier_status.models import CopierStatusIn
from app.copier_status.service import copier_status_service

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
STATUS = {"profile": "demo", "account_login": 1, "server": "X", "currency": "EUR", "balance": 1000, "equity": 1000,
          "captured_at": NOW.isoformat(),
          "groups": [{"name": "VIP SIGNALS Ninja Inner Circle", "pnl_today": 1, "pnl_week": 2, "pnl_total": 3, "open_pnl": 0,
                      "closed_trades": 1, "open_positions": 0},
                     {"name": "ICT CRT PREMIUM"}],
          "timings": [{"group": "VIP SIGNALS Ninja Inner Circle", "delay_s": 3}]}


@pytest.fixture(autouse=True)
def clean():
    group_names._store({})
    copier_status_service.reset()
    yield
    group_names._store({})


def test_a_renamed_group_is_shown_everywhere_and_the_copier_keeps_its_title():
    copier_status_service.push(CopierStatusIn.model_validate(STATUS), NOW)
    known = group_names.originals(copier_status_service.list(NOW, raw=True))
    assert group_names.rename("ninja", "NINJA", known) == {"original": "VIP SIGNALS Ninja Inner Circle", "shown_as": "NINJA"}
    st = copier_status_service.list(NOW)[0]
    assert [g.name for g in st.groups] == ["NINJA", "ICT CRT PREMIUM"] and st.timings[0]["group"] == "NINJA"
    assert {g.name for g in copier_status_service.overview(NOW).groups} == {"NINJA", "ICT CRT PREMIUM"}
    assert copier_status_service.list(NOW, raw=True)[0].groups[0].name == "VIP SIGNALS Ninja Inner Circle"
    # by its new name too, and empty brings the original back
    assert group_names.rename("NINJA", "", known)["shown_as"] == "VIP SIGNALS Ninja Inner Circle"


def test_unclear_or_unknown_names_are_refused():
    known = ["VIP SIGNALS Ninja Inner Circle", "VIP SIGNALS Gold"]
    with pytest.raises(group_names.GroupNameError, match="several"):
        group_names.rename("vip", "X", known)
    with pytest.raises(group_names.GroupNameError, match="no group"):
        group_names.rename("crypto", "X", known)
