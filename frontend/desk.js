// Desktop mode (?desk) -- the dashboard as Brano's Windows wallpaper, shown by Lively Wallpaper on
// his main screen (docs/windows-theme.md). Clock and weather at the top, the planet large under
// them on its pedestal, every card along the bottom. A card is dragged by holding and moving it;
// a plain click still opens its view. Positions are kept in this browser, anchored to the bottom
// edge so a card that grows grows upward, not off the screen.
(() => {
  if (!document.documentElement.classList.contains('desk')) return;
  const KEY = 'auron_desk_pos', GAP = 18, PAD = 28, BOTTOM = 62;   // 62: above the Windows taskbar
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; } };
  let pos = load();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(pos)); } catch { /* private window */ } };
  const cards = () => [...document.querySelectorAll('#colLeft > .tile, #colRight > .tile')];

  // the wallpaper never talks: the dashboard window beside it already does
  if (window.AURON_voice) window.AURON_voice.say = () => {};

  function arrange() {
    const all = cards(), n = all.length || 1;
    const w = Math.min(380, (innerWidth - 2 * PAD - (n - 1) * GAP) / n);
    const row = n * w + (n - 1) * GAP, x0 = (innerWidth - row) / 2;
    document.documentElement.style.setProperty('--desk-w', `${w}px`);
    all.forEach((card, i) => {
      const id = card.id, p = pos[id];
      const left = p ? p.x * innerWidth : x0 + i * (w + GAP);
      const bottom = p ? p.b * innerHeight : BOTTOM;
      card.style.left = `${Math.max(0, Math.min(innerWidth - w, left))}px`;
      card.style.bottom = `${Math.max(0, Math.min(innerHeight - 60, bottom))}px`;
    });
  }

  // drag: more than 6 px of movement makes it a drag, and the click that ends it opens nothing
  let drag = null;
  document.addEventListener('pointerdown', (e) => {
    const card = e.target.closest('#colLeft > .tile, #colRight > .tile');
    if (!card || e.button !== 0 || e.target.closest('.card-gear, .card-menu, input, select, a')) return;
    const r = card.getBoundingClientRect();
    drag = { card, sx: e.clientX, sy: e.clientY, left: parseFloat(card.style.left) || r.left,
      bottom: parseFloat(card.style.bottom) || innerHeight - r.bottom, moved: false };
  });
  document.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true; drag.card.classList.add('dragging');
    drag.card.style.left = `${Math.max(0, Math.min(innerWidth - drag.card.offsetWidth, drag.left + dx))}px`;
    drag.card.style.bottom = `${Math.max(0, Math.min(innerHeight - 60, drag.bottom - dy))}px`;
  });
  document.addEventListener('pointerup', () => {
    if (!drag) return;
    const { card, moved } = drag; drag = null;
    card.classList.remove('dragging');
    if (!moved) return;
    pos[card.id] = { x: parseFloat(card.style.left) / innerWidth, b: parseFloat(card.style.bottom) / innerHeight };
    save();
    const swallow = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
    card.addEventListener('click', swallow, { capture: true, once: true });
    setTimeout(() => card.removeEventListener('click', swallow, { capture: true }), 300);
  });

  // "Karten zurück in die Reihe": double-click on the empty desktop
  document.addEventListener('dblclick', (e) => {
    if (e.target.closest('.tile, .core, .detail, .card-menu')) return;
    pos = {}; save(); arrange();
  });

  // layout.js re-places cards (AURON can add or remove some): new ones get a slot in the row
  for (const col of ['colLeft', 'colRight']) new MutationObserver(arrange).observe(document.getElementById(col), { childList: true });
  addEventListener('resize', arrange);
  arrange();
})();
