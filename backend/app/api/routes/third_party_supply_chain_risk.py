from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.third_party_supply_chain_risk import ThirdPartyRiskAction, ThirdPartyRiskCreate, ThirdPartyRiskRecord
from app.services.third_party_supply_chain_risk import third_party_supply_chain_risk_service

router = APIRouter(prefix="/v1/third-party-supply-chain-risk", tags=["third-party-supply-chain-risk"])


@router.get("/status")
def status() -> dict:
    return third_party_supply_chain_risk_service.status()


@router.post("/records", response_model=ThirdPartyRiskRecord)
def create_record(payload: ThirdPartyRiskCreate) -> ThirdPartyRiskRecord:
    try:
        return third_party_supply_chain_risk_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ThirdPartyRiskRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ThirdPartyRiskRecord]:
    return third_party_supply_chain_risk_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ThirdPartyRiskRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ThirdPartyRiskRecord:
    try:
        return third_party_supply_chain_risk_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ThirdPartyRiskRecord)
def act_on_record(record_id: str, payload: ThirdPartyRiskAction) -> ThirdPartyRiskRecord:
    try:
        return third_party_supply_chain_risk_service.act(
            payload.workspace_id,
            record_id,
            payload.action,
            payload.actor,
            payload.operation_id,
            payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in third_party_supply_chain_risk_service.audit(workspace_id)]
