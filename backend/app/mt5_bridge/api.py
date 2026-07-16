from uuid import UUID

from fastapi import APIRouter, HTTPException

from .models import (
    MT5BridgeStatus,
    MT5Heartbeat,
    MT5SnapshotIngest,
    MT5TerminalData,
    MT5TerminalRecord,
    MT5TerminalRegister,
)
from .service import MT5BridgeError, mt5_bridge_service

router = APIRouter(prefix="/v1/mt5", tags=["mt5"])


@router.get("/status", response_model=MT5BridgeStatus)
def status() -> MT5BridgeStatus:
    return mt5_bridge_service.status()


@router.post("/terminals", response_model=MT5TerminalRecord)
def register_terminal(payload: MT5TerminalRegister) -> MT5TerminalRecord:
    try:
        return mt5_bridge_service.register(payload)
    except MT5BridgeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/terminals", response_model=list[MT5TerminalData])
def list_terminals() -> list[MT5TerminalData]:
    return mt5_bridge_service.list()


@router.get("/terminals/{terminal_id}", response_model=MT5TerminalData)
def get_terminal(terminal_id: UUID) -> MT5TerminalData:
    try:
        return mt5_bridge_service.get(terminal_id)
    except MT5BridgeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/terminals/{terminal_id}/heartbeat", response_model=MT5TerminalRecord)
def heartbeat(terminal_id: UUID, payload: MT5Heartbeat) -> MT5TerminalRecord:
    try:
        return mt5_bridge_service.heartbeat(terminal_id, payload)
    except MT5BridgeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/terminals/{terminal_id}/snapshot", response_model=MT5TerminalData)
def ingest_snapshot(terminal_id: UUID, payload: MT5SnapshotIngest) -> MT5TerminalData:
    try:
        return mt5_bridge_service.ingest(terminal_id, payload)
    except MT5BridgeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
