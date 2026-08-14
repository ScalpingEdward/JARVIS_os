from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_four_restoration_v21_515 import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_restoration_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.515/restoration/prepare', json={
        'actor':'tester','renewal_request_id':'missing','restoration_phrase':'WRONG',
        'proposed_successor_next_generation_forty_four_hash':'0'*64,'control_state':'healthy',
        'restoration_reference':'test','restoration_statement':'test'})
    assert response.status_code == 403


def test_activation_phrase_enforced() -> None:
    response = client().post('/auron/demo1/v21.515/activation/execute', json={
        'actor':'tester','restoration_id':'missing','activation_phrase':'WRONG',
        'observed_successor_next_generation_forty_four_hash':'0'*64,'control_state':'healthy',
        'activation_reference':'test','activation_statement':'test'})
    assert response.status_code == 403
