from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_three_monitoring_v21_513 import command_center, router, status


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.513/monitoring/start' in paths
    assert '/auron/demo1/v21.513/health/audit' in paths
    assert '/auron/demo1/v21.513/drift/open' in paths
    assert '/auron/demo1/v21.513/baseline/certify' in paths
    assert '/auron/demo1/v21.513/status' in paths
    assert '/auron/demo1/v21.513/command-center' in paths


def test_safe_empty_status() -> None:
    result = status()
    assert result['external_calls_made'] == 0
    assert result['mode'] == 'successor-next-generation-forty-three-monitoring-drift-baseline'


def test_monitoring_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.513/monitoring/start', json={'actor':'tester','certification_id':'missing','start_phrase':'WRONG','audit_interval_days':30})
    assert response.status_code == 403


def test_missing_certification_fails_closed() -> None:
    response = client().post('/auron/demo1/v21.513/monitoring/start', json={'actor':'tester','certification_id':'missing','start_phrase':'START AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY THREE MONITORING','audit_interval_days':30})
    assert response.status_code == 404


def test_command_center_safety() -> None:
    html = command_center()
    assert 'AURON v21.513' in html
    assert 'external_calls_made=0' in html
