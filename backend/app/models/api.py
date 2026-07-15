from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    task_type: str = Field(default="general", min_length=1, max_length=100)
    provider: str = Field(default="mock", min_length=1, max_length=100)


class GenerateResponse(BaseModel):
    provider: str
    model: str
    content: str


class ProvidersResponse(BaseModel):
    providers: list[str]
