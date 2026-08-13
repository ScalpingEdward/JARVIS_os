from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_two_monitoring_v21_510 import command_center, router, status


def client() -> TestClient:
    app = FastAPI(); app.include_router(router); return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.510/monitoring/start' in paths
    assert '/auron/demo1/v21.510/health/audit' in paths
    assert '/auron/demo1/v21.510/drift/open' in paths
    assert '/auron/demo1/v21.510/baseline/certify' in paths
    assert '/auron/demo1/v21.510/status' in paths
    assert '/auron/demo1/v21.510/command-center' in paths


def test_safe_empty_status() -> None:
    result = status(); assert result['external_calls_made'] == 0; assert result['mode'] == 'successor-next-generation-forty-two-monitoring-drift-baseline'


def test_start_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.510/monitoring/start', json={'actor':'tester','certification_id':'missing','start_phrase':'WRONG','audit_interval_days':30})
    assert response.status_code == 403


def test_audit_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.510/health/audit', json={'actor':'tester','monitoring_id':'missing','audit_phrase':'WRONG','observed_successor_next_generation_forty_two_hash':'0'*64,'control_state':'healthy','audit_statement':'test'})
    assert response.status_code == 403


def test_missing_monitoring_fails_closed() -> None:
    response = client().post('/auron/demo1/v21.510/health/audit', json={'actor':'tester','monitoring_id':'missing','audit_phrase':'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY TWO HEALTH','observed_successor_next_generation_forty_two_hash':'0'*64,'control_state':'healthy','audit_statement':'test'})
    assert response.status_code == 404


def test_command_center_safety() -> None:
    html = command_center(); assert 'AURON v21.510' in html; assert 'no Telegram API call' in html; assert 'external_calls_made=0' in html
