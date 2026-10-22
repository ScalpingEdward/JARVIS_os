from typing import Literal

import json
import re

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from . import voice
from .brain import AssistantError, reply, reply_stream

router = APIRouter(prefix="/v1/assistant", tags=["assistant"])


IMAGE = re.compile(r"^data:(image/(?:jpeg|png|webp|gif));base64,([A-Za-z0-9+/=]+)$")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
    # a picture Brano attached (📎 or pasted): a data URL, already made small by the dashboard
    image: str | None = Field(default=None, max_length=7_000_000)

    @field_validator("image")
    @classmethod
    def _image(cls, v: str | None) -> str | None:
        if v is not None and not IMAGE.match(v):
            raise ValueError("image must be a base64 data URL of a jpeg, png, webp or gif")
        return v


class ChatIn(BaseModel):
    messages: list[Turn] = Field(min_length=1, max_length=40)
    lang: Literal["de", "en", "sk"] = "de"

    @field_validator("messages")
    @classmethod
    def _few_images(cls, v: list[Turn]) -> list[Turn]:
        if sum(1 for t in v if t.image) > 3:
            raise ValueError("at most 3 pictures per request -- older ones are sent as text only")
        return v


def _turns(messages: list[Turn]) -> list[dict]:
    """For Claude: a turn with a picture becomes [image, text] -- the way the Messages API takes images."""
    out = []
    for m in messages:
        if m.image and m.role == "user":
            kind, data = IMAGE.match(m.image).groups()
            out.append({"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": kind, "data": data}},
                {"type": "text", "text": m.content}]})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


class ChatOut(BaseModel):
    text: str
    tools: list[str]


@router.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn) -> ChatOut:
    """One answer from AURON to the conversation so far."""
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="the last message must be Brano's")
    try:
        return ChatOut(**reply(_turns(payload.messages), payload.lang))
    except AssistantError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/chat/stream")
def chat_stream(payload: ChatIn) -> StreamingResponse:
    """The answer as it is written, one JSON object per line: {"text"}, {"tool"}, finally {"done"}
    -- or {"error"}. The dashboard starts speaking after the first sentence."""
    if payload.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="the last message must be Brano's")

    def lines():
        try:
            for ev in reply_stream(_turns(payload.messages), payload.lang):
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except AssistantError as exc:
            yield json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"})


class LiveToolIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    args: dict = Field(default_factory=dict)


@router.post("/live/session")
def live_session() -> dict:
    """The browser's one-time address for a live talk with AURON (ElevenLabs agent, see live.py)."""
    from . import live
    try:
        return live.session()
    except live.LiveError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/live/tools")
def live_tools() -> list[str]:
    """The tool names the dashboard offers the live agent."""
    from . import tools
    return [t["name"] for t in tools.TOOLS]


@router.post("/live/tool")
def live_tool(payload: LiveToolIn) -> dict:
    """A tool the live agent asked for -- run here, like in the chat."""
    from . import live
    return {"result": live.run_tool(payload.name, payload.args)}


class ClaimIn(BaseModel):
    key: str = Field(min_length=1, max_length=600)


_claimed: dict[str, float] = {}
CLAIM_FOR_S = 300


@router.post("/announce-claim")
def announce_claim(payload: ClaimIn) -> dict:
    """One voice per announcement: every open dashboard (PC window, phone app, wallpaper) asks before
    it speaks, and only the first within five minutes gets {"speak": true} -- the others only write
    it into their chat. Without this, two screens said every trade twice, a moment apart."""
    import time
    now = time.monotonic()
    for k, at in list(_claimed.items()):
        if now - at > CLAIM_FOR_S:
            del _claimed[k]
    first = payload.key not in _claimed
    if first:
        _claimed[payload.key] = now
    return {"speak": first}


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


@router.post("/listen")
async def listen(request: Request, lang: Literal["de", "en", "sk"] = "de") -> dict:
    """The browser's recording (raw body, e.g. audio/webm) -> {text}."""
    audio = await request.body()
    try:
        return {"text": voice.transcribe(audio, request.headers.get("content-type", ""), lang)}
    except voice.VoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
