from typing import Literal
from pydantic import BaseModel

VoiceChannel = Literal['voice', 'text', 'silent']
VoiceBindingState = Literal['ready', 'degraded', 'blocked']


class VoiceBindingRequest(BaseModel):
    stt_provider: str | None = None
    tts_provider: str | None = None
    stt_available: bool = True
    stt_healthy: bool = True
    tts_available: bool = True
    tts_healthy: bool = True
    text_fallback_available: bool = True
    risk_brain_hard_block: bool = False


class VoiceBindingDecision(BaseModel):
    state: VoiceBindingState
    input_channel: VoiceChannel
    output_channel: VoiceChannel
    bound_stt_provider: str | None
    bound_tts_provider: str | None
    fallback_used: bool
    reasons: list[str]
    autonomous_high_risk_execution_enabled: bool = False


class VoiceAdapterStatus(BaseModel):
    version: str = 'v21.227'
    provider_contract_ready: bool
    voice_adapter_bound: bool
    configured_stt_provider: str
    configured_tts_provider: str
    text_fallback_enabled: bool
    existing_voice_control_bound: bool
    autonomous_high_risk_execution_enabled: bool = False
    notes: list[str] = []
