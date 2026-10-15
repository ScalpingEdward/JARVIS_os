"""Draws room.svg, the dashboard's backdrop: a command room at night, a wall of
glass onto mountains and a valley of lights, a reflecting floor.

Generated rather than hand-written because stars, city lights and ridges are
random-but-repeatable (fixed seed). Run after changing it:

    python frontend/make_room.py
"""
import math
import random
from pathlib import Path

W, H = 1920, 1080
HORIZON = 640            # where the valley lies
FLOOR = 760              # where the glass wall meets the floor
rnd = random.Random(26)


def ridge(base, amp, rough, step=12):
    """A mountain line: a few slow waves plus noise, closed down to the floor."""
    phases = [rnd.uniform(0, 6.28) for _ in range(4)]
    pts = []
    for x in range(-20, W + 40, step):
        y = base
        for i, ph in enumerate(phases):
            y -= amp / (i + 1) * (0.5 + 0.5 * math.sin(x / (420 / (i + 1)) + ph))
        y += rnd.uniform(-rough, rough)
        pts.append(f"{x},{y:.0f}")
    return "M-20,{} L{} L{},{} Z".format(FLOOR, " L".join(pts), W + 40, FLOOR)


stars = "".join(
    f'<circle cx="{rnd.uniform(0, W):.0f}" cy="{rnd.uniform(0, HORIZON - 160) ** 1.05:.0f}" r="{rnd.choice([.6, .8, 1, 1.3, 1.7])}" '
    f'opacity="{rnd.uniform(.25, .95):.2f}"/>'
    for _ in range(420)
)
lights = "".join(
    f'<circle cx="{x:.0f}" cy="{HORIZON + rnd.uniform(-6, 36) + abs(x - W / 2) * .02:.0f}" r="{rnd.choice([.8, 1, 1.4, 1.8])}" '
    f'fill="{rnd.choice(["#ffcf7a", "#ffb04d", "#fff2d0", "#9fd8ff"])}" opacity="{rnd.uniform(.4, 1):.2f}"/>'
    for x in [rnd.gauss(W / 2, 520) for _ in range(650)] if 0 < x < W
)

# the glass wall: struts lean slightly toward the centre, as seen from inside
struts = "".join(
    f'<path d="M{x},{40} L{x + (x - W / 2) * .06:.0f},{FLOOR}" stroke="url(#strut)" stroke-width="{14 if i % 3 == 0 else 6}"/>'
    for i, x in enumerate(range(0, W + 1, 240))
)
# floor grid running toward the vanishing point under AURON
vx = W / 2
grid = "".join(
    f'<line x1="{vx}" y1="{FLOOR}" x2="{vx + (i * 260)}" y2="{H + 400}" stroke="#4fd8ff" stroke-opacity=".07"/>'
    for i in range(-12, 13)
) + "".join(
    f'<line x1="0" y1="{FLOOR + d:.0f}" x2="{W}" y2="{FLOOR + d:.0f}" stroke="#4fd8ff" stroke-opacity="{.09 - k * .006:.3f}"/>'
    for k, d in enumerate([4, 12, 24, 42, 68, 104, 152, 214, 292])
)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#03060d"/><stop offset=".55" stop-color="#0a1a33"/><stop offset=".85" stop-color="#173659"/><stop offset="1" stop-color="#2a4a6b"/>
  </linearGradient>
  <linearGradient id="far" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b5677"/><stop offset="1" stop-color="#14243b"/></linearGradient>
  <linearGradient id="mid" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22374f"/><stop offset="1" stop-color="#0a1424"/></linearGradient>
  <linearGradient id="near" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#121e2e"/><stop offset="1" stop-color="#05090f"/></linearGradient>
  <linearGradient id="strut" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b111a"/><stop offset="1" stop-color="#05080d"/></linearGradient>
  <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1626"/><stop offset="1" stop-color="#03050a"/></linearGradient>
  <linearGradient id="glare" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset=".5" stop-color="#bfe6ff" stop-opacity=".05"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
  <radialGradient id="pool" cx=".5" cy="0" r=".5"><stop offset="0" stop-color="#4fd8ff" stop-opacity=".35"/><stop offset="1" stop-color="#4fd8ff" stop-opacity="0"/></radialGradient>
  <radialGradient id="moon" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#dff3ff" stop-opacity=".9"/><stop offset=".3" stop-color="#9fd0ff" stop-opacity=".25"/><stop offset="1" stop-color="#9fd0ff" stop-opacity="0"/></radialGradient>
  <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6fa8d8" stop-opacity="0"/><stop offset="1" stop-color="#6fa8d8" stop-opacity=".22"/></linearGradient>
</defs>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
<g fill="#dff1ff">{stars}</g>
<circle cx="1490" cy="190" r="140" fill="url(#moon)"/>
<path d="{ridge(HORIZON - 60, 260, 6)}" fill="url(#far)" opacity=".85"/>
<rect y="{HORIZON - 170}" width="{W}" height="170" fill="url(#haze)"/>
<path d="{ridge(HORIZON - 10, 170, 5)}" fill="url(#mid)"/>
<g>{lights}</g>
<path d="{ridge(HORIZON + 50, 110, 4)}" fill="url(#near)"/>
<rect y="0" width="{W}" height="{FLOOR}" fill="url(#glare)"/>
<rect y="0" width="{W}" height="42" fill="#05080d"/>
<g>{struts}</g>
<rect y="{FLOOR - 6}" width="{W}" height="10" fill="#0c1522"/>
<rect y="{FLOOR}" width="{W}" height="{H - FLOOR}" fill="url(#floor)"/>
<g>{grid}</g>
<ellipse cx="{vx}" cy="{FLOOR + 160}" rx="560" ry="150" fill="url(#pool)"/>
</svg>'''

out = Path(__file__).with_name("room.svg")
out.write_text(svg, encoding="utf-8")
print(out, round(len(svg) / 1024), "KB")
