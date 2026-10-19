"""Licence plates are made unreadable before anything leaves this machine.

Runs at ingest, right after grading/cutting, on the processed file -- the one that is uploaded and
posted. The detector is a small YOLO-v9 model (open-image-models, MIT, ~8 MB ONNX) baked into the
image at build time (Dockerfile, checksum pinned): no download at runtime, no picture leaves the
laptop.

Recall over precision: a smudge on a bumper costs nothing, a readable plate on Instagram does. So
the threshold is low (0.2) and a large photo is searched again in four overlapping tiles -- at the
model's 640 px, a plate on a car in the background is a few pixels and only shows up in a tile.

A failure is never silent: the caller drops the processed file, and an item without one cannot be
posted (_post_refs refuses rather than falling back to the original).
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_PATH = Path(os.getenv("AURON_PLATE_MODEL", "/opt/models/plates-yolo-v9-t-640.onnx"))
CONF = 0.2
TILE_ABOVE_PX = 1400        # photos larger than this are also searched in 2x2 tiles
VIDEO_EVERY_N = 5           # detect on every 5th frame, hold each box for the frames around it
PAD = 0.25                  # grow each box so the whole plate frame is covered


class PlateError(RuntimeError):
    pass


_det = None


def _detector():
    global _det
    if _det is None:
        if not MODEL_PATH.is_file():
            raise PlateError(f"plate model missing at {MODEL_PATH} -- the image is built with it (Dockerfile)")
        from open_image_models import create_detector
        _det = create_detector(str(MODEL_PATH), backend="yolo_v9", class_labels=["License Plate"], conf_thresh=CONF)
    return _det


def find(img) -> list[tuple[int, int, int, int]]:
    """Boxes (x1, y1, x2, y2) of every plate in a BGR image."""
    h, w = img.shape[:2]
    views = [(0, 0, img)]
    if max(h, w) > TILE_ABOVE_PX:
        th, tw = int(h * 0.6), int(w * 0.6)
        for y in (0, h - th):
            for x in (0, w - tw):
                views.append((x, y, img[y:y + th, x:x + tw]))
    boxes = []
    for ox, oy, view in views:
        for d in _detector().predict(view):
            b = d.bounding_box
            boxes.append((b.x1 + ox, b.y1 + oy, b.x2 + ox, b.y2 + oy))
    return boxes


def cover(img, boxes) -> None:
    """Pixelate, then blur -- unreadable, and it does not look like a black bar on the photo."""
    import cv2
    h, w = img.shape[:2]
    for x1, y1, x2, y2 in boxes:
        px, py = int((x2 - x1) * PAD), int((y2 - y1) * PAD)
        x1, y1, x2, y2 = max(0, x1 - px), max(0, y1 - py), min(w, x2 + px), min(h, y2 + py)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        roi = img[y1:y2, x1:x2]
        small = cv2.resize(roi, (max(1, (x2 - x1) // 12), max(1, (y2 - y1) // 12)), interpolation=cv2.INTER_LINEAR)
        roi = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
        k = max(3, ((min(x2 - x1, y2 - y1) // 4) | 1))
        img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)


def photo(path: Path) -> int:
    """Cover every plate in the photo, in place. Returns how many."""
    import cv2
    img = cv2.imread(str(path))
    if img is None:
        raise PlateError(f"cannot read {path.name}")
    boxes = find(img)
    if boxes:
        cover(img, boxes)
        if not cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 95]):
            raise PlateError(f"cannot write {path.name}")
    return len(boxes)


def video(path: Path, ffmpeg: str = "ffmpeg") -> int:
    """Cover every plate in the clip, in place (audio kept). Returns frames with a plate.

    Two passes over the file, frame by frame -- a 30 s clip in full HD held in memory at once
    would be over 5 GB, more than the Docker VM has."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise PlateError(f"cannot open {path.name}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    hits: dict[int, list] = {}
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % VIDEO_EVERY_N == 0:
            boxes = find(f)
            if boxes:
                hits[i] = boxes
        i += 1
    cap.release()
    if i == 0:
        raise PlateError(f"no frames in {path.name}")
    if not hits:
        return 0

    cap = cv2.VideoCapture(str(path))
    ok, first = cap.read()
    h, w = first.shape[:2]
    out = path.with_name(path.stem + ".plates.mp4")
    cmd = [ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps:.3f}", "-i", "-",
           "-i", str(path), "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
           "-pix_fmt", "yuv420p", "-c:a", "copy", "-threads", "2", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    covered, n, f = 0, 0, first
    try:
        while ok:
            base = n - n % VIDEO_EVERY_N   # boxes from the detection before and after: a moving car stays covered
            near = hits.get(base, []) + hits.get(base + VIDEO_EVERY_N, [])
            if near:
                cover(f, near)
                covered += 1
            proc.stdin.write(f.tobytes())
            n += 1
            ok, f = cap.read()
        proc.stdin.close()
        err = proc.stderr.read()
        proc.wait()
    finally:
        cap.release()
    if proc.returncode != 0 or not out.is_file():
        out.unlink(missing_ok=True)
        raise PlateError(f"ffmpeg could not write {path.name}: {err.decode('utf-8', 'replace')[-300:]}")
    out.replace(path)
    return covered
