const CACHE_NAME = 'airspace-shell-v1';
const SHELL_ASSETS = [
  '/',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/apple-touch-icon.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok && !event.request.url.includes('/api/')) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        if (cached) return cached;
        if (event.request.mode === 'navigate') return caches.match('/');
        return Response.error();
      })
  );
});

self.addEventListener('push', event => {
  const data = event.data?.json() || {};
  const options = {
    ...(data.body ? {body: data.body} : {}),
    ...(data.image ? {image: data.image} : {}),
    tag: data.tag || 'airspace-flight',
    icon: '/icons/icon-192.png',
    data: {url: data.url || '/'}
  };
  event.waitUntil(self.registration.showNotification(data.title || 'A plane is nearby', options));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({type: 'window', includeUncontrolled: true}).then(windows => {
      const existing = windows.find(client => new URL(client.url).origin === self.location.origin);
      if (existing) {
        return existing.navigate(target).then(client => client?.focus());
      }
      return clients.openWindow(target);
    })
  );
});
