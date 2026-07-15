from fastapi import APIRouter, HTTPException

from .models import TelegramVoiceRequest, VoiceReply, VoiceSettings, VoiceStatus, VoiceTranscriptRequest
from .service import VoiceControlError, voice_control_service

router = APIRouter(prefix="/v1/voice", tags=["voice"])


@router.get("/status", response_model=VoiceStatus)
def voice_status() -> VoiceStatus:
    return voice_control_service.status()


@router.put("/settings", response_model=VoiceSettings)
def configure_voice(settings: VoiceSettings) -> VoiceSettings:
    return voice_control_service.configure(settings)


@router.post("/transcript", response_model=VoiceReply)
def handle_transcript(payload: VoiceTranscriptRequest) -> VoiceReply:
    try:
        return voice_control_service.handle_transcript(payload)
    except VoiceControlError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/telegram/voice", response_model=VoiceReply)
def handle_telegram_voice(payload: TelegramVoiceRequest) -> VoiceReply:
    try:
        return voice_control_service.handle_telegram_voice(payload)
    except VoiceControlError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
