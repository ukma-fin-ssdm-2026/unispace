/**
 * Локальна розробка: тримаємо фронтенд на тому ж хості, що й бекенд (localhost).
 * Сесійна cookie бекенду прив'язана до хоста, а Microsoft Entra повертає лише на http://localhost,
 * тому на http://127.0.0.1:8001 запити до бекенду йшли б без сесії. Скрипт переводить сторінку
 * на хост із BACKEND_API_URL. На Render (не loopback-адреси) нічого не робить.
 *
 * Примітка щодо використання ШІ: скрипт згенеровано ШІ (Claude), перевірено вручну локально.
 */
(function () {
    const meta = document.querySelector('meta[name="unispace-backend-origin"]');
    if (!meta || !meta.content) return;

    let backendHost;
    try {
        backendHost = new URL(meta.content).hostname;
    } catch {
        return;
    }

    const loopback = ['localhost', '127.0.0.1'];
    const currentHost = window.location.hostname;
    if (loopback.includes(currentHost) && loopback.includes(backendHost) && currentHost !== backendHost) {
        const url = new URL(window.location.href);
        url.hostname = backendHost;
        window.location.replace(url.toString());
    }
})();
