"""Cover licence plates in everything already processed (run once inside the API container):

    python -m app.instagram_content.plates_backfill [image|video]

A file that changed is marked for re-upload (processed_media_ref cleared), so the n8n upload step
puts the covered version into Drive and the post uses that one. A file that cannot be checked is
removed and its item can no longer be posted -- the same rule as at ingest.
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.db import SessionLocal
from app.db_models import InstagramMediaPoolItemRow

from . import plates
from .media_pool_models import MediaPoolItem
from .media_processing import output_dir
from .models import MediaType


DONE_LIST = ".plates-backfill-done"   # in the processed dir: a second run skips what is done


def main(kind: str | None = None) -> None:
    root = output_dir()
    done_file = Path(root) / DONE_LIST
    done = set(done_file.read_text().split()) if done_file.is_file() else set()
    with SessionLocal() as s:
        rows = s.query(InstagramMediaPoolItemRow).all()
    todo = []
    for row in rows:
        item = MediaPoolItem.model_validate_json(row.data)
        if item.processed_file and item.processed_file not in done and (kind is None or item.media_type.value == kind):
            todo.append((row.id, item))
    changed = failed = 0
    for n, (row_id, item) in enumerate(todo, 1):
        path = Path(root) / item.processed_file
        try:
            if not path.is_file():
                raise plates.PlateError("file missing")
            found = plates.video(path) if item.media_type == MediaType.video else plates.photo(path)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[{n}/{len(todo)}] {item.media_ref}: FAILED, held back ({exc})", flush=True)
            path.unlink(missing_ok=True)
            _update(row_id, processed_file=None, processed_media_ref=None)
            continue
        if found:
            changed += 1
            _update(row_id, processed_media_ref=None)   # re-upload the covered file
        with done_file.open("a") as fh:
            fh.write(item.processed_file + chr(10))
        print(f"[{n}/{len(todo)}] {item.media_ref}: {found} covered", flush=True)
    print(f"done: {len(todo)} checked, {changed} changed (re-upload), {failed} held back", flush=True)


def _update(row_id, **fields) -> None:
    with SessionLocal() as s:
        row = s.get(InstagramMediaPoolItemRow, row_id)
        item = MediaPoolItem.model_validate_json(row.data).model_copy(update=fields)
        row.data = item.model_dump_json()
        s.commit()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
