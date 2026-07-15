from fastapi import APIRouter, HTTPException

from .models import CommandRequest, CommandResponse
from .service import CommandExecutionError, command_service

router = APIRouter(prefix="/v1/commands", tags=["commands"])


@router.post("/execute", response_model=CommandResponse)
def execute_command(payload: CommandRequest) -> CommandResponse:
    try:
        return command_service.execute(payload)
    except CommandExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
