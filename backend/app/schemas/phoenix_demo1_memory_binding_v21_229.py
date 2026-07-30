from pydantic import BaseModel, Field


class MemoryContextQuery(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=8, ge=1, le=25)
    min_priority: int = Field(default=1, ge=1, le=4)
    include_content: bool = True
    risk_brain_hard_block: bool = False


class MemoryContextItem(BaseModel):
    memory_id: str
    category: str
    priority: int
    tags: list[str]
    content: str | None
    relevance_score: float


class MemoryContextResponse(BaseModel):
    version: str = 'v21.229'
    state: str
    provider: str
    provider_bound: bool
    query: str
    items: list[MemoryContextItem]
    count: int
    context_available: bool
    reasons: list[str]
