from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ..autonomous_research.api import router as autonomous_research_router
from ..collaboration_mesh.api import router as collaboration_mesh_router
from ..config_control.api import router as config_control_router
from ..decision_memory.api import router as decision_memory_router
from ..digital_twin.api import router as digital_twin_router
from ..live_integrations.api import router as live_integrations_router
from ..notification_hub.api import router as notification_hub_router
from ..personal_ceo.api import router as personal_ceo_router
from ..predictive_intelligence.api import router as predictive_intelligence_router
from ..proactive_operations.api import router as proactive_operations_router
from ..readiness_center.api import router as readiness_center_router
from ..strategic_planning.api import router as strategic_planning_router
from .models import MarketVisionCreate, MarketVisionListResponse, MarketVisionRecord, MarketVisionStatus
from .service import market_vision_service


router = APIRouter(tags=["market-vision"])


@router.get("/v1/market-vision/status", response_model=MarketVisionStatus)
def vision_status() -> MarketVisionStatus:
    return market_vision_service.status()


@router.post("/v1/market-vision/analyses", response_model=MarketVisionRecord, status_code=status.HTTP_201_CREATED)
def create_analysis(payload: MarketVisionCreate) -> MarketVisionRecord:
    return market_vision_service.create(payload)


@router.get("/v1/market-vision/analyses", response_model=MarketVisionListResponse)
def list_analyses(symbol: str | None = Query(default=None, max_length=40)) -> MarketVisionListResponse:
    items = market_vision_service.list_all(symbol=symbol)
    return MarketVisionListResponse(items=items, count=len(items))


@router.get("/v1/market-vision/analyses/{analysis_id}", response_model=MarketVisionRecord)
def get_analysis(analysis_id: UUID) -> MarketVisionRecord:
    record = market_vision_service.get(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market vision analysis not found")
    return record


@router.get("/v1/market-vision/latest/{symbol}", response_model=MarketVisionRecord)
def latest_analysis(symbol: str) -> MarketVisionRecord:
    record = market_vision_service.latest(symbol)
    if record is None:
        raise HTTPException(status_code=404, detail="No market vision analysis found")
    return record


router.include_router(autonomous_research_router)
router.include_router(personal_ceo_router)
router.include_router(live_integrations_router)
router.include_router(collaboration_mesh_router)
router.include_router(proactive_operations_router)
router.include_router(notification_hub_router)
router.include_router(config_control_router)
router.include_router(readiness_center_router)
router.include_router(digital_twin_router)
router.include_router(decision_memory_router)
router.include_router(strategic_planning_router)
router.include_router(predictive_intelligence_router)
