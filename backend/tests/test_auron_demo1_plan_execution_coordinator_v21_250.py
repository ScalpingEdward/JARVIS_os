from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(session: str, command: str, workspace: str = 'demo-v250') -> dict:
    return {
        'session_id': session,
        'workspace_id': workspace,
        'operator_id': 'brano-v250',
        'command': command,
        'risk_brain_hard_block': False,
    }


def test_command_center_registered():
    response = client.get('/auron/demo1/v21.250/command-center')
    assert response.status_code == 200
    assert 'v21.250' in response.text
    assert '/auron/demo1/v21.250/dialogue' in response.text


def test_safe_plan_step_can_be_prepared_without_execution():
    session = 'exec-v250-safe-preview'
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Unser Ziel ist Systemstatus prüfen.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Wir arbeiten an check system status.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Plane unser Ziel'))

    preview = client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Bereite nächsten Planschritt vor'))
    assert preview.status_code == 200
    body = preview.json()
    assert body['mode'] == 'plan-execution-preview'
    assert body['execution_preview']['classification'] == 'safe-capability'
    assert body['execution_preview']['approval_required'] is False
    assert body['plan_done_count'] == 0


def test_safe_plan_step_executes_and_advances_only_after_completion():
    session = 'exec-v250-safe-run'
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Unser Ziel ist Systemstatus prüfen.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Wir arbeiten an check system status.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Plane unser Ziel'))

    executed = client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Führe nächsten Planschritt aus'))
    assert executed.status_code == 200
    body = executed.json()
    assert body['mode'] == 'plan-execution-completed'
    assert body['execution_state'] == 'completed'
    assert body['plan_done_count'] >= 1


def test_financial_plan_step_never_executes_without_approval():
    session = 'exec-v250-financial'
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Unser Ziel ist Trading Ablauf testen.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Nächster Schritt ist buy EURUSD now.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Plane unser Ziel'))

    preview = client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Bereite nächsten Planschritt vor')).json()
    assert preview['execution_preview']['classification'] == 'approval-required'
    assert preview['approval_required'] is True

    executed = client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Führe nächsten Planschritt aus')).json()
    assert executed['mode'] == 'plan-execution-approval-required'
    assert executed['plan_done_count'] == 0


def test_risk_brain_blocks_execution_preview():
    session = 'exec-v250-blocked'
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Unser Ziel ist Systemstatus prüfen.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Wir arbeiten an check system status.'))
    client.post('/auron/demo1/v21.250/dialogue', json=payload(session, 'Plane unser Ziel'))
    blocked = payload(session, 'Bereite nächsten Planschritt vor')
    blocked['risk_brain_hard_block'] = True
    response = client.post('/auron/demo1/v21.250/dialogue', json=blocked)
    assert response.status_code == 200
    assert response.json()['execution_preview']['classification'] == 'blocked'
