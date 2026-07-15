from fastapi import FastAPI

from .config import get_settings

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
