from app.executive_mt5_break_even_scale_out.models import BreakEvenAssessmentCreate, BreakEvenState
from app.executive_mt5_break_even_scale_out.service import ExecutiveMT5BreakEvenScaleOutService


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": "source-1",
        "lifecycle_id": "life-1",
        "trailing_state": "trailing-active",
        "position_ticket": 123,
        "side": "buy",
        "entry_price": 2000.0,
        "current_price": 2010.0,
        "current_volume": 1.0,
        "point_size": 0.1,
        "trigger_points": 50,
        "break_even_offset_points": 5,
        "spread_points": 2,
        "commission_points": 1,
        "scale_out_percent": 50,
        "volume_step": 0.01,
        "minimum_remaining_volume": 0.01,
        "minimum_rr": 1.0,
        "observed_rr": 2.0,
        "stop_level_points": 10,
        "freeze_level_points": 5,
        "risk_approved": True,
        "prop_rules_approved": True,
        "human_approved": True,
        "command_dispatched": True,
        "broker_acknowledged": True,
        "broker_retcode": 10009,
        "deal_event_received": True,
        "resulting_stop_loss": 2000.8,
        "resulting_volume": 0.5,
        "position_reconciled": True,
        "account_reconciled": True,
    }
    values.update(overrides)
    return BreakEvenAssessmentCreate(**values)


def test_profit_lock_complete():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(), "tester")
    assert record.state == BreakEvenState.PROFIT_LOCKED
    assert record.close_volume == 0.5
    assert record.remaining_volume == 0.5


def test_trailing_dependency():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(trailing_state="trigger-not-reached"), "tester")
    assert record.state == BreakEvenState.TRAILING_REQUIRED


def test_trigger_not_reached():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(current_price=2002.0), "tester")
    assert record.state == BreakEvenState.TRIGGER_NOT_REACHED


def test_scale_out_rr_gate():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(observed_rr=0.5), "tester")
    assert record.state == BreakEvenState.SCALE_OUT_INVALID


def test_risk_brain_hard_block():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(risk_brain_blocked=True), "tester")
    assert record.state == BreakEvenState.BLOCKED


def test_human_approval_required():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(human_approved=False), "tester")
    assert record.state == BreakEvenState.APPROVAL_REQUIRED


def test_deal_event_required_for_scale_out():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(deal_event_received=False), "tester")
    assert record.state == BreakEvenState.DEAL_EVENT_PENDING


def test_duplicate_source_key_rejected():
    service = ExecutiveMT5BreakEvenScaleOutService()
    service.create(payload(), "tester")
    try:
        service.create(payload(), "tester")
        assert False, "expected duplicate rejection"
    except ValueError:
        assert True


def test_workspace_isolation():
    service = ExecutiveMT5BreakEvenScaleOutService()
    record = service.create(payload(), "tester")
    assert service.get(record.id, "ws-2") is None
    assert service.list_records("ws-2") == []
