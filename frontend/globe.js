// AURON's planet: a turning crystal globe with the real continents (Natural Earth via
// world-atlas, drawn with d3-geo). The near side glows; the far side shows faintly through
// the sphere, mirrored, as it would through glass. If anything fails to load, the glass
// sphere stays without a map.
// On the wallpaper (?desk) the planet is his to play with: drag turns it (and lets it spin on),
// the mouse wheel zooms it with its rings, a double-click puts it back.
(async function globe() {
  const host = document.querySelector('.sphere');
  if (!host || !window.d3 || !window.topojson) return;
  const canvas = document.createElement('canvas');
  canvas.className = 'globe-map';
  host.appendChild(canvas);
  const g = canvas.getContext('2d');

  let land, graticule;
  try {
    const topo = await (await fetch('https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-110m.json')).json();
    land = topojson.feature(topo, topo.objects.land);
    graticule = d3.geoGraticule10();
  } catch (e) { console.warn('globe map unavailable:', e); return; }

  let size = 0, dpr = 1, zoom = 1, drawn = '';
  const projection = d3.geoOrthographic().clipAngle(90).precision(0.6);
  const path = d3.geoPath(projection, g);
  function resize() {
    // the layout size (a zoom is a CSS scale on top), drawn finer the more it is zoomed in
    dpr = Math.min(devicePixelRatio || 1, matchMedia('(pointer: coarse)').matches ? 1.5 : 2) * Math.max(1, zoom);
    size = host.offsetWidth || host.getBoundingClientRect().width;
    canvas.width = canvas.height = Math.round(size * dpr);
    projection.translate([size / 2, size / 2]).scale(size / 2 * 0.985);
    drawn = '';  // a new canvas size clears it
  }
  new ResizeObserver(resize).observe(host); resize();

  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const BASE_TILT = -18;            // the axis leans, like a real globe
  const SPIN = reduced ? 0 : 0.006; // degrees per ms: one turn in a minute
  let lon = 10, tilt = BASE_TILT, speed = SPIN, last = performance.now(), dragging = false;

  function draw(now) {
    const dt = now - last;
    last = now;
    if (!dragging) {
      lon = (lon + speed * dt) % 360;
      speed += (SPIN - speed) * Math.min(1, dt / 1500);        // a flick slows back to the steady turn
      tilt += (BASE_TILT - tilt) * Math.min(1, dt / 4000);     // and the axis leans back
    }
    // a globe standing still (reduced motion -- always on the LG TV) is not drawn again: projecting the
    // whole map each frame took most of the TV's chip (measured 2026-10-29)
    const now2 = `${lon.toFixed(3)}|${tilt.toFixed(3)}|${size}|${dpr}`;
    if (now2 === drawn) { requestAnimationFrame(draw); return; }
    drawn = now2;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, size, size);

    // far side first, mirrored: seen through the glass, so faint and blurred
    g.save();
    g.translate(size, 0); g.scale(-1, 1);
    projection.rotate([lon + 180, -tilt]);
    g.beginPath(); path(land);
    g.fillStyle = 'rgba(110,200,255,.10)'; g.fill();
    g.lineWidth = .6; g.strokeStyle = 'rgba(150,220,255,.18)'; g.stroke();
    g.restore();

    // near side
    projection.rotate([lon, tilt]);
    g.beginPath(); path(graticule);
    g.lineWidth = .5; g.strokeStyle = 'rgba(140,220,255,.16)'; g.stroke();
    g.beginPath(); path(land);
    const fill = g.createRadialGradient(size * .36, size * .32, size * .05, size / 2, size / 2, size / 2);
    fill.addColorStop(0, 'rgba(210,245,255,.60)'); fill.addColorStop(.6, 'rgba(90,200,255,.38)'); fill.addColorStop(1, 'rgba(40,120,220,.22)');
    g.fillStyle = fill; g.fill();
    g.shadowColor = 'rgba(79,216,255,.9)'; g.shadowBlur = 8;
    g.lineWidth = 1; g.strokeStyle = 'rgba(190,240,255,.85)'; g.stroke();
    g.shadowBlur = 0;

    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);

  // ---- the wallpaper: turn, spin, zoom ------------------------------------------------------
  if (!document.documentElement.classList.contains('desk')) return;
  const core = document.getElementById('core');
  let px = 0, py = 0, pt = 0, v = 0;
  core.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    dragging = true; px = e.clientX; py = e.clientY; pt = performance.now(); v = 0;
    core.setPointerCapture(e.pointerId); core.classList.add('turning');
    e.preventDefault();
  });
  core.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const now = performance.now(), dx = e.clientX - px, dy = e.clientY - py;
    const k = 180 / (size * zoom || 300);                      // a drag across the planet turns it half way
    lon = (lon + dx * k) % 360;
    tilt = Math.max(-75, Math.min(75, tilt - dy * k));
    v = (dx * k) / Math.max(1, now - pt);                      // degrees per ms, for the spin after letting go
    px = e.clientX; py = e.clientY; pt = now;
  });
  const release = () => {
    if (!dragging) return;
    dragging = false; core.classList.remove('turning');
    speed = Math.max(-0.6, Math.min(0.6, performance.now() - pt < 80 ? v : SPIN));
    last = performance.now();
  };
  core.addEventListener('pointerup', release);
  core.addEventListener('pointercancel', release);
  const setZoom = (z) => {
    zoom = Math.max(0.6, Math.min(1.8, z));
    document.documentElement.style.setProperty('--planet-zoom', zoom.toFixed(3));
    resize();
  };
  addEventListener('wheel', (e) => {
    if (e.target.closest?.('.tile, .card-menu, .detail')) return;   // the cards and views scroll as usual
    e.preventDefault();
    setZoom(zoom * Math.exp(-e.deltaY * 0.0012));
  }, { passive: false });
  core.addEventListener('dblclick', () => { setZoom(1); tilt = BASE_TILT; speed = SPIN; });
})();
