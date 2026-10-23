from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import service

router = APIRouter(prefix="/v1/push", tags=["push"])


class SubscribeIn(BaseModel):
    subscription: dict
    device: str = Field(default="", max_length=60)


class RouteIn(BaseModel):
    category: str
    way: str


class NotifyIn(BaseModel):
    title: str = Field(max_length=120)
    body: str = Field(default="", max_length=900)
    category: str = "other"


@router.get("/key")
def key() -> dict:
    """The public key a device needs to sign up for AURON's notifications."""
    return {"key": service.public_key()}


@router.post("/subscribe")
def subscribe(body: SubscribeIn) -> dict:
    try:
        return service.subscribe(body.subscription, body.device)
    except service.PushError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/unsubscribe")
def unsubscribe(body: SubscribeIn) -> dict:
    return {"removed": service.unsubscribe(str(body.subscription.get("endpoint", "")))}


@router.get("/settings")
def settings() -> dict:
    return {"devices": [{"device": d["device"], "added": d["added"]} for d in service.devices()], "routes": service.routes(),
            "ways": list(service.WAYS)}


@router.put("/route")
def route(body: RouteIn) -> dict:
    try:
        return service.set_route(body.category, body.way)
    except service.PushError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/test")
def test() -> dict:
    n = service.send("AURON", "So sehen meine Mitteilungen aus, Sir.", "system")
    if not n:
        raise HTTPException(status_code=409, detail="kein Gerät hat Mitteilungen eingeschaltet")
    return {"sent_to": n}


@router.post("/notify")
def notify(body: NotifyIn) -> dict:
    """For the copiers on the laptop: their messages reach the app too (same routes and mute as Telegram)."""
    from app.notification_hub import mute
    if mute.muted().get(body.category) and not mute.TROUBLE.search(body.body):
        return {"sent_to": 0, "muted": True}
    if not service.wants(body.category, "app"):
        return {"sent_to": 0}
    return {"sent_to": service.send(body.title, body.body, body.category)}
