from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from .models import (
    AccountComplianceStatus,
    AccountStateUpdate,
    StrategyAssignment,
    StrategyAssignmentCreate,
    TradingAccountCreate,
    TradingAccountRecord,
)
from .service import AccountRegistryError, account_registry_service

router = APIRouter(prefix="/v1/accounts", tags=["accounts"])


@router.post("", response_model=TradingAccountRecord, status_code=201)
def register_account(payload: TradingAccountCreate) -> TradingAccountRecord:
    try:
        return account_registry_service.register_account(payload)
    except AccountRegistryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[TradingAccountRecord])
def list_accounts() -> list[TradingAccountRecord]:
    return account_registry_service.list_accounts()


@router.get("/{account_id}", response_model=TradingAccountRecord)
def get_account(account_id: UUID) -> TradingAccountRecord:
    try:
        return account_registry_service.get_account(account_id)
    except AccountRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{account_id}/strategies", response_model=list[StrategyAssignment])
def list_strategies(account_id: UUID) -> list[StrategyAssignment]:
    try:
        return account_registry_service.list_assignments(account_id)
    except AccountRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{account_id}/strategies", response_model=StrategyAssignment, status_code=201)
def assign_strategy(account_id: UUID, payload: StrategyAssignmentCreate) -> StrategyAssignment:
    try:
        return account_registry_service.assign_strategy(account_id, payload)
    except AccountRegistryError as exc:
        status_code = 404 if "not found" in str(exc) else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{account_id}/strategies/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_strategy(account_id: UUID, strategy_id: str) -> Response:
    try:
        account_registry_service.unassign_strategy(account_id, strategy_id)
    except AccountRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{account_id}/state", response_model=TradingAccountRecord)
def update_state(account_id: UUID, payload: AccountStateUpdate) -> TradingAccountRecord:
    try:
        return account_registry_service.update_state(account_id, payload)
    except AccountRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{account_id}/compliance", response_model=AccountComplianceStatus)
def compliance(account_id: UUID) -> AccountComplianceStatus:
    try:
        return account_registry_service.compliance(account_id)
    except AccountRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{account_id}/suspend", response_model=TradingAccountRecord)
def suspend(account_id: UUID) -> TradingAccountRecord:
    try:
        return account_registry_service.suspend(account_id)
    except AccountRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{account_id}/activate", response_model=TradingAccountRecord)
def activate(account_id: UUID) -> TradingAccountRecord:
    try:
        return account_registry_service.activate(account_id)
    except AccountRegistryError as exc:
        status_code = 404 if "not found" in str(exc) else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
