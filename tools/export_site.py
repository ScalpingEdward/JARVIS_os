"""Pack the website draft into ONE html file (styles, scripts, pictures inside) for showing it
to someone without publishing it -- e.g. to upload to ChatGPT for copy work.

    python tools/export_site.py   ->  frontend/site/export/auron-website.html

Rooms are shrunk to 1920 px so the file stays small; the globe and d3 still load from the CDN.
"""
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

FRONT = Path(__file__).resolve().parent.parent / "frontend"
SITE = FRONT / "site"
OUT = SITE / "export"


def data_uri(path: Path, max_w: int | None = None, quality: int = 72) -> str:
    if max_w and path.suffix == ".webp":
        im = Image.open(path)
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=quality)
        raw, kind = buf.getvalue(), "image/webp"
    else:
        raw, kind = path.read_bytes(), "image/webp" if path.suffix == ".webp" else "image/png"
    return f"data:{kind};base64,{base64.b64encode(raw).decode()}"


def main() -> None:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    html = html.replace('<link rel="icon" href="../auron.ico" />\n', "")
    html = html.replace('<link rel="stylesheet" href="./site.css" />', f"<style>\n{(SITE / 'site.css').read_text(encoding='utf-8')}\n</style>")

    # rooms: one shrunk copy each, used by the hero, the page background and the room row
    rooms_js = (FRONT / "rooms" / "rooms.js").read_text(encoding="utf-8")
    srcs = dict(re.findall(r"(\w+): \{ name: '[^']*', src: '([^']+)'", rooms_js))
    uris = {k: data_uri(FRONT / s, max_w=1920) for k, s in srcs.items() if (FRONT / s).exists()}
    for k, s in srcs.items():
        html = html.replace(f'src="../{s}"', f'src="{uris[k]}"') if k in uris else html
    patch = f"\n<script>Object.entries({json.dumps(uris)}).forEach(([k, u]) => {{ if (window.AURON_ROOMS[k]) window.AURON_ROOMS[k].src = u; }});</script>"
    hero = (SITE / "hero.js").read_text(encoding="utf-8").replace("const src = (k) => `../${ROOMS[k].src}`;", "const src = (k) => ROOMS[k].src;")
    html = html.replace('<script src="../globe.js"></script>', f"<script>\n{(FRONT / 'globe.js').read_text(encoding='utf-8')}\n</script>")
    html = html.replace('<script src="../rooms/rooms.js"></script>', f"<script>\n{rooms_js}\n</script>{patch}")
    html = html.replace('<script src="./hero.js"></script>', f"<script>\n{hero}\n</script>")
    html = html.replace('<script src="./i18n.js"></script>', f"<script>\n{(SITE / 'i18n.js').read_text(encoding='utf-8')}\n</script>")
    for name in ("dashboard.webp", "phoenix-mark.png", "hologram.webp"):
        if not (SITE / "img" / name).exists():
            continue
        html = html.replace(f'src="./img/{name}"', f'src="{data_uri(SITE / "img" / name)}"')
    html = html.replace("<!-- Entwurf: nicht veröffentlicht, keine Anbindungen. Bilder der Räume kommen aus ../rooms/. -->",
                        "<!-- Entwurf von AURON / Phoenix Life Solutions -- nicht veröffentlicht. Alles in einer Datei. -->")
    OUT.mkdir(exist_ok=True)
    (OUT / "auron-website.html").write_text(html, encoding="utf-8")
    left = re.findall(r'(?:src|href)="(\.\./[^"]+|\./img/[^"]+)"', html)
    print(f"{OUT / 'auron-website.html'}: {len(html) / 1e6:.1f} MB; unresolved: {left}")


def artifact(out: Path) -> None:
    """The same page as a claude.ai artifact (the shared promo link): no html/head/body wrapper (the
    artifact adds its own), and the globe's world map inline -- the artifact frame blocks fetch()."""
    import re
    import urllib.request
    s = (OUT / "auron-website.html").read_text(encoding="utf-8")
    url = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-110m.json"
    land = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    s = s.replace(f"await (await fetch('{url}')).json()", land)
    head = s[s.index("<head>") + 6:s.index("</head>")]
    head = re.sub(r'<meta charset[^>]*>\s*|<meta name="viewport"[^>]*>\s*', "", head)
    head = re.sub(r"<title>.*?</title>", "<title>AURON Website</title>", head, count=1)
    body = s[s.index("<body>") + 6:s.rindex("</body>")]
    out.write_text(head + "<style>:root{color-scheme:dark} body{background:#05070c}</style>\n" + body, encoding="utf-8")
    print(f"{out}: {out.stat().st_size / 1e6:.1f} MB")


def pages(out: Path) -> None:
    """A folder to upload as it is to a static host (Cloudflare Pages, Netlify): the one-file page as
    index.html, the legal pages with their stylesheet, the icon, and a header that keeps search
    engines out until Brano decides otherwise."""
    import shutil
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(OUT / "auron-website.html", out / "index.html")
    for name in ("impressum.html", "datenschutz.html", "agb.html", "site.css"):
        shutil.copy(SITE / name, out / name)
    shutil.copy(FRONT / "app-icon-192.png", out / "favicon.png")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n", encoding="utf-8")
    print(f"{out}: {', '.join(sorted(p.name for p in out.iterdir()))}")


if __name__ == "__main__":
    import sys
    main()
    if len(sys.argv) > 2 and sys.argv[1] == "--pages":
        pages(Path(sys.argv[2]))
    if len(sys.argv) > 2 and sys.argv[1] == "--artifact":
        artifact(Path(sys.argv[2]))
