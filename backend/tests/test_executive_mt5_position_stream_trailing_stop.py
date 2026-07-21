from uuid import uuid4

import pytest

from app.executive_mt5_position_stream_trailing_stop.models import PositionStreamCreate, PositionStreamObservation, PositionStreamState, TrailingModifyRequest
from app.executive_mt5_position_stream_trailing_stop.service import executive_mt5_position_stream_trailing_stop_service as service


def payload(**overrides):
    values = {
        "workspace_id": "ws-1",
        "source_key": str(uuid4()),
        "actor_id": "tester",
        "position_ticket": 123,
        "observation": PositionStreamObservation(
            stream_connected=True,
            sequence_contiguous=True,
            snapshot_age_seconds=1,
            symbol="EURUSD",
            current_price=1.1050,
            entry_price=1.1000,
            trailing_enabled=True,
            activation_distance_points=100,
            trailing_distance_points=50,
            point_size=0.00001,
            proposed_stop_loss=1.1030,
            human_approval_verified=True,
            modify_dispatched=True,
            modify_acknowledged=True,
            broker_retcode_ok=True,
            resulting_stop_loss_verified=True,
            position_snapshot_reconciled=True,
            account_snapshot_reconciled=True,
        ),
    }
    values.update(overrides)
    return PositionStreamCreate(**values)


def setup_function():
    service.reset()


def test_trailing_active():
    assert service.assess(payload()).state == PositionStreamState.trailing_active


def test_lifecycle_required():
    p = payload()
    p.observation.lifecycle_state = "reconciliation-required"
    assert service.assess(p).state == PositionStreamState.lifecycle_required


def test_event_gap_detected():
    p = payload()
    p.observation.sequence_contiguous = False
    assert service.assess(p).state == PositionStreamState.event_gap_detected


def test_stale_snapshot():
    p = payload()
    p.observation.snapshot_age_seconds = 20
    assert service.assess(p).state == PositionStreamState.stale_snapshot


def test_trigger_not_reached():
    p = payload()
    p.observation.current_price = 1.1002
    assert service.assess(p).state == PositionStreamState.trigger_not_reached


def test_protection_invalid():
    p = payload()
    p.observation.proposed_stop_loss = 1.1060
    assert service.assess(p).state == PositionStreamState.protection_invalid


def test_approval_required():
    p = payload()
    p.observation.human_approval_verified = False
    assert service.assess(p).state == PositionStreamState.approval_required


def test_modify_pending():
    p = payload()
    p.observation.modify_dispatched = False
    assert service.assess(p).state == PositionStreamState.modify_pending


def test_execute_reconciles():
    p = payload()
    p.observation.modify_acknowledged = False
    record = service.assess(p)
    updated = service.execute(TrailingModifyRequest(workspace_id="ws-1", stream_id=record.stream_id, actor_id="tester", human_approval_verified=True, modify_dispatched=True, modify_acknowledged=True, broker_retcode_ok=True, resulting_stop_loss_verified=True, position_snapshot_reconciled=True, account_snapshot_reconciled=True))
    assert updated.state == PositionStreamState.trailing_active


def test_risk_brain_blocks():
    assert service.assess(payload(risk_brain_clear=False)).state == PositionStreamState.blocked


def test_duplicate_source_key_rejected():
    p = payload(source_key="duplicate")
    service.assess(p)
    with pytest.raises(ValueError):
        service.assess(payload(source_key="duplicate"))


def test_workspace_isolation():
    record = service.assess(payload())
    assert service.get(record.id, "other") is None
