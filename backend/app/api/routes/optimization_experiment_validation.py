from fastapi import APIRouter, HTTPException, Query
from app.schemas.optimization_experiment_validation import ExperimentAction, ExperimentCreate, ExperimentRecord
from app.services.optimization_experiment_validation import optimization_experiment_validation_service as service

router=APIRouter(prefix="/v1/optimization-experiments",tags=["optimization-experiments"])

@router.get("/status")
def status(): return service.status()

@router.post("/records",response_model=ExperimentRecord)
def create_record(payload:ExperimentCreate):
    try: return service.create(payload)
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc

@router.get("/records",response_model=list[ExperimentRecord])
def list_records(workspace_id:str=Query(min_length=1)): return service.list(workspace_id)

@router.get("/records/{record_id}",response_model=ExperimentRecord)
def get_record(record_id:str,workspace_id:str=Query(min_length=1)):
    try: return service.get(workspace_id,record_id)
    except KeyError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc

@router.post("/records/{record_id}/actions",response_model=ExperimentRecord)
def act(record_id:str,payload:ExperimentAction):
    try: return service.act(payload.workspace_id,record_id,payload.action,payload.actor,payload.operation_id,payload.reason)
    except KeyError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc

@router.get("/audit")
def audit(workspace_id:str=Query(min_length=1)): return service.audit(workspace_id)
