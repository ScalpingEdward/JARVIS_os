from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import SimulationCreate, SimulationListResponse, SimulationPlatformStatus, SimulationRecord
from .service import simulation_service

router = APIRouter(prefix="/v1/simulations", tags=["simulation-engine"])


@router.get("/status", response_model=SimulationPlatformStatus)
def platform_status() -> SimulationPlatformStatus:
    return simulation_service.status()


@router.post("", response_model=SimulationRecord, status_code=status.HTTP_201_CREATED)
def create_simulation(payload: SimulationCreate) -> SimulationRecord:
    return simulation_service.create(payload)


@router.get("", response_model=SimulationListResponse)
def list_simulations() -> SimulationListResponse:
    items = simulation_service.list_all()
    return SimulationListResponse(items=items, count=len(items))


@router.get("/{simulation_id}", response_model=SimulationRecord)
def get_simulation(simulation_id: UUID) -> SimulationRecord:
    record = simulation_service.get(simulation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return record


@router.post("/{simulation_id}/run", response_model=SimulationRecord)
def run_simulation(simulation_id: UUID) -> SimulationRecord:
    try:
        record = simulation_service.run(simulation_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return record
