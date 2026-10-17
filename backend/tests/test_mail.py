import pytest

from app.mail import service as svc
from app.mail.service import MailError, mail_service


class FakeGmail:
    def __init__(self):
        self.sent = []
        self.msgs = {
            "a": {"id": "a", "thread_id": "t1", "labels": [], "from": "Finanzamt <post@finanzamt.de>", "reply_to": "",
                  "subject": "Bescheid 2025", "message_id": "<m-a@fa>", "snippet": "Frist bis 30.10.", "received": 1792200000},
            "b": {"id": "b", "thread_id": "t2", "labels": [], "from": "Shop <news@shop.de>", "reply_to": "",
                  "subject": "50 % Rabatt", "message_id": "<m-b@shop>", "snippet": "Nur heute", "received": 1792200100},
        }

    @staticmethod
    def configured():
        return True

    def list_ids(self, *a, **k):
        return list(self.msgs)

    def message(self, mid, full=False):
        return {**self.msgs[mid], **({"body": "Text"} if full else {})}

    def send_reply(self, *args):
        self.sent.append(args)
        return "sent-id"


@pytest.fixture
def mail(monkeypatch):
    mail_service.reset()
    g = FakeGmail()
    monkeypatch.setattr(mail_service, "gmail", g)
    monkeypatch.setattr(svc, "classify", lambda ms: [
        {"id": m["id"], "important": m["id"] == "a", "category": "steuer" if m["id"] == "a" else "werbung",
         "summary": "Steuerbescheid, Frist 30.10." if m["id"] == "a" else "Werbung", "sorted": True} for m in ms])
    told = []
    monkeypatch.setattr(mail_service, "_telegram", lambda lines, title, keyboard=None: (told.append((title, lines, keyboard)), True)[1])
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    return g, told


def test_poll_sorts_stores_and_alerts_important_once(mail):
    g, told = mail
    assert mail_service.poll() == {"new": 2, "important": 1, "error": ""}
    assert [t[0] for t in told] == ["Wichtige Post"] and "Bescheid 2025" in told[0][1][0]
    assert mail_service.poll()["new"] == 0          # already sorted: no second Claude call, no second alert
    assert len(told) == 1
    imp = mail_service.items(important_only=True, days=3650)
    assert [i["id"] for i in imp] == ["a"] and imp[0]["category"] == "steuer"


def test_a_reply_is_only_a_draft_until_brano_sends_it(mail):
    g, told = mail
    mail_service.poll()
    d = mail_service.draft("a", "Sehr geehrte Damen und Herren, ...")
    assert d["status"] == "pending" and d["to"].endswith("<post@finanzamt.de>") and d["subject"] == "Re: Bescheid 2025"
    assert g.sent == []                               # drafting sends nothing
    assert told[-1][2][0][0]["callback_data"] == f"mail:m:{d['id']}"
    assert mail_service.send(d["id"])["status"] == "sent" and len(g.sent) == 1
    assert g.sent[0][3:] == ("t1", "<m-a@fa>")        # threaded as a reply
    with pytest.raises(MailError):
        mail_service.send(d["id"])                    # not twice


def test_telegram_tap_from_another_chat_sends_nothing(mail):
    g, _ = mail
    mail_service.poll()
    d = mail_service.draft("a", "x")
    with pytest.raises(MailError):
        mail_service.handle_tap({"callback_query": {"data": f"mail:m:{d['id']}", "message": {"chat": {"id": 7}}}})
    assert g.sent == []
    mail_service.handle_tap({"callback_query": {"data": f"mail:k:{d['id']}", "message": {"chat": {"id": 42}}}})
    assert mail_service.drafts() == [] and g.sent == []


def test_the_assistant_has_no_tool_that_sends():
    from app.assistant import tools
    names = {t["name"] for t in tools.TOOLS}
    assert "mail_draft_reply" in names and not any("send" in n for n in names)


def test_poller_routes_mail_taps():
    from app.telegram_inbound.poller import route_for
    assert route_for({"callback_query": {"data": "mail:m:abc"}}).__name__ == "_mail"
