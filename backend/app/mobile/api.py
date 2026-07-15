from fastapi import APIRouter, HTTPException

from .models import MobileControlStatus, MobileReply, TelegramUpdate
from .service import MobileControlError, mobile_control_service

router = APIRouter(prefix="/v1/mobile", tags=["mobile"])


@router.post("/telegram/update", response_model=MobileReply)
def telegram_update(payload: TelegramUpdate) -> MobileReply:
    try:
        return mobile_control_service.handle(payload)
    except MobileControlError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/status", response_model=MobileControlStatus)
def mobile_status() -> MobileControlStatus:
    return mobile_control_service.status()
