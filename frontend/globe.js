// AURON's planet: a turning crystal globe with the real continents (Natural Earth via
// world-atlas, drawn with d3-geo). The near side glows; the far side shows faintly through
// the sphere, mirrored, as it would through glass. If anything fails to load, the glass
// sphere stays without a map.
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

  let size = 0, dpr = 1;
  const projection = d3.geoOrthographic().clipAngle(90).precision(0.6);
  const path = d3.geoPath(projection, g);
  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    size = host.getBoundingClientRect().width;
    canvas.width = canvas.height = Math.round(size * dpr);
    projection.translate([size / 2, size / 2]).scale(size / 2 * 0.985);
  }
  new ResizeObserver(resize).observe(host); resize();

  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const TILT = -18;               // the axis leans, like a real globe
  let lon = 10, last = performance.now();

  function draw(now) {
    lon = (lon + (reduced ? 0 : (now - last) * 0.006)) % 360;  // one turn in a minute
    last = now;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, size, size);

    // far side first, mirrored: seen through the glass, so faint and blurred
    g.save();
    g.translate(size, 0); g.scale(-1, 1);
    projection.rotate([lon + 180, -TILT]);
    g.beginPath(); path(land);
    g.fillStyle = 'rgba(110,200,255,.10)'; g.fill();
    g.lineWidth = .6; g.strokeStyle = 'rgba(150,220,255,.18)'; g.stroke();
    g.restore();

    // near side
    projection.rotate([lon, TILT]);
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
})();
