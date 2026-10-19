from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except service.LayoutError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/layout")
def get_layout() -> dict:
    """Which cards, where, in what order -- the same on every screen."""
    return service.get()


@router.put("/layout")
def put_layout(layout: dict) -> dict:
    return _guard(service.save, layout)


@router.post("/layout/reset")
def reset_layout() -> dict:
    return service.reset()


class NoteIn(BaseModel):
    text: str


class NotePatch(BaseModel):
    done: bool | None = None
    delete: bool = False


@router.get("/notes")
def get_notes() -> list[dict]:
    return service.notes()


@router.post("/notes")
def add_note(body: NoteIn) -> list[dict]:
    return _guard(service.add_note, body.text)


@router.patch("/notes/{note_id}")
def patch_note(note_id: str, body: NotePatch) -> list[dict]:
    return _guard(service.set_note, note_id, body.done, body.delete)
