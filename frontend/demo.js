// Demo mode: http://127.0.0.1:8080/?demo -- the dashboard with made-up accounts, groups,
// mail and trades, for screenshots on the website. Nothing real is fetched or shown;
// without ?demo this file does nothing.
(() => {
  if (!new URLSearchParams(location.search).has('demo')) return;
  const now = Date.now(), iso = (ms) => new Date(ms).toISOString();
  const spark = (base, drift) => Array.from({ length: 30 }, (_, i) => +(base * (1 + drift * i / 30 + Math.sin(i / 3) * 0.006)).toFixed(2));
  const group = (name, today, week, total, closed, open = 0, openPnl = 0) =>
    ({ name, pnl_today: today, pnl_week: week, pnl_total: total, closed_trades: closed, open_positions: open, open_pnl: openPnl });
  const acc = (profile, label, bal, groups) => ({ profile, label, state: 'live', currency: 'EUR', account_login: 1, server: 'Demo',
    balance: bal, equity: bal + 38.4, captured_at: iso(now), received_at: iso(now), groups, open_positions: [], closed: [] });
  const accounts = [
    acc('gold', 'Gold Signals Pro', 12480.55, [group('Gold Signals Pro', 186.4, 642.9, 2480.55, 41, 2, 38.4)]),
    acc('crypto', 'Crypto Wave', 5310.2, [group('Crypto Wave', 54.1, 212.3, 310.2, 18)]),
    acc('fx', 'FX Elite Room', 8905.75, [group('FX Elite Room', -12.6, 96.4, 905.75, 27)]),
  ];
  const fixtures = {
    '/v1/copier/overview': {
      totals: [{ currency: 'EUR', accounts: 3, balance: 26696.5, equity: 26734.9, pnl_today: 227.9, pnl_week: 951.6, pnl_total: 3696.5, open_pnl: 38.4, open_positions: 2 }],
      accounts,
      groups: accounts.map((a) => ({ ...a.groups[0], currency: 'EUR', accounts: [a.profile] })),
    },
    '/v1/copier/history': Object.fromEntries(accounts.map((a) => [a.profile,
      Array.from({ length: 48 }, (_, i) => ({ at: iso(now - (48 - i) * 1800e3), balance: a.balance, equity: a.balance - 180 + i * 4.5 + Math.sin(i / 4) * 30 }))])),
    '/v1/watchlist': { captured_at: iso(now), received_at: iso(now), stale: false, items: [
      ['Bitcoin', 'Krypto', 1, 98420, 1.84], ['Gold', 'Rohstoffe', 2, 4212.5, 0.62], ['Silber', 'Rohstoffe', 3, 58.4, 1.1],
      ['Nasdaq 100', 'Indizes', 4, 30120, 0.74], ['S&P 500', 'Indizes', 5, 7810, 0.41], ['NVIDIA', 'Aktien', 0, 182.3, 2.3],
    ].map(([name, category, top, price, ch]) => ({ name, category, top, price, change_pct: ch, from_high_pct: -4.2, vs_sma200_pct: 6.1, rsi14: 58,
      notes: [], spark: spark(price, ch / 100), reason: '', recommended_by: '', analysis: '' })) },
    '/v1/instagram/dashboard': { needs_your_review: 2, curated_drafts_pending: 14, media_pool_available: 186, media_pool_used: 64, posted_total: 48,
      post_failed: 0, approved_ready_to_publish: 1, recent_candidates: [] },
    '/v1/telegram-instagram/schedule': { running: true, next: '19:00 reel', next_kind: 'reel', already_posted_today: true, already_fired_today: ['12:00'] },
    '/v1/mail': { connected: true, error: '', last_poll: iso(now), drafts: [], items: [
      { id: 'd1', from: 'Finanzamt Musterstadt <post@finanzamt.example>', subject: 'Ihr Steuerbescheid 2025', summary: 'Bescheid liegt vor, Einspruchsfrist bis 30.11.', important: true, done: false, category: 'steuer' },
      { id: 'd2', from: 'Hausverwaltung Nord <info@hv-nord.example>', subject: 'Nebenkostenabrechnung', summary: 'Nachzahlung 84 €, fällig zum 15.11.', important: true, done: false, category: 'rechnung' },
      { id: 'd3', from: 'Anna Berger <anna@example.com>', subject: 'Treffen nächste Woche?', summary: 'Fragt nach einem Termin Dienstag oder Mittwoch.', important: true, done: false, category: 'person' },
    ] },
    '/v1/smartmoney': { macro_error: '', insider_connected: true, insider_error: '', clusters: { PLTR: ['A', 'B', 'C'] },
      macro: [{ title: 'CPI m/m', title_de: 'Inflation', currency: 'USD', at: iso(now + 2 * 3600e3), forecast: '0.3%' },
        { title: 'Federal Funds Rate', title_de: 'Fed-Zinsentscheid', currency: 'USD', at: iso(now + 50 * 3600e3), forecast: '4.25%' }],
      insider: [{ ticker: 'NVDA', name: 'NVIDIA', owner: 'Director Example', title: 'Director', code: 'P', value: 2.4e6, traded_on: iso(now - 864e5) },
        { ticker: 'MSFT', name: 'Microsoft', owner: 'Officer Example', title: 'CFO', code: 'P', value: 860e3, traded_on: iso(now - 2 * 864e5) }] },
    '/health': { status: 'healthy' },
    '/v1/telegram-instagram/status': { bot_reachable: true },
  };
  const realFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    const path = url.replace(/^.*?\/api/, '').split('?')[0];
    if (url.includes('/api/') || url.startsWith('/api')) {
      const body = fixtures[path];
      return Promise.resolve(new Response(JSON.stringify(body ?? {}), { status: body ? 200 : 404, headers: { 'Content-Type': 'application/json' } }));
    }
    return realFetch(input, init);
  };
  document.documentElement.classList.add('demo');
})();
