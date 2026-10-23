"""AURON's icon: the single glowing ring of the dashboard's AURON button (Brano, 2026-10-23) -- the ring
alone, no light on it: the logo is just the ring.

    python tools/make_ring_icon.py      writes every app / desktop icon into frontend/
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "frontend"
BG, RING = (3, 5, 10, 255), (79, 216, 255)


def ring(size: int, scale: float = 1.0, bg: bool = True) -> Image.Image:
    s = size * 4                                            # drawn large, scaled down smooth
    img = Image.new("RGBA", (s, s), BG if bg else (0, 0, 0, 0))
    r, w = s * 0.31 * scale, max(2, s * 0.04 * scale)
    c = s / 2
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([c - r, c - r, c + r, c + r], outline=RING + (255,), width=int(w * 2.2))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s * 0.035)))
    d = ImageDraw.Draw(img)
    d.ellipse([c - r, c - r, c + r, c + r], outline=RING + (255,), width=int(w))
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    for name, size in [("icon-192.png", 192), ("icon-512.png", 512), ("app-icon-192.png", 192), ("app-icon-512.png", 512),
                       ("apple-touch-icon.png", 180), ("app-icon-1024.png", 1024)]:
        ring(size).convert("RGB").save(OUT / name)
    ring(512, scale=0.78).convert("RGB").save(OUT / "app-icon-maskable-512.png")   # inside the maskable safe zone
    ring(256).save(OUT / "auron-planet.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icons written")


if __name__ == "__main__":
    main()
