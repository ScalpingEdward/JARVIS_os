from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .real_provider_client import (
    ResearchFetchResult,
    ResearchProviderClient,
    ResearchProviderConfig,
    ResearchProviderFetchError,
)

router = APIRouter(prefix="/v1/research/provider", tags=["research-provider"])

# Deliberately explicit and small. Extending this requires a conscious code
# change and review, never a runtime parameter -- that is what keeps this a
# real allowlist instead of a formality.
DEFAULT_ALLOWED_DOMAINS: tuple[str, ...] = ("api.github.com",)

_client = ResearchProviderClient(config=ResearchProviderConfig(allowed_domains=DEFAULT_ALLOWED_DOMAINS))


class ProviderFetchRequest(BaseModel):
    url: str
    request_id: str | None = Field(default=None, description="Client-supplied idempotency key")


class ProviderFetchResponse(BaseModel):
    request_id: str
    url: str
    status_code: int
    bytes_read: int
    content: str
    fetched_at: str

    @classmethod
    def from_result(cls, result: ResearchFetchResult) -> "ProviderFetchResponse":
        return cls(
            request_id=result.request_id,
            url=result.url,
            status_code=result.status_code,
            bytes_read=result.bytes_read,
            content=result.content,
            fetched_at=result.fetched_at,
        )


@router.post("/fetch", response_model=ProviderFetchResponse)
def fetch(payload: ProviderFetchRequest) -> ProviderFetchResponse:
    """Executes a real, bounded, read-only HTTPS GET against an allowlisted domain.

    This is the first real network call in the research vertical. Everything
    the previous H1-H40 design chain only modeled in the abstract -- identity,
    allowlist, timeout, size bound, exactly-once, audit -- is enforced here.
    """
    try:
        result = _client.fetch(payload.url, request_id=payload.request_id)
    except ResearchProviderFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProviderFetchResponse.from_result(result)
