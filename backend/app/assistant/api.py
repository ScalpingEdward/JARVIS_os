from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
