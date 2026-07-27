from fastapi import APIRouter, HTTPException, Query
from app.schemas.trust_calibrated_execution_selection import SelectionAction, SelectionCreate, SelectionRecord
from app.services.trust_calibrated_execution_selection import trust_calibrated_execution_selection_service as service

router=APIRouter(prefix='/v1/trust-calibrated-execution-selection',tags=['trust-calibrated-execution-selection'])

@router.get('/status')
def status(): return service.status()

@router.post('/records',response_model=SelectionRecord)
def create_record(payload:SelectionCreate):
    try: return service.create(payload)
    except ValueError as e: raise HTTPException(status_code=409,detail=str(e)) from e

@router.get('/records',response_model=list[SelectionRecord])
def list_records(workspace_id:str=Query(min_length=1)): return service.list(workspace_id)

@router.get('/records/{record_id}',response_model=SelectionRecord)
def get_record(record_id:str,workspace_id:str=Query(min_length=1)):
    try: return service.get(workspace_id,record_id)
    except KeyError as e: raise HTTPException(status_code=404,detail=str(e)) from e

@router.post('/records/{record_id}/actions',response_model=SelectionRecord)
def act(record_id:str,payload:SelectionAction):
    try: return service.act(payload.workspace_id,record_id,payload.action,payload.actor,payload.operation_id,payload.reason)
    except KeyError as e: raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e: raise HTTPException(status_code=409,detail=str(e)) from e

@router.get('/audit')
def audit(workspace_id:str=Query(min_length=1)): return service.audit(workspace_id)
