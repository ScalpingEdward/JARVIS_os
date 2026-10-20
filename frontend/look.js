// The look -- colours, glass, clock, planet, room, the cards' text -- lives in AURON's database
// (/v1/dashboard/look), so it is the same on every screen and AURON can change it on Brano's word
// ("mach die Karten golden" ... "nächste" ... "gut so"). Asked every 2 s; a change made here in the
// settings goes back the same way. The cards' text sizes count on the big screen only: a narrow
// phone keeps its own, 140 % there would run over.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const wide = () => innerWidth > 1000;
  let version = -1, ready = false, applying = false, timer = 0;

  function take(look) {
    applying = true;
    try {
      if (look.theme && Object.keys(look.theme).length) window.AURON_theme?.set(look.theme);
      if (look.room && window.AURON_room && look.room !== window.AURON_room.get()) window.AURON_room.set(look.room);
      if (look.cards && wide()) window.AURON_cards?.set(look.cards);
    } finally { applying = false; }
  }

  async function push() {
    const look = { theme: window.AURON_theme?.get(), room: window.AURON_room?.get() };
    if (wide()) look.cards = window.AURON_cards?.get();
    try {
      const r = await fetch(`${API_BASE}/v1/dashboard/look`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ look }) });
      if (r.ok) version = (await r.json()).version;
    } catch { /* AURON down: the next change tries again */ }
  }

  async function pull() {
    if (document.hidden && ready) return;
    let d;
    try { d = await (await fetch(`${API_BASE}/v1/dashboard/look`)).json(); } catch { return; }
    if (!ready) {
      ready = true;
      if (!d.version) { push(); return; }      // first time: this screen's look becomes the shared one
    }
    if (d.version !== version) { version = d.version; take(d.look || {}); }
  }

  window.AURON_look = { changed() { if (!ready || applying) return; clearTimeout(timer); timer = setTimeout(push, 600); } };
  document.addEventListener('auron:room', () => window.AURON_look.changed());
  pull();
  setInterval(pull, 2000);
})();
