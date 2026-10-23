import pytest

from app.notification_hub import mute
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryConfig
from app.push import api, service

SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "BPk", "auth": "xyz"}}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    service._put(service.SUBS, [])
    service._put(service.ROUTES, {})
    mute.set_muted("all", False)
    sent = []
    import pywebpush
    monkeypatch.setattr(pywebpush, "webpush", lambda sub, payload, **k: sent.append((sub["endpoint"], payload)))
    # send_later runs on a thread -- here at once
    monkeypatch.setattr(service, "send_later", lambda t, b, c="other", u="/": service.send(t, b, c, u))
    yield sent
    service._put(service.SUBS, [])
    service._put(service.ROUTES, {})


def test_a_key_pair_is_made_once_and_kept():
    k = service.public_key()
    assert len(k) > 80 and service.public_key() == k


def test_telegram_messages_reach_the_app_by_route(clean):
    tg = []
    c = TelegramDeliveryClient(TelegramDeliveryConfig(bot_token="t", chat_id="1"))
    c._post_message = lambda text, **k: tg.append(text) or 1
    c.send("Wichtige Post", "Finanzamt")
    assert clean == [] and len(tg) == 1                     # nobody signed up: Telegram as always
    service.subscribe(SUB, "iPhone")
    c.send("Wichtige Post", "Finanzamt")
    assert len(clean) == 1 and len(tg) == 2                 # both (default)
    service.set_route("mail", "app")
    c.send("Wichtige Post", "Steuer")
    assert len(clean) == 2 and len(tg) == 2                 # app only
    mute.set_muted("mail", True)
    c.send("Wichtige Post", "Spam")
    assert len(clean) == 2                                  # muted stays muted everywhere


def test_copier_notifications_follow_mute_and_routes(clean):
    service.subscribe(SUB, "Laptop")
    assert api.notify(api.NotifyIn(title="Kopierer NINJA", body="OPENED XAUUSD", category="trades"))["sent_to"] == 1
    mute.set_muted("trades", True)
    assert api.notify(api.NotifyIn(title="Kopierer NINJA", body="OPENED XAUUSD", category="trades"))["sent_to"] == 0
    assert api.notify(api.NotifyIn(title="Kopierer NINJA", body="order FAILED", category="trades"))["sent_to"] == 1


def test_a_device_the_push_service_forgot_is_dropped(monkeypatch):
    import pywebpush

    class Gone(pywebpush.WebPushException):
        pass

    def fail(sub, payload, **k):
        raise Gone("gone", response=type("R", (), {"status_code": 410})())
    monkeypatch.setattr(pywebpush, "webpush", fail)
    service.subscribe(SUB, "alt")
    assert service.send("x", "y") == 0 and service.devices() == []


def test_bad_subscriptions_and_routes_are_refused():
    with pytest.raises(service.PushError):
        service.subscribe({"endpoint": "http://evil", "keys": {}})
    with pytest.raises(service.PushError):
        service.set_route("mail", "fax")
