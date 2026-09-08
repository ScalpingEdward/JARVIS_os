"""Position monitor API -- read-only status, a manual tick, and a runtime
pause/resume switch.

Neither /status, /tick, /pause, nor /resume ever modifies a stop-loss or
closes a position -- pausing stops the periodic *assessment* from
running, nothing more; it was never the thing touching a broker. See
position_monitor/__init__.py for what this module does and does not do.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter

from .models import MonitorAuditRecord, MonitorStatus, MonitorTickResult
from .service import position_monitor_service

router = APIRouter(prefix="/v1/position-monitor", tags=["position-monitor"])


class ResumeRequest(BaseModel):
    #: Omit to keep whatever interval was last configured (the default on
    #: a fresh process, or whatever /resume last set it to) -- resuming
    #: should not silently reset an operator's earlier choice back to the
    #: module's own default.
    interval_seconds: float | None = Field(default=None, gt=0)


@router.get("/status", response_model=MonitorStatus)
def status() -> MonitorStatus:
    return position_monitor_service.status()


@router.post("/tick", response_model=MonitorTickResult)
def tick() -> MonitorTickResult:
    """Run one assessment pass right now, synchronously."""
    return position_monitor_service.tick()


@router.get("/audit", response_model=list[MonitorAuditRecord])
def audit(limit: int = 50) -> list[MonitorAuditRecord]:
    """Notifications actually sent (and any that failed to send), plus any
    tick that raised -- not every routine tick. Most recent first."""
    return position_monitor_service.audit_records(limit)


@router.post("/pause", response_model=MonitorStatus)
async def pause() -> MonitorStatus:
    """Stop the background loop without restarting the process. Safe to
    call when it is already stopped (a no-op, not an error) -- an
    operator reaching for a kill switch should never have to first check
    whether it is already off."""
    await position_monitor_service.stop()
    return position_monitor_service.status()


@router.post("/resume", response_model=MonitorStatus)
async def resume(request: ResumeRequest = ResumeRequest()) -> MonitorStatus:
    """Start the background loop. Safe to call when already running (a
    no-op -- see PositionMonitorService.start()).

    Must be async, not sync, even though start() itself does no
    awaiting: a sync FastAPI endpoint runs in a threadpool worker
    (via anyio.to_thread), which has no running asyncio event loop --
    asyncio.create_task() inside start() would raise "no running event
    loop" there. Caught by this endpoint's own tests, not left for a
    production 500 to find.
    """
    interval = request.interval_seconds or position_monitor_service.status().interval_seconds
    position_monitor_service.start(interval)
    return position_monitor_service.status()
