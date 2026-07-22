self.addEventListener('push', event => {
  const data = event.data?.json() || {};
  const options = {
    ...(data.body ? {body: data.body} : {}),
    tag: data.tag || 'airspace-flight',
    icon: '/icons/icon-192.png',
    data: {url: data.url || '/'}
  };
  event.waitUntil(self.registration.showNotification(data.title || 'A plane is nearby', options));
});
self.addEventListener('notificationclick', event => { event.notification.close(); event.waitUntil(clients.openWindow(event.notification.data?.url || '/')); });
