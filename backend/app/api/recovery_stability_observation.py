from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.recovery_stability_observation import StabilitySample, recovery_stability_observation_service as service

router=APIRouter(prefix="/v1/recovery-stability-observation",tags=["recovery-stability-observation"])

class SampleIn(BaseModel):
    primary_available:bool
    latency_ms:float=Field(ge=0)
    receipt_reconciliation:float=Field(ge=0,le=1)
    worker_heartbeat_ok:bool
    gateway_healthy:bool
    adapter_healthy:bool
    confidence:float=Field(default=1,ge=0,le=1)
    freshness:float=Field(default=1,ge=0,le=1)

class CreateIn(BaseModel):
    record_id:str; workspace_id:str; source_key:str; recovery_attestation_id:str; recovery_attestation_digest:str
    recovery_attestation_state:str; operation:str; target:str; samples:list[SampleIn]
    max_latency_ms:float=Field(default=1500,gt=0); min_reconciliation:float=Field(default=.95,ge=0,le=1)
    upstream_risk_brain_blocked:bool=False; requested_by:str="system"

class ActionIn(BaseModel):
    workspace_id:str; action:str; actor:str; operation_id:str; reason:str|None=None

@router.get("/status")
def status(): return service.status()

@router.post("/records")
def create_record(p:CreateIn):
    try:
        d=p.model_dump(); d["samples"]=[StabilitySample(**x) for x in d["samples"]]; return service.create(**d).__dict__
    except ValueError as e: raise HTTPException(status_code=409,detail=str(e)) from e

@router.get("/records")
def list_records(workspace_id:str=Query(min_length=1)): return [r.__dict__ for r in service.list(workspace_id)]

@router.get("/records/{record_id}")
def get_record(record_id:str,workspace_id:str=Query(min_length=1)):
    try:return service.get(workspace_id,record_id).__dict__
    except KeyError as e: raise HTTPException(status_code=404,detail=str(e)) from e

@router.post("/records/{record_id}/actions")
def act(record_id:str,p:ActionIn):
    try:return service.act(p.workspace_id,record_id,p.action,p.actor,p.operation_id,p.reason).__dict__
    except KeyError as e: raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e: raise HTTPException(status_code=409,detail=str(e)) from e

@router.get("/audit")
def audit(workspace_id:str=Query(min_length=1)): return service.audit(workspace_id)
