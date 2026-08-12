from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_thirty_eight_restoration_v21_497 import command_center, router, status


def client() -> TestClient:
    app = FastAPI(); app.include_router(router); return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.497/restoration/prepare' in paths
    assert '/auron/demo1/v21.497/activation/execute' in paths
    assert '/auron/demo1/v21.497/succession/certify' in paths
    assert '/auron/demo1/v21.497/status' in paths
    assert '/auron/demo1/v21.497/command-center' in paths


def test_safe_empty_status() -> None:
    result = status(); assert result['external_calls_made'] == 0; assert result['mode'] == 'successor-next-generation-thirty-eight-restoration-activation-succession'


def test_restoration_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.497/restoration/prepare', json={'actor':'tester','renewal_request_id':'missing','restoration_phrase':'WRONG','proposed_successor_next_generation_thirty_eight_hash':'0'*64,'control_state':'healthy','restoration_reference':'test','restoration_statement':'test'})
    assert response.status_code == 403


def test_activation_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.497/activation/execute', json={'actor':'tester','restoration_id':'missing','activation_phrase':'WRONG','observed_successor_next_generation_thirty_eight_hash':'0'*64,'control_state':'healthy','activation_reference':'test','activation_statement':'test'})
    assert response.status_code == 403


def test_certification_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.497/succession/certify', json={'actor':'tester','activation_id':'missing','certification_phrase':'WRONG','certification_reference':'test','certification_statement':'test'})
    assert response.status_code == 403


def test_missing_renewal_fails_closed() -> None:
    response = client().post('/auron/demo1/v21.497/restoration/prepare', json={'actor':'tester','renewal_request_id':'missing','restoration_phrase':'RESTORE AURON TELEGRAM SUCCESSOR NEXT GENERATION THIRTY EIGHT','proposed_successor_next_generation_thirty_eight_hash':'0'*64,'control_state':'healthy','restoration_reference':'test','restoration_statement':'test'})
    assert response.status_code == 404


def test_command_center_safety() -> None:
    html = command_center(); assert 'AURON v21.497' in html; assert 'no Telegram API call' in html; assert 'external_calls_made=0' in html
