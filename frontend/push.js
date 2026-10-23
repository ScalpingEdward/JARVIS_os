// AURON's own notifications (backend/app/push) -- Einstellungen > Benachrichtigungen: switch them on for
// this device (laptop or iPhone; the iPhone needs AURON on its home screen, iOS 16.4 or newer), send a test,
// and choose per kind of message: app, Telegram or both.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const NAMES = { mail: 'Wichtige Post', markets: 'Märkte (Insider, Makro)', watchlist: 'Watchlist-Alarme', instagram: 'Instagram-Zeitplan',
    copier: 'Kopierer (Störungen)', trades: 'Trades', system: 'System (Backup)', other: 'Sonstiges' };
  const WAYS = { app: 'App', telegram: 'Telegram', both: 'Beides' };
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const reg = supported ? navigator.serviceWorker.register('/sw.js').catch(() => null) : Promise.resolve(null);
  const call = async (method, path, body) => {
    const r = await fetch(`${API_BASE}/v1/push${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
    return d;
  };
  const key = (b64) => { const p = '='.repeat((4 - (b64.length % 4)) % 4), raw = atob((b64 + p).replace(/-/g, '+').replace(/_/g, '/')); return Uint8Array.from(raw, (c) => c.charCodeAt(0)); };
  const deviceName = () => (/iPhone/.test(navigator.userAgent) ? 'iPhone' : /iPad/.test(navigator.userAgent) ? 'iPad' : /Android/.test(navigator.userAgent) ? 'Handy' : 'Laptop');

  async function current() {
    const r = await reg;
    return r ? r.pushManager.getSubscription() : null;
  }
  async function enable() {
    const r = await reg;
    if (!r) throw new Error('Mitteilungen gehen hier nicht' + (/iPhone|iPad/.test(navigator.userAgent) ? ' – AURON erst zum Home-Bildschirm hinzufügen und von dort öffnen' : ''));
    if (await Notification.requestPermission() !== 'granted') throw new Error('Mitteilungen wurden nicht erlaubt (Einstellungen des Geräts)');
    const { key: k } = await call('GET', '/key');
    const sub = await r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key(k) });
    await call('POST', '/subscribe', { subscription: sub.toJSON(), device: deviceName() });
  }
  async function disable() {
    const sub = await current();
    if (sub) { await call('POST', '/unsubscribe', { subscription: sub.toJSON() }); await sub.unsubscribe(); }
  }

  async function editor(el) {
    let s, sub;
    try { [s, sub] = await Promise.all([call('GET', '/settings'), current()]); } catch (e) { el.innerHTML = `<p class="th-text">Nicht erreichbar: ${esc(e.message)}</p>`; return; }
    el.innerHTML = `<section class="th-sec"><h4>Dieses Gerät</h4>
        ${!supported ? `<p class="th-text">Mitteilungen gehen in diesem Browser nicht.${/iPhone|iPad/.test(navigator.userAgent) ? ' Auf dem iPhone: AURON über „Teilen › Zum Home-Bildschirm“ hinzufügen und von dort öffnen.' : ''}</p>`
          : sub ? '<p class="th-text">Mitteilungen sind hier <b>an</b>.</p><div class="nf-btns"><button type="button" data-n="test">Test senden</button><button type="button" data-n="off">Ausschalten</button></div>'
          : '<p class="th-text">Mitteilungen sind hier aus.</p><div class="nf-btns"><button type="button" data-n="on" class="nf-main">Auf diesem Gerät einschalten</button></div>'}
        <p class="th-text nf-devs">Eingeschaltet auf: ${s.devices.map((d) => esc(d.device)).join(', ') || '–'}</p></section>
      <section class="th-sec"><h4>Was wohin</h4>
        ${Object.entries(s.routes).map(([c, w]) => `<div class="nf-row"><span>${NAMES[c] || c}</span><div class="seg nf-seg">${s.ways.map((x) =>
          `<button type="button" data-cat="${c}" data-way="${x}" class="${x === w ? 'on' : ''}">${WAYS[x]}</button>`).join('')}</div></div>`).join('')}
        <p class="th-text">Stumm geschaltete Kategorien bleiben überall stumm. Karten mit Knöpfen (Freigaben) kommen weiter über Telegram.</p></section>`;
    el.onclick = async (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      b.disabled = true;
      try {
        if (b.dataset.n === 'on') await enable();
        if (b.dataset.n === 'off') await disable();
        if (b.dataset.n === 'test') await call('POST', '/test');
        if (b.dataset.cat) await call('PUT', '/route', { category: b.dataset.cat, way: b.dataset.way });
        editor(el);
      } catch (err) { alert(err.message); b.disabled = false; }
    };
  }
  window.AURON_push = { editor };
})();
