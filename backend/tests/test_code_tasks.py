import pytest

from app.assistant import tools
from app.code_tasks import service


@pytest.fixture(autouse=True)
def clean():
    service._save([])
    yield
    service._save([])


def test_a_wish_goes_through_the_runner_and_only_brano_puts_it_live():
    out, failed = tools.run("code_request", {"change": "Equity als reine Zahl neben jedem Gruppennamen"})
    assert not failed and '"queued"' in out
    t = service.tasks()[0]
    with pytest.raises(service.CodeTaskError):          # nothing to approve yet
        service.decide(t["id"], "approve")
    assert service.claim()["status"] == "running" and service.claim() is None
    service.report(t["id"], "ready", summary="done", diff="1 file changed", tests="12 passed", branch="auron/task-x")
    assert service.decide(t["id"], "approve")["status"] == "approved"
    assert service.claim()["status"] == "applying"
    assert service.report(t["id"], "applied", commit="abc123")["status"] == "applied"
    assert service.decide(t["id"], "revert")["status"] == "revert_requested"
    assert service.claim()["status"] == "reverting"
    assert service.report(t["id"], "reverted")["status"] == "reverted"


def test_the_runner_cannot_skip_a_step_and_a_rejected_change_is_discarded():
    t = service.create("Eine Spalte mehr in der Tabelle")
    with pytest.raises(service.CodeTaskError):
        service.report(t["id"], "applied")              # straight to live: no
    service.claim(); service.report(t["id"], "ready")
    assert service.decide(t["id"], "reject")["status"] == "rejected"
    assert service.claim()["status"] == "discarding"
    assert service.report(t["id"], "discarded")["status"] == "discarded"


def test_an_approval_that_could_not_be_merged_can_be_given_again():
    t = service.create("Eine Beschreibung im Menü ändern")
    service.claim(); service.report(t["id"], "ready")
    service.decide(t["id"], "approve"); service.claim()
    service.report(t["id"], "apply_failed", error="local changes would be overwritten")
    again = service.decide(t["id"], "approve")
    assert again["status"] == "approved" and again["error"] == ""


def test_a_pc_job_is_planned_first_and_cannot_be_reverted_automatically():
    out, failed = tools.run("pc_request", {"job": "Desktop aufräumen: Bilder in einen Ordner Bilder"})
    assert not failed
    t = service.tasks()[0]
    assert t["kind"] == "pc" and t["status"] == "queued"
    service.claim(); service.report(t["id"], "ready", summary="1. ...")
    service.decide(t["id"], "approve"); service.claim(); service.report(t["id"], "applied")
    with pytest.raises(service.CodeTaskError, match="cannot be reverted"):
        service.decide(t["id"], "revert")
