from fastapi import APIRouter, HTTPException

from .models import (
    CommandRequest,
    CommandResponse,
    NaturalLanguageRequest,
    NaturalLanguageResponse,
)
from .natural import NaturalLanguageParseError, natural_language_parser
from .service import CommandExecutionError, command_service

router = APIRouter(prefix="/v1/commands", tags=["commands"])


@router.post("/execute", response_model=CommandResponse)
def execute_command(payload: CommandRequest) -> CommandResponse:
    try:
        return command_service.execute(payload)
    except CommandExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/natural", response_model=NaturalLanguageResponse)
def execute_natural_language(payload: NaturalLanguageRequest) -> NaturalLanguageResponse:
    try:
        parsed = natural_language_parser.parse(payload.text)
        result = command_service.execute(parsed.command) if payload.execute else None
        return NaturalLanguageResponse(
            recognized=True,
            confidence=parsed.confidence,
            command=parsed.command,
            result=result,
        )
    except NaturalLanguageParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CommandExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
