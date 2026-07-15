from fastapi import FastAPI, HTTPException

from .config import get_settings
from .models.api import GenerateRequest, GenerateResponse, ProvidersResponse
from .models.contracts import ModelRequest
from .models.router import UnknownProviderError, model_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.version)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.version,
        "status": "online",
    }


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
    }


@app.get("/v1/models/providers", response_model=ProvidersResponse, tags=["models"])
def list_model_providers() -> ProvidersResponse:
    return ProvidersResponse(providers=model_router.available_providers())


@app.post("/v1/models/generate", response_model=GenerateResponse, tags=["models"])
def generate_model_response(payload: GenerateRequest) -> GenerateResponse:
    try:
        result = model_router.generate(
            ModelRequest(prompt=payload.prompt, task_type=payload.task_type),
            provider_name=payload.provider,
        )
    except UnknownProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GenerateResponse(
        provider=result.provider,
        model=result.model,
        content=result.content,
    )
