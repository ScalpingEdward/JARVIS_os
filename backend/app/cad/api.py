from fastapi import APIRouter, HTTPException, Response

from . import service
from .engine import CadError

router = APIRouter(prefix="/v1/cad", tags=["cad"])


@router.get("")
def list_parts() -> list[dict]:
    """AURON's 3D parts, newest first."""
    return service.parts()


@router.get("/{part_id}")
def part(part_id: str) -> dict:
    try:
        return service.get(part_id)
    except CadError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{part_id}/part.stl")
def part_stl(part_id: str) -> Response:
    """The STL for the 3D view -- and for the printer's slicer."""
    try:
        meta, data = service.get(part_id), service.stl(part_id)
    except (CadError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    fname = "".join(c if c.isalnum() or c in "-_" else "_" for c in meta["name"]) or part_id
    return Response(data, media_type="model/stl", headers={"Content-Disposition": f'attachment; filename="{fname}.stl"'})
