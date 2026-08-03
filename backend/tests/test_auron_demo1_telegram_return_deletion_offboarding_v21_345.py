from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import auron_demo1_telegram_return_deletion_offboarding_v21_345 as module


def test_v21_345_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.345/proof/commit' in paths
    assert '/auron/demo1/v21.345/offboard' in paths
    assert '/auron/demo1/v21.345/residual-copy/exception/open' in paths
    assert '/auron/demo1/v21.345/residual-copy/exception/resolve' in paths
    assert '/auron/demo1/v21.345/status' in paths


def test_v21_345_status_is_safe_and_empty() -> None:
    module.reset_telegram_return_deletion_offboarding_store()
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.345/status')
    assert response.status_code == 200
    body = response.json()
    assert body['proofs_committed'] == 0
    assert body['recipients_offboarded'] == 0
    assert body['external_calls_made'] == 0


def test_v21_345_requires_explicit_proof_phrase() -> None:
    module.reset_telegram_return_deletion_offboarding_store()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.345/proof/commit', json={
        'actor': 'auditor',
        'retention_id': 'missing',
        'proof_phrase': 'wrong',
        'proof_type': 'deleted',
        'recipient_reference': 'R-1',
        'proof_statement': 'Recipient confirms deletion.',
    })
    assert response.status_code == 403


def test_v21_345_offboarding_requires_proof() -> None:
    module.reset_telegram_return_deletion_offboarding_store()
    client = TestClient(app)
    response = client.post('/auron/demo1/v21.345/offboard', json={
        'actor': 'auditor',
        'retention_id': 'missing',
        'offboarding_phrase': 'OFFBOARD AURON TELEGRAM DISCLOSURE RECIPIENT',
        'access_termination_statement': 'All recipient access is terminated.',
    })
    assert response.status_code == 409
