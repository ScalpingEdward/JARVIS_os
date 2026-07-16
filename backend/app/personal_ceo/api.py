from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import ExecutiveBriefing, ExecutiveBriefingCreate, PersonalCEOProfile, PersonalCEOStatus
from .service import personal_ceo_service


router = APIRouter(prefix="/v1/personal-ceo", tags=["personal-ceo"])


@router.get("/status", response_model=PersonalCEOStatus)
def ceo_status() -> PersonalCEOStatus:
    return personal_ceo_service.status()


@router.get("/profile", response_model=PersonalCEOProfile)
def get_profile() -> PersonalCEOProfile:
    return personal_ceo_service.profile()


@router.put("/profile", response_model=PersonalCEOProfile)
def update_profile(payload: PersonalCEOProfile) -> PersonalCEOProfile:
    return personal_ceo_service.update_profile(payload)


@router.post("/briefings", response_model=ExecutiveBriefing, status_code=status.HTTP_201_CREATED)
def create_briefing(payload: ExecutiveBriefingCreate) -> ExecutiveBriefing:
    return personal_ceo_service.create_briefing(payload)


@router.get("/briefings", response_model=list[ExecutiveBriefing])
def list_briefings() -> list[ExecutiveBriefing]:
    return personal_ceo_service.list_briefings()


@router.get("/briefings/latest", response_model=ExecutiveBriefing)
def latest_briefing() -> ExecutiveBriefing:
    briefing = personal_ceo_service.latest()
    if briefing is None:
        raise HTTPException(status_code=404, detail="No executive briefing found")
    return briefing


@router.get("/briefings/{briefing_id}", response_model=ExecutiveBriefing)
def get_briefing(briefing_id: UUID) -> ExecutiveBriefing:
    briefing = personal_ceo_service.get(briefing_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="Executive briefing not found")
    return briefing
