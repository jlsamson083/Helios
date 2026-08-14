self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(data.title || 'Helios', {
    body: data.body || 'A new energy event was recorded.',
    icon: '/icon.png',
    badge: '/favicon.png',
    data: { url: data.url || '/alerts' },
    tag: data.title || 'helios-alert',
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url || '/alerts'));
});
