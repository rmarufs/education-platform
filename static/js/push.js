(function () {
    'use strict';

    var DISMISS_KEY = 'push_dismissed_until';
    var DISMISS_DAYS = 7; // сколько дней прятать после "Не сейчас"

    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var rawData = window.atob(base64);
        var outputArray = new Uint8Array(rawData.length);
        for (var i = 0; i < rawData.length; i++) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    function isDismissed() {
        try {
            var until = localStorage.getItem(DISMISS_KEY);
            if (!until) return false;
            return Date.now() < parseInt(until, 10);
        } catch (_) {
            return false;
        }
    }

    function saveDismiss() {
        try {
            var until = Date.now() + DISMISS_DAYS * 24 * 60 * 60 * 1000;
            localStorage.setItem(DISMISS_KEY, String(until));
        } catch (_) {}
    }

    function showCard() {
        var card = document.getElementById('push-permission-card');
        if (card) {
            card.style.display = '';
        }
    }

    function hideCard() {
        var card = document.getElementById('push-permission-card');
        if (card) {
            // плавное скрытие
            card.style.transition = 'opacity 0.3s ease, max-height 0.4s ease';
            card.style.opacity = '0';
            card.style.overflow = 'hidden';
            setTimeout(function () {
                card.style.display = 'none';
                card.style.opacity = '';
                card.style.overflow = '';
            }, 350);
        }
    }

    function showSuccessState() {
        var card = document.getElementById('push-permission-card');
        var defaultInner = card ? card.querySelector('.push-permission-card__inner:not(.push-permission-card__success)') : null;
        var successInner = document.getElementById('push-success-state');
        if (card) card.style.display = '';
        if (defaultInner) defaultInner.style.display = 'none';
        if (successInner) successInner.style.display = '';
        // автоскрыть через 5 секунд
        setTimeout(hideCard, 5000);
    }

    async function subscribeUser() {
        try {
            var reg = await navigator.serviceWorker.ready;
            var pkRes = await fetch('/api/push/public-key');
            if (!pkRes.ok) throw new Error('Failed to get public key');
            var pkData = await pkRes.json();
            var applicationServerKey = urlBase64ToUint8Array(pkData.public_key);

            var subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });

            var csrfMeta = document.querySelector('meta[name="csrf-token"]');
            var csrfToken = csrfMeta ? csrfMeta.content : '';
            var subRes = await fetch('/api/push/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(subscription)
            });

            if (!subRes.ok) throw new Error('Failed to save subscription');
            showSuccessState();
        } catch (err) {
            console.error('[push.js] Subscription error:', err);
            hideCard();
        }
    }

    async function handleEnableClick() {
        var permission = await Notification.requestPermission();
        if (permission === 'granted') {
            await subscribeUser();
        } else if (permission === 'denied') {
            hideCard();
        } else {
            // default — ничего не делаем, пользователь закрыл диалог
        }
    }

    function handleDismissClick() {
        saveDismiss();
        hideCard();
    }

    async function initPushCard() {
        // Проверяем поддержку API
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

        // Регистрируем service worker (если ещё не зарегистрирован)
        try {
            await navigator.serviceWorker.register('/sw.js');
        } catch (err) {
            console.warn('[push.js] SW registration failed:', err);
            return;
        }

        var permission = Notification.permission;

        // Если пользователь уже разрешил — не показываем карточку
        if (permission === 'granted') {
            // Убеждаемся, что подписка актуальна
            try {
                var reg = await navigator.serviceWorker.ready;
                var existingSub = await reg.pushManager.getSubscription();
                if (!existingSub) {
                    // Тихо переподписываем без показа карточки
                    await subscribeUser();
                }
            } catch (_) {}
            return;
        }

        // Если пользователь запретил — не показываем карточку
        if (permission === 'denied') return;

        // Если пользователь недавно нажал "Не сейчас" — не показываем
        if (isDismissed()) return;

        // Показываем карточку
        showCard();

        // Привязываем события
        var enableBtn = document.getElementById('push-enable-btn');
        var dismissBtn = document.getElementById('push-dismiss-btn');
        var closeBtn = document.getElementById('push-close-btn');
        var successCloseBtn = document.getElementById('push-success-close-btn');

        if (enableBtn) enableBtn.addEventListener('click', handleEnableClick);
        if (dismissBtn) dismissBtn.addEventListener('click', handleDismissClick);
        if (closeBtn) closeBtn.addEventListener('click', handleDismissClick);
        if (successCloseBtn) successCloseBtn.addEventListener('click', hideCard);
    }

    // Запускаем только на страницах с карточкой (наличие push-permission-card)
    function onReady() {
        if (document.getElementById('push-permission-card')) {
            initPushCard();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
    }
})();
