// AURON's 3D parts (backend/app/cad): the part he designed, between the card columns like the chart --
// drag turns it, the wheel zooms, it turns slowly on its own. "Bauplan" draws it as glowing edges in the
// accent colour (a CAD blueprint), "Massiv" as a solid part. STL saves the file for the printer's slicer.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const LIBS = ['https://unpkg.com/three@0.147.0/build/three.min.js',
    'https://unpkg.com/three@0.147.0/examples/js/loaders/STLLoader.js',
    'https://unpkg.com/three@0.147.0/examples/js/controls/OrbitControls.js'];
  const box = document.createElement('section');
  box.className = 'pos-chart model-view'; box.hidden = true;
  box.innerHTML = `<header class="pc-head"><b class="pc-title mv-title"></b><span class="pc-sum mono mv-size"></span>
      <span class="pc-tf mv-mode"><button type="button" data-mode="plan" class="on">Bauplan</button><button type="button" data-mode="solid">Massiv</button></span>
      <span class="pc-btns"><a class="mv-stl" download>STL</a>
      <button type="button" class="pc-full mv-full" title="Vollbild (an/aus)">⤢</button>
      <button type="button" class="pc-x mv-x" aria-label="Schließen">✕</button></span></header>
    <div class="pc-body mv-body"></div><p class="pc-wait muted mv-wait">Lade das Teil …</p>`;
  document.body.append(box);
  const body = box.querySelector('.mv-body'), wait = box.querySelector('.mv-wait');
  let ready = null, three = null, mode = 'plan', full = false, raf = 0;

  const load = (src) => new Promise((ok, bad) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => bad(new Error('3D-Bibliothek lädt nicht')); document.head.append(s); });
  const lib = () => ready || (ready = (async () => { if (!window.THREE) await load(LIBS[0]); await load(LIBS[1]); await load(LIBS[2]); })());

  function place() {
    const l = document.getElementById('colLeft')?.getBoundingClientRect(), r = document.getElementById('colRight')?.getBoundingClientRect();
    if (full || !l || !r || innerWidth <= 1000 || r.left - l.right < 480) {
      Object.assign(box.style, full ? { left: '12px', right: '12px', top: '12px', bottom: '12px' } : { left: '12px', right: '12px', top: '70px', bottom: '110px' });
    } else {
      Object.assign(box.style, { left: `${Math.round(l.right + 14)}px`, right: `${Math.round(innerWidth - r.left + 14)}px`,
        top: `${Math.round(Math.min(l.top, r.top))}px`, bottom: `${Math.round(innerHeight - Math.max(l.bottom, r.bottom))}px` });
    }
    if (three) { const w = body.clientWidth, h = body.clientHeight; three.renderer.setSize(w, h); three.camera.aspect = w / Math.max(h, 1); three.camera.updateProjectionMatrix(); }
  }

  function scene() {
    const T = window.THREE, renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    body.append(renderer.domElement);
    const sc = new T.Scene(), camera = new T.PerspectiveCamera(40, 1, 0.1, 10000);
    sc.add(new T.AmbientLight(0xffffff, 0.55));
    const key = new T.DirectionalLight(0xffffff, 0.9); key.position.set(1, 1.5, 2); sc.add(key);
    const rim = new T.DirectionalLight(0x88ccff, 0.5); rim.position.set(-2, -1, -1); sc.add(rim);
    const controls = new T.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 1.2;
    controls.addEventListener('start', () => { controls.autoRotate = false; });
    return { T, renderer, sc, camera, controls, group: null };
  }

  function show(geo) {
    const { T, sc, camera, controls } = three;
    if (three.group) sc.remove(three.group);
    geo.computeVertexNormals(); geo.center();
    const g = new T.Group();
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4fd8ff';
    if (mode === 'plan') {
      g.add(new T.Mesh(geo, new T.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.07, depthWrite: false })));
      g.add(new T.LineSegments(new T.EdgesGeometry(geo, 18), new T.LineBasicMaterial({ color: accent })));
    } else {
      g.add(new T.Mesh(geo, new T.MeshStandardMaterial({ color: 0xc9d3e0, metalness: 0.35, roughness: 0.45 })));
    }
    g.rotation.x = -Math.PI / 2;                       // CAD's z is up; three's y is up
    sc.add(g); three.group = g;
    geo.computeBoundingSphere();
    const r = geo.boundingSphere.radius || 10;
    camera.position.set(r * 1.6, r * 1.1, r * 2.0); camera.near = r / 100; camera.far = r * 100; camera.updateProjectionMatrix();
    controls.target.set(0, 0, 0); controls.update();
  }

  let geometry = null;
  async function open(id) {
    box.hidden = false; wait.hidden = false; wait.textContent = 'Lade das Teil …'; place();
    try {
      await lib();
      const meta = await (await fetch(`${API_BASE}/v1/cad/${id}`)).json();
      if (!meta.id) throw new Error(meta.detail || 'Teil nicht gefunden');
      box.querySelector('.mv-title').textContent = `${meta.name} · v${meta.version}`;
      box.querySelector('.mv-size').textContent = `${meta.size_mm.map((v) => v.toLocaleString('de-DE')).join(' × ')} mm`;
      box.querySelector('.mv-stl').href = `${API_BASE}/v1/cad/${id}/part.stl`;
      const buf = await (await fetch(`${API_BASE}/v1/cad/${id}/part.stl`)).arrayBuffer();
      if (!three) three = scene();
      place();
      geometry = new window.THREE.STLLoader().parse(buf);
      show(geometry);
      wait.hidden = true;
      cancelAnimationFrame(raf);
      const tick = () => { if (box.hidden) return; three.controls.update(); three.renderer.render(three.sc, three.camera); raf = requestAnimationFrame(tick); };
      tick();
    } catch (e) { wait.textContent = `Geht nicht: ${e.message}`; }
  }
  function close() { box.hidden = true; cancelAnimationFrame(raf); }

  box.querySelector('.mv-mode').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-mode]');
    if (!b || b.dataset.mode === mode) return;
    mode = b.dataset.mode;
    box.querySelectorAll('.mv-mode button').forEach((x) => x.classList.toggle('on', x === b));
    if (geometry) show(geometry);
  });
  box.querySelector('.mv-full').addEventListener('click', () => { full = !full; place(); });
  box.querySelector('.mv-x').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.hidden) close(); });
  addEventListener('resize', () => { if (!box.hidden) place(); });
  window.AURON_model = { open, close };
})();
