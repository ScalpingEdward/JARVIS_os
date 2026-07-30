from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_operator_dashboard_v21_230 import OperatorDashboardRequest
from app.services.phoenix_demo1_operator_dashboard_v21_230 import build_operator_dashboard


def req(**kw):
    data = dict(workspace_id='ws-demo', operator_id='operator-demo')
    data.update(kw)
    return OperatorDashboardRequest(**data)


def test_dashboard_unifies_core_demo1_surfaces():
    snapshot = build_operator_dashboard(req())
    ids = {panel.panel_id for panel in snapshot.panels}
    assert {'system-readiness', 'approvals', 'memory', 'voice', 'tools'} <= ids
    assert snapshot.operator_ui_bound is True
    assert snapshot.memory_provider_bound is True
    assert snapshot.voice_adapter_bound is True
    assert snapshot.approval_store_persistent is True
    assert snapshot.autonomous_high_risk_execution_enabled is False


def test_tool_panel_remains_attention_item_until_concrete_adapters_bound():
    snapshot = build_operator_dashboard(req())
    assert snapshot.concrete_tool_adapters_bound is False
    assert 'tools' in snapshot.attention_panels


def test_risk_brain_hard_block_blocks_entire_surface():
    snapshot = build_operator_dashboard(req(risk_brain_hard_block=True))
    assert snapshot.state == 'blocked'
    assert all(panel.state == 'blocked' for panel in snapshot.panels)
    assert len(snapshot.attention_panels) == len(snapshot.panels)


def test_dashboard_navigation_is_explicit_and_stable():
    snapshot = build_operator_dashboard(req())
    assert snapshot.navigation['approvals'] == '/phoenix/demo1/v21.228/approvals'
    assert snapshot.navigation['memory'] == '/phoenix/demo1/v21.229/memory/status'
    assert snapshot.navigation['dashboard'] == '/phoenix/demo1/v21.230/dashboard'


def test_dashboard_route_is_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.230/dashboard' in paths
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.230/dashboard', json={'workspace_id':'ws-demo','operator_id':'operator-demo'})
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.230'
    assert body['operator_ui_bound'] is True
    assert body['autonomous_high_risk_execution_enabled'] is False
