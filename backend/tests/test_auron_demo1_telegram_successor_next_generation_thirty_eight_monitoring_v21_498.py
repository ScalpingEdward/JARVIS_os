from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_thirty_eight_monitoring_v21_498 import command_center, router, status


def client() -> TestClient:
    app = FastAPI(); app.include_router(router); return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.498/monitoring/start' in paths
    assert '/auron/demo1/v21.498/health/audit' in paths
    assert '/auron/demo1/v21.498/drift/open' in paths
    assert '/auron/demo1/v21.498/baseline/certify' in paths
    assert '/auron/demo1/v21.498/status' in paths
    assert '/auron/demo1/v21.498/command-center' in paths


def test_safe_empty_status() -> None:
    result = status(); assert result['external_calls_made'] == 0; assert result['mode'] == 'successor-next-generation-thirty-eight-monitoring-drift-renewed-baseline'


def test_start_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.498/monitoring/start', json={'actor':'tester','certification_id':'missing','start_phrase':'WRONG','audit_interval_days':30})
    assert response.status_code == 403


def test_audit_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.498/health/audit', json={'actor':'tester','monitoring_id':'missing','audit_phrase':'WRONG','observed_successor_next_generation_thirty_eight_hash':'0'*64,'control_state':'healthy','audit_statement':'test'})
    assert response.status_code == 403


def test_drift_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.498/drift/open', json={'actor':'tester','monitoring_id':'missing','trigger_audit_id':'missing','open_phrase':'WRONG','drift_reference':'test','drift_statement':'test'})
    assert response.status_code == 403


def test_baseline_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.498/baseline/certify', json={'actor':'tester','monitoring_id':'missing','certification_phrase':'WRONG','observed_successor_next_generation_thirty_eight_hash':'0'*64,'control_state':'healthy','baseline_reference':'test','baseline_statement':'test'})
    assert response.status_code == 403


def test_command_center_safety() -> None:
    html = command_center(); assert 'AURON v21.498' in html; assert 'no Telegram API call' in html; assert 'external_calls_made=0' in html
