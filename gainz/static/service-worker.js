const TIMER_NOTIFICATION_TAG = 'gainz-timer';

self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

function showTimerNotification(payload = {}) {
    const title = payload.title || 'Rest timer complete';
    const options = Object.assign(
        {
            body: 'Time to start your next set.',
            icon: '/static/favicon.ico',
            tag: TIMER_NOTIFICATION_TAG,
            renotify: true
        },
        payload.options || {}
    );

    return self.registration.showNotification(title, options);
}

self.addEventListener('message', event => {
    const data = event.data;
    if (!data || data.type !== 'timer-complete') {
        return;
    }

    event.waitUntil(showTimerNotification(data));
});

self.addEventListener('notificationclick', event => {
    event.notification.close();

    const targetUrl = event.notification?.data?.url || '/';

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
            for (const client of clientList) {
                if ('focus' in client) {
                    return client.focus();
                }
            }
            if (self.clients.openWindow) {
                return self.clients.openWindow(targetUrl);
            }
            return undefined;
        })
    );
});
