"""A new room for the dashboard, from one of Brano's pictures (Krea, Ideogram ...).

    python tools/add_room.py SOURCE KEY "NAME" --ped X,Y,W [--zones JSON]

    SOURCE  the picture, 4K (3840x2160) or larger; another aspect ratio is cut to 16:9 around the middle
    KEY     short name, a-z 0-9 - (e.g. earth2) -- also what AURON and the look use
    NAME    what the design menu shows (e.g. "Über der Erde II")
    --ped   the pedestal's top: centre x, centre y, width -- fractions of the picture (0..1)
    --zones the animated areas, as in rooms/rooms.js: [["stars", x0, y0, x1, y1], ...]

Writes frontend/rooms/KEY.webp (3840x2160), adds or replaces the entry in rooms/rooms.js (the design
menu and the room shader read it from there) and in AURON's design catalog (dashboard_design). The
pedestal and the zones are measured by looking at the picture, per picture -- there is no default:
a guessed pedestal puts the planet next to it, a guessed zone makes a window frame ripple.
"""
import argparse
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ROOMS = ROOT / "frontend" / "rooms"
W, H = 3840, 2160


def picture(src: Path, out: Path) -> None:
    im = Image.open(src).convert("RGB")
    if im.width < W * 0.9:
        raise SystemExit(f"{src.name} is {im.width}x{im.height} -- needs 4K (3840 wide), else it looks soft")
    r = im.width / im.height
    if abs(r - W / H) > 0.01:                       # cut to 16:9 around the middle, never stretch
        if r > W / H:
            w = round(im.height * W / H); x = (im.width - w) // 2; im = im.crop((x, 0, x + w, im.height))
        else:
            h = round(im.width * H / W); y = (im.height - h) // 2; im = im.crop((0, y, im.width, y + h))
    im.resize((W, H), Image.LANCZOS).save(out, "WEBP", quality=84, method=6)


def entry(key: str, name: str, ped: list[float], zones: list) -> str:
    z = ", ".join("[" + ", ".join(json.dumps(v) for v in zone) + "]" for zone in zones)
    return (f"  {key}: {{ name: {json.dumps(name, ensure_ascii=False).replace(chr(34), chr(39))}, src: 'rooms/{key}.webp', "
            f"w: {W}, h: {H}, ped: [{', '.join(f'{v:.3f}' for v in ped)}], zones: [\n    {z}] }},\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("key"); ap.add_argument("name")
    ap.add_argument("--ped", required=True); ap.add_argument("--zones", default="[]")
    a = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{2,24}", a.key):
        raise SystemExit("key: 2-24 of a-z 0-9 -")
    ped = [float(v) for v in a.ped.split(",")]
    zones = json.loads(a.zones)
    picture(Path(a.source), ROOMS / f"{a.key}.webp")

    js = ROOMS / "rooms.js"
    s = js.read_text(encoding="utf-8")
    s = re.sub(rf"\n  {re.escape(a.key)}: \{{.*?\] \}},\n", "\n", s, flags=re.S)       # replace, not duplicate
    s = s.replace("\n};", "\n" + entry(a.key, a.name, ped, zones).rstrip("\n") + "\n};", 1)
    js.write_text(s, encoding="utf-8")

    look = ROOT / "backend" / "app" / "dashboard_layout" / "look.py"
    t = look.read_text(encoding="utf-8")
    item = f'"{a.key} {a.name}"'
    if f'"{a.key} ' not in t:
        t = re.sub(r'("room": \[[^\]]*?)\]', lambda m: f"{m.group(1)}, {item}]", t, count=1)
        look.write_text(t, encoding="utf-8")
    print(f"rooms/{a.key}.webp + rooms.js + AURON's catalog -- rebuild frontend and api")


if __name__ == "__main__":
    main()
