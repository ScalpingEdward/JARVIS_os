"""The AURON Windows theme for Brano's three 1920x1080 screens -- built from the dashboard itself.

    python tools/windows_theme.py   ->  windows-theme/AURON.deskthemepack (+ the pictures alone)

Renders three pictures with Edge headless from the running frontend (:8080):
  main   (DISPLAY2, bottom left)  the lounge with the planet -- what shows while Lively is off
  right  (DISPLAY1, bottom right) "Über der Erde", room only
  top    (DISPLAY3, above, x 888) "Orbit", room only
and puts them into ONE spanned picture laid out like the screens (Windows' "Span" maps the whole
desktop onto one image -- a .theme file cannot set a picture per screen). The .theme also sets
dark mode and AURON's cyan as accent. Brano installs it himself by double-clicking the pack; the
live dashboard on the main screen comes from Lively Wallpaper (docs/windows-theme.md).
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "windows-theme"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://127.0.0.1:8080/"
W, H = 1920, 1080
# where each screen sits in the virtual desktop (Settings > Display), relative to the top-left corner
# of all three together: the top screen starts 888 px right of the main screen's left edge
SHOTS = {
    "main": ("?desk&bare&room=lounge", (0, H)),
    "right": ("?desk&bare&noplanet&room=earth", (W, H)),
    "top": ("?desk&bare&noplanet&room=orbit", (888, 0)),
}
ACCENT = "0XC44FD8FF"   # --accent #4fd8ff


def shoot(query: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([EDGE, "--headless=new", f"--user-data-dir={prof}", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={W},{H}", "--virtual-time-budget=20000", "--enable-unsafe-swiftshader",
                        f"--screenshot={out}", BASE + query], check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    im = Image.open(out)
    if im.size != (W, H):
        raise SystemExit(f"{out.name}: {im.size}, expected {W}x{H}")


THEME = """; AURON -- Phoenix Life Solutions. Built by tools/windows_theme.py.
[Theme]
DisplayName=AURON

[Control Panel\\Desktop]
Wallpaper=%ThemeDir%DesktopBackground\\auron-span.jpg
WallpaperStyle=22
TileWallpaper=0
Pattern=

[VisualStyles]
Path=%SystemRoot%\\resources\\Themes\\Aero\\Aero.msstyles
ColorStyle=NormalColor
Size=NormalSize
AutoColorization=0
ColorizationColor={accent}
SystemMode=Dark
AppMode=Dark
VisualStyleVersion=10

[MasterThemeSelector]
MTSM=RJSPBS

[Sounds]
SchemeName=

[boot]
SCRNSAVE.EXE=
"""


def main() -> None:
    build = OUT / "build"
    shutil.rmtree(build, ignore_errors=True)
    (build / "DesktopBackground").mkdir(parents=True)
    pics = {}
    for name, (query, _) in SHOTS.items():
        png = build / f"{name}.png"
        shoot(query, png)
        pics[name] = Image.open(png).convert("RGB")
        pics[name].save(OUT / f"auron-{name}.jpg", quality=92)
        print("rendered", name)
    span = Image.new("RGB", (W * 2, H * 2), (3, 5, 10))
    for name, (_, at) in SHOTS.items():
        span.paste(pics[name], at)
    span.save(build / "DesktopBackground" / "auron-span.jpg", quality=92)
    (build / "AURON.theme").write_text(THEME.format(accent=ACCENT), encoding="utf-8")
    # a .deskthemepack is a cabinet; makecab keeps the folder through the directive file
    ddf = build / "pack.ddf"
    ddf.write_text("\n".join([
        ".Set CabinetNameTemplate=AURON.deskthemepack", f".Set DiskDirectoryTemplate={OUT}",
        ".Set Cabinet=on", ".Set Compress=on", ".Set MaxDiskSize=0", ".Set RptFileName=nul", ".Set InfFileName=nul",
        f'"{build / "AURON.theme"}" "AURON.theme"',
        f'"{build / "DesktopBackground" / "auron-span.jpg"}" "DesktopBackground\\auron-span.jpg"',
    ]) + "\n", encoding="utf-8")
    subprocess.run(["makecab", "/F", str(ddf)], check=True, cwd=build, stdout=subprocess.DEVNULL)
    print(OUT / "AURON.deskthemepack", f"{(OUT / 'AURON.deskthemepack').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
