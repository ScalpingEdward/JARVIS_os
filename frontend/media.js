// A window in the middle, where the chart opens -- between the card columns, with full screen -- for
// what is watched or listened to on the side (Brano, 2026-10-29: "Web, Spotify, YouTube ... so in
// einem Fenster in der Mitte wie Charts"). YouTube first: a link or a video id plays here; the last
// ones stay as a list, so on the TV nothing needs typing twice. Spotify and web pages come as tabs of
// their own once they work -- no empty tabs before that.
(() => {
  const KEPT = 'auron_media_recent';
  const box = document.createElement('section');
  box.className = 'pos-chart media-box'; box.hidden = true;
  box.innerHTML = `<header class="pc-head"><b class="pc-title">YouTube</b>
      <form class="md-yt"><input class="md-url" type="text" placeholder="YouTube-Link oder Video-ID" spellcheck="false" />
        <button type="submit">Abspielen</button></form>
      <span class="pc-btns"><button type="button" class="pc-full" title="Vollbild (an/aus)" aria-label="Vollbild">⤢</button>
      <button type="button" class="pc-x" aria-label="Fenster schließen">✕</button></span></header>
    <div class="md-body"><iframe class="md-frame" hidden allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>
      <div class="md-recent"></div></div>`;
  document.body.append(box);
  const frame = box.querySelector('.md-frame'), url = box.querySelector('.md-url'), recentEl = box.querySelector('.md-recent');

  // the same place as the chart: between the columns, or the whole screen
  let full = false;
  function place() {
    const l = document.getElementById('colLeft')?.getBoundingClientRect(), r = document.getElementById('colRight')?.getBoundingClientRect();
    box.classList.toggle('full', full);
    if (full || !l || !r || innerWidth <= 1000 || r.left - l.right < 480) {
      Object.assign(box.style, full ? { left: '12px', right: '12px', top: '12px', bottom: '12px' } : { left: '12px', right: '12px', top: '70px', bottom: '110px' });
      return;
    }
    Object.assign(box.style, { left: `${Math.round(l.right + 14)}px`, right: `${Math.round(innerWidth - r.left + 14)}px`,
      top: `${Math.round(Math.min(l.top, r.top))}px`, bottom: `${Math.round(innerHeight - Math.max(l.bottom, r.bottom))}px` });
  }
  const setFull = (on) => { full = on ?? !full; place(); };

  // what a link or id means: a video, a short, or a playlist
  function parse(text) {
    const s = (text || '').trim();
    if (/^[\w-]{11}$/.test(s)) return { video: s };
    let u;
    try { u = new URL(/^https?:/i.test(s) ? s : `https://${s}`); } catch { return null; }
    if (!/(^|\.)(youtube\.com|youtube-nocookie\.com|youtu\.be)$/i.test(u.hostname)) return null;
    const list = u.searchParams.get('list');
    const id = u.hostname.endsWith('youtu.be') ? u.pathname.slice(1)
      : u.searchParams.get('v') || (u.pathname.match(/^\/(?:shorts|embed|live)\/([\w-]{11})/) || [])[1];
    if (id && /^[\w-]{11}$/.test(id)) return { video: id, list };
    return list ? { list } : null;
  }
  const src = (m) => (m.video
    ? `https://www.youtube-nocookie.com/embed/${m.video}?autoplay=1&rel=0${m.list ? `&list=${encodeURIComponent(m.list)}` : ''}`
    : `https://www.youtube-nocookie.com/embed/videoseries?autoplay=1&list=${encodeURIComponent(m.list)}`);

  const kept = () => { try { return JSON.parse(localStorage.getItem(KEPT) || '[]'); } catch { return []; } };
  function keep(m, text) {
    const list = [{ ...m, text }, ...kept().filter((x) => x.video !== m.video || x.list !== m.list)].slice(0, 8);
    try { localStorage.setItem(KEPT, JSON.stringify(list)); } catch { /* private window */ }
    showRecent();
  }
  function showRecent() {
    const list = kept();
    recentEl.innerHTML = list.length
      ? `<small class="muted">Zuletzt</small>${list.map((m, i) => `<button type="button" data-i="${i}">${m.video
        ? `<img src="https://i.ytimg.com/vi/${esc(m.video)}/mqdefault.jpg" alt="" loading="lazy" />` : '<span class="md-pl">☰</span>'}<span>${esc(m.text)}</span></button>`).join('')}`
      : '<p class="muted">Einen YouTube-Link oder eine Video-ID oben einfügen und „Abspielen“.</p>';
  }

  function play(m, text) {
    // on the LG TV the embedded player cannot run (its browser is too old for YouTube): the TV's own
    // YouTube app plays it instead (tools/tv_gate/shim.js)
    if (window.AURON_tv?.youtube?.(m)) { keep(m, text); return; }
    frame.src = src(m); frame.hidden = false;
    recentEl.hidden = true;
    keep(m, text);
  }
  box.querySelector('.md-yt').addEventListener('submit', (e) => {
    e.preventDefault();
    const m = parse(url.value);
    if (!m) { url.select(); url.placeholder = 'Kein YouTube-Link -- bitte nochmal'; url.value = ''; return; }
    play(m, url.value.trim());
    url.value = '';
  });
  recentEl.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-i]');
    if (!b) return;
    const m = kept()[+b.dataset.i];
    if (m) play(m, m.text);
  });

  function open() {
    window.AURON_chart?.close();
    place(); box.hidden = false;
    if (frame.hidden) { recentEl.hidden = false; showRecent(); }
  }
  function close() {
    if (box.hidden) return;
    box.hidden = true; full = false;
    frame.src = 'about:blank'; frame.hidden = true;   // stops the sound
  }
  box.querySelector('.pc-full').addEventListener('click', () => setFull());
  box.querySelector('.pc-x').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.hidden) close(); });
  document.addEventListener('auron:chartopen', close);   // one window in the middle at a time
  addEventListener('resize', () => { if (!box.hidden) place(); });

  document.getElementById('ytBtn')?.addEventListener('click', () => (box.hidden ? open() : close()));
  window.AURON_media = { open, close, full: setFull, play: (text) => { const m = parse(text); if (m) { open(); play(m, text); } return !!m; } };
})();
