// The hero works like the dashboard: each room is scaled and shifted so its pedestal stands
// right under AURON's planet (pedestal data from ../rooms/rooms.js). A "look" is a room together
// with the dashboard settings that suit it -- accent, glass colour, glass style, planet colour --
// so ‹ › shows at once what the settings menu can do. It tours by itself until someone clicks.
(() => {
  const ROOMS = window.AURON_ROOMS || {};
  const LOOKS = [
    { room: 'earth', name: 'Über der Erde', style: 'Klares Glas', glass: 'frosted', accent: '#4fd8ff', tint: '150 200 255', planet: '#4fd8ff' },
    { room: 'forest', name: 'Am Wasserfall', style: 'Verblasst · Grün', glass: 'faded', accent: '#3ddc97', tint: '170 255 215', planet: '#3ddc97' },
    { room: 'noir', name: 'Noir', style: 'Schwarze Karten · Gold', glass: 'dark', accent: '#f5b84a', tint: '14 14 16', planet: '#f5b84a' },
    { room: 'alps', name: 'In den Alpen', style: 'Matt · Abendrot', glass: 'matte', accent: '#ff9a62', tint: '255 205 175', planet: '#ff7eb6' },
    { room: 'gold', name: 'Im eigenen Turm', style: 'Massiv · Champagner', glass: 'solid', accent: '#f2d58a', tint: '255 232 180', planet: '#f5b84a' },
    { room: 'lounge', name: 'Über der Stadt', style: 'Klares Glas · Violett', glass: 'frosted', accent: '#b88cff', tint: '205 185 255', planet: '#b88cff' },
  ].filter((l) => ROOMS[l.room]);
  const a = document.getElementById('bgA'), b = document.getElementById('bgB'), where = document.getElementById('where');
  const core = document.getElementById('core'), root = document.documentElement;
  const pageBg = document.getElementById('pageBg');
  const src = (k) => `../${ROOMS[k].src}`;

  function place(layer, key) {
    const room = ROOMS[key], c = core.getBoundingClientRect(), hero = layer.parentElement.getBoundingClientRect();
    const px = c.left - hero.left + c.width / 2, py = c.top - hero.top + c.height * 0.88;
    const vw = hero.width, vh = hero.height, [x, y, top] = room.ped;
    let scale = Math.max(vw / room.w, vh / room.h, (c.width * 0.8) / (top * room.w));
    for (let i = 0; i < 40; i++) {
      const W = room.w * scale, H = room.h * scale, bx = px - x * W, by = py - y * H;
      if (bx <= 0 && by <= 0 && bx + W >= vw && by + H >= vh) {
        layer.style.backgroundImage = `url("${src(key)}")`;
        layer.style.backgroundSize = `${W}px ${H}px`;
        layer.style.backgroundPosition = `${bx}px ${by}px`;
        layer.dataset.room = key;
        return;
      }
      scale *= 1.05;
    }
  }
  // the planet is drawn cyan; another colour is a hue turn (as in ../settings.js)
  function planetFilter(hex) {
    const [r, g, bl] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const max = Math.max(r, g, bl), min = Math.min(r, g, bl), d = max - min;
    if (!d) return 'grayscale(1) brightness(1.15)';
    const h = max === r ? ((g - bl) / d) % 6 : max === g ? (bl - r) / d + 2 : (r - g) / d + 4;
    return `hue-rotate(${Math.round(((h * 60 + 360) % 360) - 192)}deg)`;
  }
  function wear(look) {
    root.style.setProperty('--accent', look.accent);
    root.style.setProperty('--tint', look.tint);
    root.style.setProperty('--planet-filter', planetFilter(look.planet));
    root.dataset.glass = look.glass;
    // the rest of the page sits in the same room, dimmed, like the cards on the dashboard
    pageBg.style.opacity = 0;
    setTimeout(() => { pageBg.style.backgroundImage = `url("${src(look.room)}")`; pageBg.style.opacity = 1; }, 450);
  }

  let n = 0, front = a, back = b, timer = null;
  place(front, LOOKS[0].room);
  wear(LOOKS[0]);
  addEventListener('resize', () => { place(front, front.dataset.room); if (back.dataset.room) place(back, back.dataset.room); });
  LOOKS.forEach((l) => { const i = new Image(); i.src = src(l.room); });

  function show(i) {
    n = (i + LOOKS.length) % LOOKS.length;
    const look = LOOKS[n];
    place(back, look.room);
    back.classList.remove('next'); front.classList.add('next');
    [front, back] = [back, front];
    wear(look);
    where.style.opacity = 0;
    setTimeout(() => { where.innerHTML = `<b>${look.name}</b> · ${look.style}`; where.style.opacity = 1; }, 400);
  }
  // a click takes over: the tour stops, so the chosen look stays
  document.getElementById('prevLook').addEventListener('click', () => { clearInterval(timer); show(n - 1); });
  document.getElementById('nextLook').addEventListener('click', () => { clearInterval(timer); show(n + 1); });
  addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') { clearInterval(timer); show(n - 1); }
    if (e.key === 'ArrowRight') { clearInterval(timer); show(n + 1); }
  });
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || LOOKS.length < 2) return;
  timer = setInterval(() => show(n + 1), 7000);
})();

// pictures with data-zoom open large; "Als Bild öffnen" shows the picture alone in a new tab
(() => {
  const box = document.getElementById('lightbox'), img = document.getElementById('lbImg');
  if (!box) return;
  const close = () => { box.hidden = true; document.body.style.overflow = ''; };
  document.querySelectorAll('img[data-zoom]').forEach((el) => el.addEventListener('click', () => {
    img.src = el.currentSrc || el.src; img.alt = el.alt;
    box.hidden = false; document.body.style.overflow = 'hidden';
  }));
  box.addEventListener('click', (e) => { if (e.target === box || e.target === img) close(); });
  document.getElementById('lbClose').addEventListener('click', close);
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.hidden) close(); });
  // a blob address also works when the picture is embedded (the one-file export); data: tabs are blocked
  document.getElementById('lbOpen').addEventListener('click', async () => {
    const blob = await (await fetch(img.src)).blob();
    window.open(URL.createObjectURL(blob), '_blank');
  });
})();

// hologram fan preview: planet only or the whole dashboard
(() => {
  const fan = document.getElementById('fan');
  if (!fan) return;
  document.querySelectorAll('.holo-modes button').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.holo-modes button').forEach((x) => x.classList.toggle('on', x === b));
    fan.dataset.mode = b.dataset.mode;
  }));
})();
