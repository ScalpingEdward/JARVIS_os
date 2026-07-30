from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_voice_adapter_v21_227 import VoiceBindingRequest
from app.services.phoenix_demo1_voice_adapter_v21_227 import (
    resolve_voice_binding,
    voice_adapter_status,
)


def test_voice_adapter_status_binds_existing_voice_configuration():
    status = voice_adapter_status()
    assert status.provider_contract_ready is True
    assert status.voice_adapter_bound is True
    assert status.existing_voice_control_bound is True
    assert status.configured_stt_provider
    assert status.configured_tts_provider
    assert status.autonomous_high_risk_execution_enabled is False


def test_healthy_stt_tts_resolves_voice_to_voice():
    decision = resolve_voice_binding(VoiceBindingRequest())
    assert decision.state == 'ready'
    assert decision.input_channel == 'voice'
    assert decision.output_channel == 'voice'
    assert decision.fallback_used is False


def test_stt_failure_falls_back_to_text_input():
    decision = resolve_voice_binding(VoiceBindingRequest(stt_available=False))
    assert decision.state == 'degraded'
    assert decision.input_channel == 'text'
    assert decision.output_channel == 'voice'
    assert decision.fallback_used is True


def test_tts_failure_falls_back_to_text_output():
    decision = resolve_voice_binding(VoiceBindingRequest(tts_healthy=False))
    assert decision.state == 'degraded'
    assert decision.input_channel == 'voice'
    assert decision.output_channel == 'text'
    assert decision.fallback_used is True


def test_no_fallback_blocks_when_voice_transport_is_unavailable():
    decision = resolve_voice_binding(VoiceBindingRequest(
        stt_available=False,
        tts_available=False,
        text_fallback_available=False,
    ))
    assert decision.state == 'blocked'
    assert 'no-safe-interaction-fallback' in decision.reasons


def test_risk_brain_hard_block_fails_closed():
    decision = resolve_voice_binding(VoiceBindingRequest(risk_brain_hard_block=True))
    assert decision.state == 'blocked'
    assert decision.input_channel == 'silent'
    assert decision.output_channel == 'silent'


def test_voice_adapter_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.227/voice/status' in paths
    assert '/phoenix/demo1/v21.227/voice/resolve' in paths


def test_voice_status_endpoint_is_live():
    response = TestClient(app).get('/phoenix/demo1/v21.227/voice/status')
    assert response.status_code == 200
    assert response.json()['voice_adapter_bound'] is True
