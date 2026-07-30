from app.schemas.phoenix_demo1_voice_adapter_v21_227 import (
    VoiceAdapterStatus,
    VoiceBindingDecision,
    VoiceBindingRequest,
)
from app.voice.service import voice_control_service


def voice_adapter_status() -> VoiceAdapterStatus:
    settings = voice_control_service.settings()
    return VoiceAdapterStatus(
        provider_contract_ready=True,
        voice_adapter_bound=True,
        configured_stt_provider=settings.speech_to_text_provider,
        configured_tts_provider=settings.text_to_speech_provider,
        text_fallback_enabled=True,
        existing_voice_control_bound=True,
        autonomous_high_risk_execution_enabled=False,
        notes=[
            'Provider binding uses the existing PHOENIX voice-control settings as the canonical STT/TTS configuration source.',
            'Browser/client speech providers remain responsible for actual audio capture/playback transport.',
            'Text fallback remains available when voice input or output is unavailable or unhealthy.',
            'Voice transport never bypasses existing approval or Risk Brain governance.',
        ],
    )


def resolve_voice_binding(req: VoiceBindingRequest) -> VoiceBindingDecision:
    settings = voice_control_service.settings()
    stt_provider = req.stt_provider or settings.speech_to_text_provider
    tts_provider = req.tts_provider or settings.text_to_speech_provider
    reasons: list[str] = []

    if req.risk_brain_hard_block:
        return VoiceBindingDecision(
            state='blocked',
            input_channel='silent',
            output_channel='silent',
            bound_stt_provider=None,
            bound_tts_provider=None,
            fallback_used=False,
            reasons=['risk-brain-hard-block'],
            autonomous_high_risk_execution_enabled=False,
        )

    stt_ok = bool(stt_provider) and req.stt_available and req.stt_healthy
    tts_ok = bool(tts_provider) and req.tts_available and req.tts_healthy

    if not stt_ok:
        reasons.append('stt-unavailable-or-unhealthy')
    if not tts_ok:
        reasons.append('tts-unavailable-or-unhealthy')

    input_channel = 'voice' if stt_ok else ('text' if req.text_fallback_available else 'silent')
    output_channel = 'voice' if tts_ok else ('text' if req.text_fallback_available else 'silent')
    fallback_used = input_channel == 'text' or output_channel == 'text'

    if input_channel == 'silent' or output_channel == 'silent':
        state = 'blocked'
        reasons.append('no-safe-interaction-fallback')
    elif stt_ok and tts_ok:
        state = 'ready'
    else:
        state = 'degraded'
        reasons.append('text-fallback-active')

    return VoiceBindingDecision(
        state=state,
        input_channel=input_channel,
        output_channel=output_channel,
        bound_stt_provider=stt_provider if stt_ok else None,
        bound_tts_provider=tts_provider if tts_ok else None,
        fallback_used=fallback_used,
        reasons=reasons,
        autonomous_high_risk_execution_enabled=False,
    )
