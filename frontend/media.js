// A window in the middle, where the chart opens -- between the card columns, with full screen -- for
// what is watched or listened to on the side (Brano, 2026-10-29: "Web, Spotify, YouTube ... so in
// einem Fenster in der Mitte wie Charts"). Two tabs:
// - YouTube: a link or a video id plays here; the last ones stay as a list, so on the TV nothing needs
//   typing twice.
// - Spotify: what plays, with cover and progress; back, play/pause, next, volume, the device it plays on,
//   his playlists and a search. Spotify cannot be embedded, so this steers his Spotify (backend
//   /v1/spotify/...) -- the sound comes from the chosen device, not from this window.
// Web pages come as a tab of their own once they work -- no empty tab before that.
(() => {
  const KEPT = 'auron_media_recent', TAB = 'auron_media_tab';
  const ic = (d) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${d}"/></svg>`;
  const ICON = { prev: ic('M6 5h2v14H6zM20 5v14L9 12z'), next: ic('M16 5h2v14h-2zM4 5v14l11-7z'),
    play: ic('M7 4v16l13-8z'), pause: ic('M6 4h4v16H6zM14 4h4v16h-4z') };
  const box = document.createElement('section');
  box.className = 'pos-chart media-box'; box.hidden = true;
  box.innerHTML = `<header class="pc-head"><span class="md-tabs"><button type="button" data-tab="yt">YouTube</button>
        <button type="button" data-tab="sp">Spotify</button></span>
      <form class="md-yt"><input class="md-url" type="text" placeholder="YouTube-Link oder Video-ID" spellcheck="false" />
        <button type="submit">Abspielen</button></form>
      <form class="md-yt sp-search" hidden><input class="sp-q" type="text" placeholder="Song, Künstler oder Playlist" spellcheck="false" />
        <button type="submit">Spielen</button></form>
      <span class="pc-btns"><button type="button" class="pc-full" title="Vollbild (an/aus)" aria-label="Vollbild">⤢</button>
      <button type="button" class="pc-x" aria-label="Fenster schließen">✕</button></span></header>
    <div class="md-body"><iframe class="md-frame" hidden allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>
      <div class="md-recent"></div>
      <div class="md-sp" hidden>
        <div class="sp-now"><img class="sp-cover" alt="" hidden /><div class="sp-text"><b class="sp-title">–</b><span class="sp-artist"></span>
          <div class="sp-bar"><i></i></div><small class="sp-time muted"></small></div></div>
        <div class="sp-ctl"><button type="button" data-a="previous" aria-label="Zurück">${ICON.prev}</button>
          <button type="button" data-a="toggle" class="sp-pp" aria-label="Abspielen/Pause">${ICON.play}</button>
          <button type="button" data-a="next" aria-label="Weiter">${ICON.next}</button>
          <label class="sp-vol-l">Lautstärke <input class="sp-vol" type="range" min="0" max="100" step="5" /></label>
          <select class="sp-devs" title="Wo die Musik spielt"></select></div>
        <p class="sp-msg muted"></p>
        <small class="muted">Deine Playlists</small><div class="sp-lists"></div>
      </div></div>`;
  document.body.append(box);
  const $m = (s) => box.querySelector(s);
  const frame = $m('.md-frame'), url = $m('.md-url'), recentEl = $m('.md-recent'), spEl = $m('.md-sp');

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

  // ---- tabs -----------------------------------------------------------------------------------
  let tab = 'yt';
  try { tab = localStorage.getItem(TAB) || 'yt'; } catch { /* private window */ }
  function show(t) {
    tab = t;
    try { localStorage.setItem(TAB, t); } catch { /* private window */ }
    box.querySelectorAll('.md-tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === t));
    $m('.md-yt:not(.sp-search)').hidden = t !== 'yt'; $m('.sp-search').hidden = t !== 'sp';
    const yt = t === 'yt';
    if (!yt) { frame.src = 'about:blank'; frame.hidden = true; }   // a video does not play on under the music
    recentEl.hidden = !yt || !frame.hidden;
    spEl.hidden = yt;
    if (yt) { stopPolling(); if (frame.hidden) showRecent(); } else startPolling();
  }
  $m('.md-tabs').addEventListener('click', (e) => { const b = e.target.closest('button[data-tab]'); if (b) show(b.dataset.tab); });

  // ---- YouTube ----------------------------------------------------------------------------------
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
  $m('.md-yt:not(.sp-search)').addEventListener('submit', (e) => {
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

  // ---- Spotify ----------------------------------------------------------------------------------
  const mmss = (ms) => { const s = Math.round((ms || 0) / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  const msg = (t) => { $m('.sp-msg').textContent = t || ''; };
  let now = null, poll = 0, devPoll = 0, listsShown = false;

  async function refresh() {
    try { now = await get('/v1/spotify/player'); } catch (e) { msg(e.message); return; }
    msg('');
    const cover = $m('.sp-cover');
    // a cover that failed (it loads alongside 36 playlist pictures) is asked for again, else it stays empty
    if (now.cover) {
      if (cover.getAttribute('src') !== now.cover || (cover.complete && !cover.naturalWidth)) { cover.removeAttribute('src'); cover.src = now.cover; }
      cover.hidden = false;
    } else cover.hidden = true;
    $m('.sp-title').textContent = now.title || 'Gerade läuft nichts';
    $m('.sp-artist').textContent = now.title ? `${now.artist}${now.album ? ` · ${now.album}` : ''}` : 'Spotify auf Laptop, Handy oder TV öffnen -- oder unten eine Playlist wählen';
    $m('.sp-bar i').style.width = now.duration_ms ? `${(100 * now.progress_ms / now.duration_ms).toFixed(1)}%` : '0';
    $m('.sp-time').textContent = now.duration_ms ? `${mmss(now.progress_ms)} / ${mmss(now.duration_ms)}` : '';
    $m('.sp-pp').innerHTML = now.playing ? ICON.pause : ICON.play;
    const vol = $m('.sp-vol');
    if (now.volume != null && document.activeElement !== vol) vol.value = now.volume;
  }
  async function devices() {
    let d;
    try { d = (await get('/v1/spotify/devices')).devices; } catch { return; }
    const sel = $m('.sp-devs');
    if (document.activeElement === sel) return;
    sel.innerHTML = d.length ? d.map((x) => `<option value="${esc(x.id)}"${x.active ? ' selected' : ''}>${esc(x.name)}</option>`).join('')
      : '<option value="">kein Gerät offen</option>';
  }
  async function lists() {
    if (listsShown) return;
    let p;
    try { p = (await get('/v1/spotify/playlists')).playlists; } catch (e) { msg(e.message); return; }
    listsShown = true;
    $m('.sp-lists').innerHTML = p.map((x) => `<button type="button" data-uri="${esc(x.uri)}">${x.cover
      ? `<img src="${esc(x.cover)}" alt="" loading="lazy" />` : '<span class="md-pl">♫</span>'}<span>${esc(x.name)}</span></button>`).join('');
  }
  function startPolling() {
    refresh(); devices(); lists();
    clearInterval(poll); clearInterval(devPoll);
    poll = setInterval(refresh, 3000); devPoll = setInterval(devices, 15000);
  }
  function stopPolling() { clearInterval(poll); clearInterval(devPoll); }

  async function control(body) {
    try { await send('POST', '/v1/spotify/control', body); msg(''); } catch (e) { msg(e.message); }
    setTimeout(refresh, 400);
  }
  $m('.sp-ctl').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-a]');
    if (!b) return;
    const a = b.dataset.a === 'toggle' ? (now?.playing ? 'pause' : 'play') : b.dataset.a;
    control({ action: a });
  });
  $m('.sp-vol').addEventListener('change', (e) => control({ action: 'volume', value: +e.target.value }));
  $m('.sp-devs').addEventListener('change', (e) => { if (e.target.value) control({ action: 'transfer', device_id: e.target.value }); });
  $m('.sp-lists').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-uri]');
    if (b) control({ action: 'play_uri', uri: b.dataset.uri, device_id: $m('.sp-devs').value || null });
  });
  $m('.sp-search').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = $m('.sp-q').value.trim();
    if (q) control({ action: 'search', query: q, kind: 'track' });
    $m('.sp-q').value = '';
  });

  // ---- open / close -----------------------------------------------------------------------------
  function open(t) {
    window.AURON_chart?.close();
    place(); box.hidden = false;
    show(t || tab);
  }
  function close() {
    if (box.hidden) return;
    box.hidden = true; full = false;
    stopPolling();
    frame.src = 'about:blank'; frame.hidden = true;   // stops the video's sound (Spotify plays on)
  }
  $m('.pc-full').addEventListener('click', () => setFull());
  $m('.pc-x').addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.hidden) close(); });
  document.addEventListener('auron:chartopen', close);   // one window in the middle at a time
  addEventListener('resize', () => { if (!box.hidden) place(); });

  const toggle = (t) => (box.hidden || tab !== t ? open(t) : close());
  document.getElementById('ytBtn')?.addEventListener('click', () => toggle('yt'));
  document.getElementById('spBtn')?.addEventListener('click', () => toggle('sp'));
  window.AURON_media = { open, close, full: setFull, play: (text) => { const m = parse(text); if (m) { open('yt'); play(m, text); } return !!m; } };
})();
