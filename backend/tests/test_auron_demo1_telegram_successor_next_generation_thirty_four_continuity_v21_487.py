from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_thirty_four_continuity_v21_487 import command_center, router, status


def client() -> TestClient:
    app = FastAPI(); app.include_router(router); return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.487/continuity/start' in paths
    assert '/auron/demo1/v21.487/continuity/checkpoint' in paths
    assert '/auron/demo1/v21.487/baseline/expire' in paths
    assert '/auron/demo1/v21.487/renewal/request' in paths
    assert '/auron/demo1/v21.487/status' in paths
    assert '/auron/demo1/v21.487/command-center' in paths


def test_safe_empty_status() -> None:
    result = status()
    assert result['external_calls_made'] == 0
    assert result['mode'] == 'successor-next-generation-thirty-four-continuity-expiry-renewal'


def test_start_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.487/continuity/start', json={'actor':'tester','baseline_id':'missing','start_phrase':'WRONG','validity_days':90,'checkpoint_interval_days':30})
    assert response.status_code == 403


def test_checkpoint_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.487/continuity/checkpoint', json={'actor':'tester','continuity_id':'missing','check_phrase':'WRONG','observed_successor_next_generation_thirty_four_hash':'0'*64,'control_state':'healthy','continuity_statement':'test'})
    assert response.status_code == 403


def test_expiry_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.487/baseline/expire', json={'actor':'tester','continuity_id':'missing','expiry_phrase':'WRONG','expiry_reference':'test','expiry_statement':'test'})
    assert response.status_code == 403


def test_renewal_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.487/renewal/request', json={'actor':'tester','expiry_id':'missing','renewal_phrase':'WRONG','renewal_reference':'test','renewal_statement':'test'})
    assert response.status_code == 403


def test_command_center_safety() -> None:
    html = command_center()
    assert 'AURON v21.487' in html
    assert 'no Telegram API call' in html
    assert 'external_calls_made=0' in html
