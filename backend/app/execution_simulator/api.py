from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import (
    ExecutionReport,
    SimulationOrderCreate,
    SimulationOrderList,
    SimulationOrderRecord,
    SimulatorStatus,
)
from .service import execution_simulator_service


router = APIRouter(prefix="/v1/execution-simulator", tags=["execution-simulator"])


@router.get("/status", response_model=SimulatorStatus)
def simulator_status() -> SimulatorStatus:
    return execution_simulator_service.status()


@router.post("/orders", response_model=SimulationOrderRecord, status_code=status.HTTP_201_CREATED)
def create_order(payload: SimulationOrderCreate) -> SimulationOrderRecord:
    return execution_simulator_service.create(payload)


@router.get("/orders", response_model=SimulationOrderList)
def list_orders() -> SimulationOrderList:
    items = execution_simulator_service.list_all()
    return SimulationOrderList(items=items, count=len(items))


@router.get("/orders/{order_id}", response_model=SimulationOrderRecord)
def get_order(order_id: UUID) -> SimulationOrderRecord:
    record = execution_simulator_service.get(order_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Simulation order not found")
    return record


@router.post("/orders/{order_id}/cancel", response_model=SimulationOrderRecord)
def cancel_order(order_id: UUID) -> SimulationOrderRecord:
    record = execution_simulator_service.cancel(order_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Simulation order not found")
    return record


@router.get("/report", response_model=ExecutionReport)
def execution_report() -> ExecutionReport:
    return execution_simulator_service.report()
