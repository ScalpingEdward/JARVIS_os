// AURON speaks up on his own -- only for what matters, and only while Brano wants it:
// an important email, an Instagram post that went out, a trade that closed. Each announcement also
// lands in the chat, so "ja" / "lies sie vor" afterwards has its context.
// Settings › Durchsagen: on/off and quiet hours (default 22:00-07:00).
(() => {
  const KEY = 'auron_announce';
  const DEF = { on: true, quietFrom: 22, quietTo: 7, mail: true, instagram: true, trades: true };
  let cfg = { ...DEF };
  try { cfg = { ...DEF, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { /* private window */ }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(cfg)); } catch { /* private window */ } };
  const eur = (v) => `${v >= 0 ? 'plus' : 'minus'} ${Math.abs(v).toLocaleString('de-DE', { maximumFractionDigits: 2 })} Euro`;

  function quiet() {
    const h = new Date().getHours(), { quietFrom: a, quietTo: b } = cfg;
    return a === b ? false : a < b ? h >= a && h < b : h >= a || h < b;
  }

  function announce(kind, text) {
    if (!cfg.on || !cfg[kind]) return;
    window.AURON_voice?.note(text);            // always in the chat, even at night
    if (quiet()) return;
    window.AURON_voice?.say(text);
  }

  // trades: app.js fires this when a closed trade shows up (the ring pulses at the same moment)
  document.addEventListener('auron:trade-closed', (e) => {
    const c = e.detail;
    announce('trades', `Sir, ${c.group} hat einen Trade ${c.profit >= 0 ? 'im Gewinn' : 'im Verlust'} geschlossen: ${c.symbol || ''} ${eur(c.profit)}.`);
  });

  // important mail: new ids since the last look; the first look only learns what is there
  const seenMail = new Set();
  let mailPrimed = false;
  document.addEventListener('auron:mail', (e) => {
    const fresh = e.detail.filter((m) => !seenMail.has(m.id));
    e.detail.forEach((m) => seenMail.add(m.id));
    if (!mailPrimed) { mailPrimed = true; return; }
    if (!fresh.length) return;
    const who = (f) => (f.split('<')[0].trim().replace(/"/g, '') || f).slice(0, 40);
    announce('mail', fresh.length === 1
      ? `Sir, eine wichtige E-Mail ist gekommen, von ${who(fresh[0].from)}: ${fresh[0].subject}. Soll ich sie vorlesen?`
      : `Sir, ${fresh.length} wichtige E-Mails sind gekommen, die erste von ${who(fresh[0].from)}. Soll ich sie zusammenfassen?`);
  });

  // Instagram: the number of posts went up
  let posted = null;
  document.addEventListener('auron:instagram', async (e) => {
    const n = e.detail.posted_total;
    if (posted !== null && n > posted) {
      let kind = 'der Post';
      try {
        const r = await fetch(`${window.AURON_API || '/api'}/v1/instagram/candidates?status=posted`);
        const items = ((await r.json()).items || []).sort((a, b) => String(b.posted_at || b.created_at).localeCompare(String(a.posted_at || a.created_at)));
        kind = { reel: 'das Reel', carousel: 'das Karussell', single_image: 'das Foto' }[items[0]?.post_format] || kind;
      } catch { /* the sentence works without it */ }
      announce('instagram', `Sir, ${kind} ist auf Instagram veröffentlicht.`);
    }
    posted = n;
  });

  // Settings › Durchsagen
  window.AURON_announce = {
    editor(box) {
      const paint = () => {
        box.innerHTML = `<label class="an-row"><input type="checkbox" id="anOn" ${cfg.on ? 'checked' : ''}/> <b>Durchsagen</b></label>
          <p class="th-text">AURON meldet sich von selbst – mit Stimme und im Chat.</p>
          ${[['mail', 'Wichtige E-Mails'], ['instagram', 'Instagram veröffentlicht'], ['trades', 'Trade geschlossen']].map(([k, n]) =>
            `<label class="an-row"><input type="checkbox" data-an="${k}" ${cfg[k] ? 'checked' : ''} ${cfg.on ? '' : 'disabled'}/> ${n}</label>`).join('')}
          <span class="th-label">Ruhezeit (nur Chat, keine Stimme)</span>
          <div class="an-quiet"><select id="anFrom">${[...Array(24).keys()].map((h) => `<option ${h === cfg.quietFrom ? 'selected' : ''}>${h}</option>`).join('')}</select> bis
            <select id="anTo">${[...Array(24).keys()].map((h) => `<option ${h === cfg.quietTo ? 'selected' : ''}>${h}</option>`).join('')}</select> Uhr</div>
          <button type="button" class="th-reset" id="anTest">Probe-Durchsage</button>`;
        box.querySelector('#anOn').onchange = (e) => { cfg.on = e.target.checked; save(); paint(); };
        box.querySelectorAll('[data-an]').forEach((c) => { c.onchange = () => { cfg[c.dataset.an] = c.checked; save(); }; });
        box.querySelector('#anFrom').onchange = (e) => { cfg.quietFrom = Number(e.target.value); save(); };
        box.querySelector('#anTo').onchange = (e) => { cfg.quietTo = Number(e.target.value); save(); };
        box.querySelector('#anTest').onclick = () => window.AURON_voice?.say('Sir, so klinge ich, wenn etwas Wichtiges passiert.');
      };
      paint();
    },
  };
})();
