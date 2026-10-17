// The room behind AURON, alive: one WebGL pass over the picture that moves only what
// rooms/rooms.js marks -- plants sway, water ripples and glitters, stars and city lights
// twinkle, clouds drift, light strips breathe. Everything else stays a still photo.
// Without WebGL (or with reduced motion) the picture is still there as the page
// background, placed the same way.
(() => {
  const ROOMS = window.AURON_ROOMS;
  const KINDS = { sway: 1, water: 2, clouds: 3, stars: 4, city: 5, sun: 6, glow: 7, flicker: 8, sheen: 9, fall: 10 };
  const MAX_Z = 16;
  const pick = () => { try { const k = localStorage.getItem('auron_room'); return ROOMS[k] ? k : 'lounge'; } catch { return 'lounge'; } };
  let key = pick(), room = ROOMS[key], rect = [0, 0, 1, 1];

  // ---- placement: the picture's pedestal right under the planet ----------------------------
  // Scaled so the pedestal's top is about as wide as the planet's orbits, never smaller than
  // the window, then shifted so the two line up; grown until it still covers the window.
  function place() {
    const core = document.getElementById('core').getBoundingClientRect();
    const px = core.left + core.width / 2, py = core.top + core.height * 0.88;
    const vw = innerWidth, vh = innerHeight, [x, y, top] = room.ped;
    let scale = Math.max(vw / room.w, vh / room.h, (core.width * 0.8) / (top * room.w));  // 0.8: less zoom, sharper room
    for (let i = 0; i < 40; i++) {
      const W = room.w * scale, H = room.h * scale, bx = px - x * W, by = py - y * H;
      if (bx <= 0 && by <= 0 && bx + W >= vw && by + H >= vh) {
        rect = [bx, by, W, H];
        document.body.style.backgroundImage = `url("${room.src}")`;
        document.body.style.backgroundSize = `${W}px ${H}px`;
        document.body.style.backgroundPosition = `${bx}px ${by}px`;
        return;
      }
      scale *= 1.05;
    }
  }

  // ---- WebGL ------------------------------------------------------------------------------
  const canvas = document.getElementById('room');
  const gl = canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' });
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;

  const FRAG = `
precision highp float;
uniform sampler2D img; uniform vec2 res; uniform vec4 rect; uniform vec2 texel; uniform float t; uniform float sharp;
uniform vec4 zr[${MAX_Z}]; uniform float zk[${MAX_Z}]; uniform int nz;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
float lum(vec3 c) { return dot(c, vec3(.299, .587, .114)); }
float around(vec2 uv) { vec2 o = texel * 3.;
  return .25 * (lum(texture2D(img, uv + vec2(o.x, 0)).rgb) + lum(texture2D(img, uv - vec2(o.x, 0)).rgb)
              + lum(texture2D(img, uv + vec2(0, o.y)).rgb) + lum(texture2D(img, uv - vec2(0, o.y)).rgb)); }
void main() {
  vec2 p = vec2(gl_FragCoord.x, res.y - gl_FragCoord.y);
  vec2 uv = (p - rect.xy) / rect.zw;
  vec2 d = vec2(0.);
  float wStars = 0., wCity = 0., wWater = 0., wSun = 0., wGlow = 0., wFlick = 0., wSheen = 0., wFall = 0.; vec2 sunC = vec2(0.);
  for (int i = 0; i < ${MAX_Z}; i++) {
    if (i >= nz) break;
    vec4 r = zr[i];
    if (uv.x < r.x || uv.y < r.y || uv.x > r.z || uv.y > r.w) continue;
    vec2 q = (uv - r.xy) / (r.zw - r.xy);
    float e = smoothstep(0., .12, q.x) * smoothstep(0., .12, 1. - q.x) * smoothstep(0., .12, q.y) * smoothstep(0., .12, 1. - q.y);
    float k = zk[i];
    if (k == 1.) {            // sway: the top of the plant moves, the pot does not
      float h = pow(1. - q.y, 1.6);
      d.x += e * h * (sin(t * .9 + uv.x * 9.) * .0016 + (noise(uv * 90. + t * .9) - .5) * .0011);
      d.y += e * h * (noise(uv * 70. - t * .7) - .5) * .0006;
    } else if (k == 2.) {     // water: small ripples, glitter comes after sampling
      d.y += e * (sin(uv.x * 1100. + t * 1.7 + sin(uv.y * 500. + t)) * .00045 + (noise(uv * vec2(60., 400.) + t * .5) - .5) * .0007);
      d.x += e * sin(uv.y * 900. + t * 1.1) * .0004;
      wWater = max(wWater, e);
    } else if (k == 3.) {     // clouds: a slow flow
      vec2 s = uv * 6. + vec2(t * .035, 0.);
      d += e * .0045 * vec2(noise(s) - .5, (noise(s + 17.) - .5) * .4);
    } else if (k == 4.) { wStars = max(wStars, e); }
    else if (k == 5.) { wCity = max(wCity, e); }
    else if (k == 6.) { wSun = max(wSun, e); sunC = (r.xy + r.zw) * .5; }
    else if (k == 7.) { wGlow = max(wGlow, e); }
    else if (k == 8.) { wFlick = max(wFlick, e); }
    else if (k == 9.) { wSheen = max(wSheen, e); }
    else if (k == 10.) {      // waterfall: the water's own texture pulled slowly downward
      float s = noise(vec2(uv.x * 420., uv.y * 55. - t * 1.1));
      d.y -= e * (s - .5) * .006;
      wFall = max(wFall, e);
    }
  }
  vec2 su = clamp(uv + d, texel, 1. - texel);
  vec3 c = texture2D(img, su).rgb;
  vec2 o = texel * 1.4;
  vec3 blur = .25 * (texture2D(img, su + vec2(o.x, 0)).rgb + texture2D(img, su - vec2(o.x, 0)).rgb
                   + texture2D(img, su + vec2(0, o.y)).rgb + texture2D(img, su - vec2(0, o.y)).rgb);
  c = clamp(c + (c - blur) * sharp, 0., 1.);
  float l = lum(c);
  if (wStars > 0. || wCity > 0.) {
    float pop = clamp((l - around(su)) * 4., 0., 1.);
    vec2 cell = floor(su / texel / 3.); float h = hash(cell);
    if (wStars > 0.) c += c * pop * wStars * 1.6 * (sin(t * (1.2 + 3. * h) + 6.283 * h) - .3);
    if (wCity > 0.) c *= 1. + pop * smoothstep(.2, .6, l) * wCity * .45 * sin(t * (.6 + 2. * h) + 6.283 * h);
  }
  if (wWater > 0.) {
    float g = pow(noise(su * vec2(700., 2200.) + vec2(t * .25, t * 1.4)), 6.) * 4.;
    c += c * smoothstep(.25, .75, l) * g * wWater;
  }
  if (wSun > 0.) c += vec3(1., .72, .42) * wSun * (.06 + .04 * sin(t * .6)) * exp(-length((uv - sunC) * vec2(1., .6)) * 22.);
  if (wGlow > 0.) c *= 1. + wGlow * smoothstep(.5, .95, l) * .09 * sin(t * .8 + uv.y * 4. + uv.x * 2.);
  if (wFlick > 0.) c *= 1. + wFlick * smoothstep(.35, .9, l) * (noise(vec2(t * 2.5, uv.x * 5. + uv.y * 3.)) - .5) * .16;
  if (wFall > 0.) {           // streaks of foam running down
    float f = noise(vec2(su.x * 650., su.y * 90. - t * 1.6)) * noise(vec2(su.x * 260., su.y * 40. - t * .9));
    c += wFall * smoothstep(.45, .85, l) * (f - .25) * .45;
  }
  if (wSheen > 0.) {
    float band = exp(-pow((uv.x * .7 + uv.y * .5 - fract(t * .02) * 2.4 + .5) * 7., 2.));
    c += c * wSheen * band * .3 * smoothstep(.06, .45, l);
  }
  gl_FragColor = vec4(c, 1.);
}`;
  const VERT = 'attribute vec2 a; void main() { gl_Position = vec4(a, 0., 1.); }';

  let prog, u = {}, tex, img = null, raf = 0, last = 0, dpr = 1, texW = 1;
  function setup() {
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
    prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const a = gl.getAttribLocation(prog, 'a'); gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    for (const n of ['img', 'res', 'rect', 'texel', 't', 'zr', 'zk', 'nz', 'sharp']) u[n] = gl.getUniformLocation(prog, n);
    tex = gl.createTexture();
  }

  function upload(image) {
    let src = image;
    const max = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    if (image.width > max) {  // an old GPU: shrink to what it can hold
      const c = document.createElement('canvas'), s = max / image.width;
      c.width = max; c.height = Math.floor(image.height * s);
      c.getContext('2d').drawImage(image, 0, 0, c.width, c.height); src = c;
    }
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, src);
    for (const [p, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR],
      [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, p, v);
    gl.uniform1i(u.img, 0);
    gl.uniform2f(u.texel, 1 / src.width, 1 / src.height);
    texW = src.width;
    const zr = new Float32Array(MAX_Z * 4), zk = new Float32Array(MAX_Z);
    room.zones.slice(0, MAX_Z).forEach(([k, x0, y0, x1, y1], i) => { zr.set([x0, y0, x1, y1], i * 4); zk[i] = KINDS[k] || 0; });
    gl.uniform4fv(u.zr, zr); gl.uniform1fv(u.zk, zk); gl.uniform1i(u.nz, Math.min(room.zones.length, MAX_Z));
  }

  function size() {
    dpr = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(innerWidth * dpr); canvas.height = Math.round(innerHeight * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
  }

  function frame(now) {
    raf = 0;
    if (!img) return;
    if (!still && document.hidden) return;
    if (now - last >= 33 || still) {  // ~30 fps is plenty for a breathing room, and spares the laptop
      last = now;
      gl.uniform2f(u.res, canvas.width, canvas.height);
      gl.uniform4f(u.rect, rect[0] * dpr, rect[1] * dpr, rect[2] * dpr, rect[3] * dpr);
      gl.uniform1f(u.t, now / 1000);
      gl.uniform1f(u.sharp, Math.min(1.1, Math.max(.35, (rect[2] * dpr / texW - .5) * 1.2)));
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      canvas.classList.add('on');
    }
    if (!still) raf = requestAnimationFrame(frame);
  }
  const kick = () => { if (!raf) raf = requestAnimationFrame(frame); };

  function setRoom(k) {
    if (!ROOMS[k]) return;
    key = k; room = ROOMS[k];
    try { localStorage.setItem('auron_room', k); } catch { /* private window */ }
    place();
    if (!gl || !prog) return;
    canvas.classList.remove('on');  // the plain picture shows until the new one is on the GPU
    const im = new Image();
    im.onload = () => { if (key !== k) return; img = im; upload(im); last = 0; kick(); };  // a later pick won
    im.src = room.src;
    document.dispatchEvent(new CustomEvent('auron:room', { detail: k }));
  }

  const relayout = () => { place(); if (gl && prog) { size(); last = 0; kick(); } };
  addEventListener('resize', relayout);
  new ResizeObserver(relayout).observe(document.getElementById('core'));
  document.addEventListener('visibilitychange', kick);
  try { if (gl) { setup(); size(); } } catch (e) { console.warn('room: no WebGL, still picture', e); prog = null; }
  window.AURON_room = { set: setRoom, get: () => key, list: () => Object.entries(ROOMS).map(([k, r]) => ({ key: k, name: r.name, src: r.src })) };
  setRoom(key);

  // ---- the room picker in the header -------------------------------------------------------
  const btn = document.getElementById('roomBtn'), menu = document.getElementById('roomMenu');
  if (!btn || !menu) return;  // the picker lives in Settings > Design now
  const paint = () => {
    menu.innerHTML = window.AURON_room.list().map((r) => `<button type="button" data-k="${r.key}" class="${r.key === key ? 'on' : ''}">
      <i style="background-image:url('${r.src}')"></i><span>${r.name}</span></button>`).join('');
  };
  btn.addEventListener('click', (e) => { e.stopPropagation(); paint(); menu.hidden = !menu.hidden; });
  menu.addEventListener('click', (e) => { const b = e.target.closest('button[data-k]'); if (b) { setRoom(b.dataset.k); paint(); } });
  document.addEventListener('click', (e) => { if (!menu.hidden && !e.composedPath().includes(menu) && e.target !== btn) menu.hidden = true; });
})();
