// AURON's service worker: only for his notifications (backend/app/push) -- it shows a message even when the
// dashboard is not in front, on the laptop and on the iPhone's home-screen app. A tap opens AURON.
// Nothing is cached here: the dashboard always loads fresh.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || 'AURON', {
    body: d.body || '', icon: '/app-icon-192.png', badge: '/icon-192.png', tag: d.tag || undefined,
    renotify: !!d.tag, data: { url: d.url || '/' },
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    const open = list.find((c) => new URL(c.url).origin === self.location.origin);
    return open ? open.focus() : self.clients.openWindow(url);
  }));
});
