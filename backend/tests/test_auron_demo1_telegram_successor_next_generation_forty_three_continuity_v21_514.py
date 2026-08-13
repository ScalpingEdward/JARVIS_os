from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_three_continuity_v21_514 import command_center, router, status


def client() -> TestClient:
    app = FastAPI(); app.include_router(router); return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.514/continuity/check' in paths
    assert '/auron/demo1/v21.514/baseline/expire' in paths
    assert '/auron/demo1/v21.514/renewal/request' in paths
    assert '/auron/demo1/v21.514/status' in paths
    assert '/auron/demo1/v21.514/command-center' in paths


def test_safe_empty_status() -> None:
    result = status(); assert result['external_calls_made'] == 0; assert result['mode'] == 'successor-next-generation-forty-three-continuity-expiry-renewal'


def test_continuity_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.514/continuity/check', json={'actor':'tester','monitoring_id':'missing','check_phrase':'WRONG','observed_successor_next_generation_forty_three_hash':'0'*64,'control_state':'healthy','validity_days':90,'continuity_statement':'test'})
    assert response.status_code == 403


def test_expiry_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.514/baseline/expire', json={'actor':'tester','monitoring_id':'missing','expiry_phrase':'WRONG','expiry_reference':'test','expiry_statement':'test'})
    assert response.status_code == 403


def test_renewal_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.514/renewal/request', json={'actor':'tester','monitoring_id':'missing','renewal_phrase':'WRONG','renewal_reference':'test','renewal_statement':'test'})
    assert response.status_code == 403


def test_missing_monitoring_fails_closed() -> None:
    response = client().post('/auron/demo1/v21.514/continuity/check', json={'actor':'tester','monitoring_id':'missing','check_phrase':'CHECK AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY THREE CONTINUITY','observed_successor_next_generation_forty_three_hash':'0'*64,'control_state':'healthy','validity_days':90,'continuity_statement':'test'})
    assert response.status_code == 404


def test_command_center_safety() -> None:
    html = command_center(); assert 'AURON v21.514' in html; assert 'no Telegram API call' in html; assert 'external_calls_made=0' in html
