from app.dashboard_layout import i18n


class FakeClient:
    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def post(self, url, **kw):
        self.asked.append(kw["json"]["messages"][0]["content"])
        a = self.answer
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {"content": [{"type": "text", "text": a}]}})()


def test_new_texts_are_translated_once_and_kept(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    i18n._store("cs", {})
    c = FakeClient('{"+# weitere": "+# dalších", "Gruppen": "Skupiny", "heute #": "dnes"}')
    out = i18n.translate("cs", ["+# weitere", "Gruppen", "heute #"], "Čeština", client=c)
    assert out == {"+# weitere": "+# dalších", "Gruppen": "Skupiny"}      # a lost number slot is dropped
    again = FakeClient("{}")
    assert i18n.translate("cs", ["Gruppen"], "Čeština", client=again) == {"Gruppen": "Skupiny"} and again.asked == []
    assert i18n.translate("de", ["Gruppen"], "Deutsch") == {}
    i18n._store("cs", {})
