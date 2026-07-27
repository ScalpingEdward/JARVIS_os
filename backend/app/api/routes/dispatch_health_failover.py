from fastapi import APIRouter, HTTPException, Query
from app.schemas.dispatch_health_failover import DispatchHealthAction, DispatchHealthCreate, DispatchHealthRecord
from app.services.dispatch_health_failover import dispatch_health_failover_service as service

router=APIRouter(prefix="/v1/dispatch-health-failover",tags=["dispatch-health-failover"])

@router.get("/status")
def status(): return service.status()

@router.post("/records",response_model=DispatchHealthRecord)
def create_record(payload:DispatchHealthCreate):
    try:return service.create(payload)
    except ValueError as e:raise HTTPException(status_code=409,detail=str(e)) from e

@router.get("/records",response_model=list[DispatchHealthRecord])
def list_records(workspace_id:str=Query(min_length=1)): return service.list(workspace_id)

@router.get("/records/{record_id}",response_model=DispatchHealthRecord)
def get_record(record_id:str,workspace_id:str=Query(min_length=1)):
    try:return service.get(workspace_id,record_id)
    except KeyError as e:raise HTTPException(status_code=404,detail=str(e)) from e

@router.post("/records/{record_id}/actions",response_model=DispatchHealthRecord)
def act(record_id:str,payload:DispatchHealthAction):
    try:return service.act(payload.workspace_id,record_id,payload.action,payload.actor,payload.operation_id,payload.reason)
    except KeyError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=409,detail=str(e)) from e

@router.get("/audit")
def audit(workspace_id:str=Query(min_length=1)): return service.audit(workspace_id)
