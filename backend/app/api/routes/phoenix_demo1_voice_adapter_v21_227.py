from fastapi import APIRouter

from app.schemas.phoenix_demo1_voice_adapter_v21_227 import (
    VoiceAdapterStatus,
    VoiceBindingDecision,
    VoiceBindingRequest,
)
from app.services.phoenix_demo1_voice_adapter_v21_227 import (
    resolve_voice_binding,
    voice_adapter_status,
)

router = APIRouter(prefix='/phoenix/demo1/v21.227', tags=['phoenix-demo1-v21.227'])


@router.get('/voice/status', response_model=VoiceAdapterStatus)
def status():
    return voice_adapter_status()


@router.post('/voice/resolve', response_model=VoiceBindingDecision)
def resolve(req: VoiceBindingRequest):
    return resolve_voice_binding(req)
