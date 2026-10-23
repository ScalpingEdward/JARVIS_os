"""AURON's icon: the single glowing ring of the dashboard's AURON button (Brano, 2026-10-23) -- the ring
alone, no light on it: the logo is just the ring.

    python tools/make_ring_icon.py      writes every app / desktop icon into frontend/
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "frontend"
BG, RING = (3, 5, 10, 255), (79, 216, 255)


def _band(img: Image.Image, c: float, rc: float, width: float, color: tuple) -> None:
    """A ring of this width centred on radius rc -- PIL draws an outline inward from its box, so the box
    is grown by half the width: the glow then spreads to both sides of the line, like the button's."""
    o = rc + width / 2
    ImageDraw.Draw(img).ellipse([c - o, c - o, c + o, c + o], outline=color, width=int(width))


def ring(size: int, scale: float = 1.0, bg: bool = True) -> Image.Image:
    """Lit inside and outside like the dashboard button (box-shadow outside + inset glow), Brano 2026-10-23:
    the first version glowed only inward."""
    s = size * 4                                            # drawn large, scaled down smooth
    img = Image.new("RGBA", (s, s), BG if bg else (0, 0, 0, 0))
    rc, w = s * 0.29 * scale, max(2, s * 0.034 * scale)
    c = s / 2
    for width, blur, alpha in ((w * 4, s * 0.045, 120), (w * 2, s * 0.018, 200)):   # soft halo, then a tighter one
        glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        _band(glow, c, rc, width, RING + (alpha,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(blur)))
    _band(img, c, rc, w, RING + (255,))                       # one cyan line, like the logo -- no white core
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
