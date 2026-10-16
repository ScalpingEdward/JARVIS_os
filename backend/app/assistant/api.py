from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import voice
from .brain import AssistantError, reply

router = APIRouter(prefix="/v1/assistant", tags=["assistant"])


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatIn(BaseModel):
    messages: list[Turn] = Field(min_length=1, max_length=40)
    lang: Literal["de", "en", "sk"] = "de"


class ChatOut(BaseModel):
    text: str
    tools: list[str]


@router.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn) -> ChatOut:
    """One answer from AURON to the conversation so far."""
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="the last message must be Brano's")
    try:
        return ChatOut(**reply([m.model_dump() for m in payload.messages], payload.lang))
    except AssistantError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    provider: Literal["elevenlabs", "openai"] = "elevenlabs"
    voice: str = Field(default="onwK4e9ZLuTAKqWW03F9", pattern=r"^[A-Za-z0-9_-]{2,40}$")
    model: str = Field(default="eleven_v4", pattern=r"^[A-Za-z0-9_.-]{2,40}$")
    accent: str = Field(default="", pattern=r"^[A-Za-z ]{0,30}$")  # Brano's pick: "British accent"


@router.get("/voices")
def list_voices() -> dict:
    """The voices AURON can speak with, per provider, and whether its key is set."""
    return voice.voices()


@router.post("/speak")
def speak(payload: SpeakIn) -> Response:
    """The text as MP3 in the chosen voice."""
    try:
        audio = voice.speak(payload.text, payload.provider, payload.voice, payload.model, payload.accent)
    except voice.VoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return Response(audio, media_type="audio/mpeg")
