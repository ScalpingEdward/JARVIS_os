from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_auron_command_center_is_registered():
    response = client.get('/auron/demo1/v21.242/command-center')
    assert response.status_code == 200
    assert 'AURON' in response.text
    assert 'v21.242' in response.text


def test_auron_greeting_becomes_conversation():
    response = client.post('/auron/demo1/v21.242/dialogue', json={
        'session_id': 'test-greeting',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'Auron, Master Brano ist hier.',
        'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'conversation'
    assert body['state'] == 'conversation'
    assert 'Master Brano' in body['reply']


def test_auron_supported_intent_uses_existing_execution_layer():
    response = client.post('/auron/demo1/v21.242/dialogue', json={
        'session_id': 'test-system',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'Auron, check system readiness.',
        'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'capability'
    assert 'system-status' in body['detected_intents']
    assert 'Systemstatus geprüft' in body['reply']


def test_financial_execution_still_requires_approval():
    response = client.post('/auron/demo1/v21.242/dialogue', json={
        'session_id': 'test-financial',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'buy EURUSD now',
        'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'approval-required'
    assert body['approval_required'] is True
