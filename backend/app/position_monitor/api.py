"""Position monitor API -- read-only status, plus a manual tick for
operators who want to trigger one pass without waiting for the timer
(useful right after registering a new terminal, or in an environment
where the background loop is deliberately left off).

Neither endpoint modifies a stop-loss or closes a position. See
position_monitor/__init__.py for what this module does and does not do.
"""

from __future__ import annotations

from fastapi import APIRouter

from .models import MonitorStatus, MonitorTickResult
from .service import position_monitor_service

router = APIRouter(prefix="/v1/position-monitor", tags=["position-monitor"])


@router.get("/status", response_model=MonitorStatus)
def status() -> MonitorStatus:
    return position_monitor_service.status()


@router.post("/tick", response_model=MonitorTickResult)
def tick() -> MonitorTickResult:
    """Run one assessment pass right now, synchronously."""
    return position_monitor_service.tick()
