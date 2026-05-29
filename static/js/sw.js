self.addEventListener('push', function(event) {
    if (!event.data) return;
    
    try {
        const data = event.data.json();
        const title = data.title || 'Новое уведомление';
        const options = {
            body: data.body,
            icon: data.icon || '/static/favicon/android-chrome-192x192.png',
            badge: data.badge || '/static/favicon/favicon-32x32.png',
            data: {
                targetUrl: data.targetUrl || '/dashboard'
            }
        };
        
        event.waitUntil(self.registration.showNotification(title, options));
    } catch (e) {
        console.error('Error parsing push data', e);
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const targetUrl = event.notification.data && event.notification.data.targetUrl ? event.notification.data.targetUrl : '/dashboard';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(windowClients) {
            for (let i = 0; i < windowClients.length; i++) {
                const client = windowClients[i];
                if (client.url.includes(targetUrl) && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
