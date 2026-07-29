from datetime import datetime, timedelta, timezone
from app.schemas.phoenix_demo1_v21_225 import DemoRequest, DemoToolState
from app.services.phoenix_demo1_v21_225 import run_demo_vertical_slice, demo_status

NOW = datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc)

def req(**kw):
    data = dict(
        session_id='demo-1', workspace_id='ws-1', operator_id='operator-1',
        command='summarize current system status', mode='interactive', priority='normal',
        action_risk='read-only', now=NOW,
        tools=[DemoToolState(tool_id='status', available=True, healthy=True)],
        memory_context_available=True, voice_available=True, text_available=True,
    )
    data.update(kw)
    return DemoRequest(**data)

def test_status_declares_bounded_demo_ready():
    s = demo_status()
    assert s.vertical_slice_ready is True
    assert s.autonomous_high_risk_execution_enabled is False

def test_read_only_work_can_continue_without_approval():
    d = run_demo_vertical_slice(req())
    assert d.state == 'working'
    assert d.interaction_channel == 'voice'
    assert d.executable_without_approval
    assert not d.approval_requests

def test_high_risk_action_is_approval_gated():
    d = run_demo_vertical_slice(req(command='execute governed trade action', action_risk='high'))
    assert d.state == 'queued-for-approval'
    assert len(d.approval_requests) == 1
    assert not d.executable_without_approval

def test_explicit_tool_approval_gate_is_respected():
    tools=[DemoToolState(tool_id='broker', available=True, healthy=True, requires_approval=True)]
    d = run_demo_vertical_slice(req(tools=tools, action_risk='medium'))
    assert d.state == 'queued-for-approval'

def test_sleep_mode_defers_noncritical_approval_request():
    d = run_demo_vertical_slice(req(mode='sleep', command='perform gated action', action_risk='high'))
    assert d.state == 'deferred'
    assert d.interaction_channel == 'silent'
    assert d.deferred_items

def test_suppression_until_defers_interaction():
    d = run_demo_vertical_slice(req(action_risk='high', suppress_interaction_until=NOW + timedelta(hours=8)))
    assert d.state == 'deferred'
    assert d.interaction_channel == 'silent'

def test_critical_request_surfaces_even_in_sleep_mode_but_stays_gated():
    d = run_demo_vertical_slice(req(mode='sleep', priority='critical', action_risk='high'))
    assert d.state == 'queued-for-approval'
    assert d.interaction_channel == 'silent'
    assert d.approval_requests

def test_text_fallback_when_voice_unavailable():
    d = run_demo_vertical_slice(req(voice_available=False, text_available=True))
    assert d.interaction_channel == 'text'

def test_risk_brain_hard_block_fails_closed():
    d = run_demo_vertical_slice(req(risk_brain_hard_block=True, action_risk='read-only'))
    assert d.state == 'blocked'
    assert not d.executable_without_approval
