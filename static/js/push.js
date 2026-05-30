(function () {
    'use strict';

    // ── Утилиты ─────────────────────────────────────────────────────────────

    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var rawData = window.atob(base64);
        var out = new Uint8Array(rawData.length);
        for (var i = 0; i < rawData.length; i++) out[i] = rawData.charCodeAt(i);
        return out;
    }

    function getCsrf() {
        var m = document.querySelector('meta[name="csrf-token"]');
        return m ? m.content : '';
    }

    // ── Управление состояниями карточки ─────────────────────────────────────

    var STATES = ['default', 'later', 'granted', 'denied', 'unsubscribed', 'unsupported'];

    function showState(name) {
        STATES.forEach(function (s) {
            var el = document.getElementById('push-state-' + s);
            if (el) el.style.display = (s === name) ? '' : 'none';
        });
    }

    // ── API-вызовы ───────────────────────────────────────────────────────────

    async function subscribe() {
        var reg = await navigator.serviceWorker.ready;
        var pkRes = await fetch('/api/push/public-key');
        if (!pkRes.ok) {
            // VAPID ключи не настроены на сервере — тихо выходим
            console.warn('[push.js] public-key endpoint returned', pkRes.status, '— push not configured on server');
            return null;
        }
        var pkData = await pkRes.json();
        var appKey = urlBase64ToUint8Array(pkData.public_key);

        var sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: appKey
        });

        var subJson = sub.toJSON();
        var res = await fetch('/api/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ endpoint: subJson.endpoint, keys: subJson.keys })
        });
        if (!res.ok) throw new Error('subscribe API failed');
        return sub;
    }

    async function unsubscribeCurrentSub(sub) {
        var endpoint = sub.endpoint;
        // Сначала уведомляем backend
        try {
            await fetch('/api/push/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
                body: JSON.stringify({ endpoint: endpoint })
            });
        } catch (_) {}
        // Затем отписываемся в браузере
        await sub.unsubscribe();
    }

    // ── Определение начального состояния ────────────────────────────────────

    async function detectInitialState() {
        var permission = Notification.permission;

        if (permission === 'denied') {
            return 'denied';
        }

        var reg = await navigator.serviceWorker.ready;
        var existingSub = await reg.pushManager.getSubscription();

        if (permission === 'granted' && existingSub) {
            return 'granted';
        }

        if (permission === 'granted' && !existingSub) {
            // Permission есть, но активной подписки нет
            return 'unsubscribed';
        }

        // permission === 'default'
        return 'default';
    }

    // ── Обработчики кнопок ──────────────────────────────────────────────────

    async function handleEnable() {
        var permission = await Notification.requestPermission();
        if (permission === 'granted') {
            try {
                var result = await subscribe();
                if (result === null) {
                    // Сервер не настроен — остаёмся в текущем состоянии, не ломаем UI
                    console.warn('[push.js] Server not configured for push, staying in current state');
                    return;
                }
                showState('granted');
            } catch (err) {
                console.error('[push.js] Subscribe error:', err);
            }
        } else if (permission === 'denied') {
            showState('denied');
        }
        // 'default' — пользователь закрыл диалог, ничего не меняем
    }

    async function handleDisable() {
        try {
            var reg = await navigator.serviceWorker.ready;
            var sub = await reg.pushManager.getSubscription();
            if (sub) {
                await unsubscribeCurrentSub(sub);
            }
            showState('unsubscribed');
        } catch (err) {
            console.error('[push.js] Unsubscribe error:', err);
        }
    }

    function handleLater() {
        showState('later');
    }

    // ── Инициализация ────────────────────────────────────────────────────────

    async function initPrefCard() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            showState('unsupported');
            return;
        }

        try {
            await navigator.serviceWorker.register('/sw.js');
        } catch (err) {
            console.warn('[push.js] SW registration failed:', err);
            return;
        }

        var initialState = await detectInitialState();
        showState(initialState);

        // Привязываем кнопки
        var enableBtn    = document.getElementById('push-enable-btn');
        var enableBtn2   = document.getElementById('push-enable-btn-2');
        var laterBtn     = document.getElementById('push-later-btn');
        var disableBtn   = document.getElementById('push-disable-btn');
        var resubBtn     = document.getElementById('push-resubscribe-btn');

        if (enableBtn)  enableBtn.addEventListener('click', handleEnable);
        if (enableBtn2) enableBtn2.addEventListener('click', handleEnable);
        if (laterBtn)   laterBtn.addEventListener('click', handleLater);
        if (disableBtn) disableBtn.addEventListener('click', handleDisable);
        if (resubBtn)   resubBtn.addEventListener('click', handleEnable);
    }

    function onReady() {
        if (document.getElementById('push-pref-card')) {
            initPrefCard();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
    }
})();
