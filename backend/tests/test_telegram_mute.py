import pytest

from app.assistant import tools
from app.notification_hub import mute
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryConfig


@pytest.fixture(autouse=True)
def clean():
    mute.set_muted("all", False)
    yield
    mute.set_muted("all", False)


def test_a_muted_category_is_not_sent_but_cards_with_buttons_always_are(monkeypatch):
    sent = []
    c = TelegramDeliveryClient(TelegramDeliveryConfig(bot_token="t", chat_id="1"))
    monkeypatch.setattr(c, "_post_message", lambda text, **k: sent.append(text) or 1)
    tools.run("telegram_notifications", {"action": "set", "category": "markets", "on": False})
    c.send("Insider-Kauf", "NVDA"); c.send("Wichtige Post", "Finanzamt")
    assert sent == ["*Wichtige Post*\nFinanzamt"]
    out, failed = tools.run("telegram_notifications", {"action": "get"})
    assert not failed and '"markets": true' in out


def test_only_trades_and_the_copier_learns_it():
    tools.run("telegram_notifications", {"action": "set", "category": "all", "on": False})
    tools.run("telegram_notifications", {"action": "set", "category": "trades", "on": True})
    assert mute.muted() == {"mail": True, "markets": True, "watchlist": True, "instagram": True, "copier": True, "trades": False, "system": True, "other": True}
    assert mute.trades_quiet() is False
    mute.set_muted("trades", True)
    assert mute.trades_quiet() is True
    with pytest.raises(mute.MuteError):
        mute.set_muted("weather", True)


def test_watchlist_alerts_have_their_own_switch():
    assert mute.category_of("Watchlist") == "watchlist"
    mute.set_muted("watchlist", True)
    assert not mute.allows("Watchlist") and mute.allows("Insider-Kauf")
