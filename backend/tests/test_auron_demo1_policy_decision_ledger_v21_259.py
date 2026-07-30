from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_policy_decision_ledger_v21_259 import _ledger, dialogue
from app.main import app


def _req(command: str, session_id: str = 'v21-259-test') -> DialogueRequest:
    return DialogueRequest(session_id=session_id, workspace_id='demo', operator_id='brano', command=command)


def test_observe_decision_is_recorded_with_receipt():
    result = dialogue(_req('Zeige System Status', 'v21-259-observe'))
    assert result['policy_receipt']['recorded'] is True
    assert result['policy_decision']['mode'] == 'observe'
    rows = _ledger(_req('ledger', 'v21-259-observe'))
    assert rows[0]['policy_mode'] == 'observe'
    assert rows[0]['allowed'] is True


def test_financial_execution_decision_records_approval_requirement():
    result = dialogue(_req('Führe einen MT5 Trade aus', 'v21-259-approval'))
    assert result['approval_required'] is True
    assert result['policy_decision']['mode'] == 'approval-required'
    rows = _ledger(_req('ledger', 'v21-259-approval'))
    assert rows[0]['approval_required'] is True
    assert rows[0]['allowed'] is False


def test_latest_decision_can_be_explained_without_recording_another_decision():
    session = 'v21-259-explain'
    dialogue(_req('Plane den nächsten Schritt', session))
    before = len(_ledger(_req('ledger', session)))
    result = dialogue(_req('Letzte Policy Entscheidung', session))
    after = len(_ledger(_req('ledger', session)))
    assert result['mode'] == 'policy-decision-explain'
    assert result['decision']['policy_mode'] == 'plan'
    assert before == after


def test_command_center_route_is_registered():
    client = TestClient(app)
    response = client.get('/auron/demo1/v21.259/command-center')
    assert response.status_code == 200
    assert 'v21.259' in response.text
    assert 'AURON POLICY DECISION LEDGER COMMAND CENTER' in response.text
