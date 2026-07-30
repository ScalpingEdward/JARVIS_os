from app.api.routes import auron_demo1_provider_brain_v21_254 as brain
from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.models.contracts import ModelResponse


def test_provider_order_prefers_openai_then_anthropic(monkeypatch):
    monkeypatch.setattr(brain.model_router, 'available_providers', lambda: ['anthropic', 'mock', 'openai'])
    assert brain._provider_order() == ['openai', 'anthropic']


def test_conversation_uses_provider_native_brain(monkeypatch):
    monkeypatch.setattr(brain, 'v21_253_dialogue', lambda req: {
        'state': 'conversation',
        'mode': 'conversation',
        'reply': 'local fallback',
        'goal': 'AURON bauen',
        'current_task': 'Provider Brain',
        'next_step': 'testen',
    })
    monkeypatch.setattr(brain.model_router, 'available_providers', lambda: ['openai'])
    monkeypatch.setattr(
        brain.model_router,
        'generate',
        lambda request, provider_name='mock': ModelResponse(provider='openai', model='test', content='Natürliche Provider-Antwort.'),
    )
    result = brain.dialogue(DialogueRequest(session_id='s1', command='Wie geht es weiter?'))
    assert result['reply'] == 'Natürliche Provider-Antwort.'
    assert result['brain_provider'] == 'openai'
    assert result['brain_mode'] == 'provider-native'


def test_governed_capability_is_not_rewritten_by_llm(monkeypatch):
    monkeypatch.setattr(brain, 'v21_253_dialogue', lambda req: {
        'state': 'completed',
        'mode': 'capability',
        'reply': 'Systemstatus geprüft.',
        'approval_required': False,
    })
    monkeypatch.setattr(brain.model_router, 'available_providers', lambda: ['openai'])
    result = brain.dialogue(DialogueRequest(session_id='s2', command='Check system status'))
    assert result['reply'] == 'Systemstatus geprüft.'
    assert result['brain_mode'] == 'governed-capability'
    assert result['brain_provider'] is None


def test_brain_status_without_provider(monkeypatch):
    monkeypatch.setattr(brain.model_router, 'available_providers', lambda: ['mock'])
    status = brain.brain_status()
    assert status['provider_native_conversation'] is False
    assert status['preferred_provider'] is None
    assert status['operational_commands_governed'] is True
