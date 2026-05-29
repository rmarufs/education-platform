(function() {
    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    async function subscribeUser() {
        try {
            const reg = await navigator.serviceWorker.ready;
            
            // Get VAPID public key
            const pkRes = await fetch('/api/push/public-key');
            if (!pkRes.ok) throw new Error('Failed to get public key');
            const pkData = await pkRes.json();
            const applicationServerKey = urlBase64ToUint8Array(pkData.public_key);

            // Subscribe via PushManager
            const subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });

            // Send subscription to backend
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            const subRes = await fetch('/api/push/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify(subscription)
            });

            if (!subRes.ok) throw new Error('Failed to save subscription');
            
            console.log('Push subscription successful');
            updateBtnState(true);
        } catch (error) {
            console.error('Error subscribing to push:', error);
            updateBtnState(false);
        }
    }

    function updateBtnState(isSubscribed) {
        const btn = document.getElementById('push-subscribe-btn');
        if (!btn) return;
        
        if (Notification.permission === 'denied') {
            btn.style.display = 'none';
            return;
        }

        btn.style.display = 'inline-flex';
        if (isSubscribed || Notification.permission === 'granted') {
            btn.classList.add('subscribed');
            btn.innerHTML = '🔕';
            btn.title = 'Уведомления включены';
            btn.disabled = true; // For now we just disable it when subscribed, or we could implement unsubscribe
        } else {
            btn.classList.remove('subscribed');
            btn.innerHTML = '🔔';
            btn.title = 'Включить уведомления браузера';
            btn.disabled = false;
        }
    }

    async function initPush() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            return;
        }

        try {
            const reg = await navigator.serviceWorker.register('/sw.js');
            
            const btn = document.getElementById('push-subscribe-btn');
            if (btn) {
                btn.addEventListener('click', async () => {
                    const permission = await Notification.requestPermission();
                    if (permission === 'granted') {
                        await subscribeUser();
                    } else {
                        updateBtnState(false);
                    }
                });
            }

            // Check current subscription status
            const sub = await reg.pushManager.getSubscription();
            updateBtnState(!!sub);

        } catch (error) {
            console.error('Service Worker registration failed:', error);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPush);
    } else {
        initPush();
    }
})();
