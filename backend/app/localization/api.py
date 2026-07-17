from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord, LocaleMutation, LocaleProfileCreate, LocaleProfileRecord,
    LocalizationStatus, ProfileState, ResolveRecord, ResolveRequest,
    TranslationEntryCreate, TranslationEntryRecord,
)
from .service import localization_service


router = APIRouter(prefix="/v1/localization", tags=["localization"])


@router.get("/status", response_model=LocalizationStatus)
def get_status() -> LocalizationStatus:
    return localization_service.status()


@router.post("/profiles", response_model=LocaleProfileRecord, status_code=status.HTTP_201_CREATED)
def create_profile(payload: LocaleProfileCreate) -> LocaleProfileRecord:
    try:
        return localization_service.create_profile(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/profiles", response_model=list[LocaleProfileRecord])
def list_profiles(workspace_id: str = Query(min_length=1, max_length=120)) -> list[LocaleProfileRecord]:
    return localization_service.list_profiles(workspace_id)


@router.get("/profiles/{profile_id}", response_model=LocaleProfileRecord)
def get_profile(profile_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> LocaleProfileRecord:
    item = localization_service.get_profile(profile_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Locale profile not found")
    return item


def _set_profile(profile_id: UUID, workspace_id: str, payload: LocaleMutation, state: ProfileState) -> LocaleProfileRecord:
    item = localization_service.set_profile_state(profile_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned locale profile not found")
    return item


@router.post("/profiles/{profile_id}/activate", response_model=LocaleProfileRecord)
def activate_profile(profile_id: UUID, payload: LocaleMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> LocaleProfileRecord:
    return _set_profile(profile_id, workspace_id, payload, ProfileState.ACTIVE)


@router.post("/profiles/{profile_id}/suspend", response_model=LocaleProfileRecord)
def suspend_profile(profile_id: UUID, payload: LocaleMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> LocaleProfileRecord:
    return _set_profile(profile_id, workspace_id, payload, ProfileState.SUSPENDED)


@router.post("/profiles/{profile_id}/archive", response_model=LocaleProfileRecord)
def archive_profile(profile_id: UUID, payload: LocaleMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> LocaleProfileRecord:
    return _set_profile(profile_id, workspace_id, payload, ProfileState.ARCHIVED)


@router.post("/translations", response_model=TranslationEntryRecord, status_code=status.HTTP_201_CREATED)
def create_translation(payload: TranslationEntryCreate) -> TranslationEntryRecord:
    try:
        return localization_service.create_translation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/translations", response_model=list[TranslationEntryRecord])
def list_translations(
    workspace_id: str = Query(min_length=1, max_length=120),
    locale: str | None = None,
    namespace: str | None = None,
) -> list[TranslationEntryRecord]:
    return localization_service.list_translations(workspace_id, locale, namespace)


@router.post("/translations/{translation_id}/retire", response_model=TranslationEntryRecord)
def retire_translation(translation_id: UUID, payload: LocaleMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> TranslationEntryRecord:
    item = localization_service.retire_translation(translation_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned translation not found")
    return item


@router.post("/resolve", response_model=ResolveRecord)
def resolve_translation(payload: ResolveRequest) -> ResolveRecord:
    return localization_service.resolve(payload)


@router.get("/resolutions", response_model=list[ResolveRecord])
def list_resolutions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ResolveRecord]:
    return localization_service.list_resolutions(workspace_id)


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return localization_service.list_audit(workspace_id)
