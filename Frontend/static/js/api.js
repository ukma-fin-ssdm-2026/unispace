/*
 * Спільний клієнт API бекенду UniSpace.
 * Адреса бекенду береться з <body data-api-base> (налаштування BACKEND_API_URL), а не вписується в код.
 * Сесія - cookie бекенду, тому всі запити йдуть з credentials: 'include'.
 * Для POST/PATCH/DELETE потрібен CSRF-токен: фронтенд на іншому домені не може прочитати cookie бекенду,
 * тож отримує токен з /api/v1/auth/csrf/ і передає його в заголовку X-CSRFToken.
 *
 * Примітка щодо використання ШІ: модуль згенеровано ШІ (Claude).
 */

const UniSpaceApi = (() => {
    const apiBase = document.body.dataset.apiBase;
    const backendOrigin = document.body.dataset.backendOrigin;
    let csrfToken = null;

    class ApiError extends Error {
        constructor(status, payload) {
            const message = payload?.error?.message || `Помилка сервера (${status})`;
            super(message);
            this.status = status;
            this.payload = payload;
        }
    }

    async function getCsrfToken() {
        if (!csrfToken) {
            // Виправлення REL-H01: Додано тайм-аут
            const response = await fetch(`${apiBase}auth/csrf/`, {
                credentials: 'include',
                signal: AbortSignal.timeout(10000)
            });

            // Виправлення REL-H03: Перевірка статусу та формату токена
            if (!response.ok) {
                throw new Error(`Не вдалося отримати CSRF-токен (Статус: ${response.status})`);
            }

            const data = await response.json();
            if (!data || typeof data.csrfToken !== 'string' || !data.csrfToken.trim()) {
                throw new Error('Отримано невалідний CSRF-токен');
            }

            csrfToken = data.csrfToken;
        }
        return csrfToken;
    }

    async function request(path, { method = 'GET', body = null, json = null, absolute = false, timeout = 10000 } = {}) {
        const headers = { Accept: 'application/json' };
        if (method !== 'GET') {
            headers['X-CSRFToken'] = await getCsrfToken();
        }
        if (json !== null) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(json);
        }
        const url = absolute ? `${backendOrigin}${path}` : `${apiBase}${path}`;

        // Виправлення REL-H01: Додано тайм-аут
        const response = await fetch(url, {
            method,
            headers,
            body,
            credentials: 'include',
            signal: AbortSignal.timeout(timeout)
        });

        if (response.status === 204) {
            return null;
        }

        // Виправлення REL-H02: Явна обробка помилок JSON-парсингу
        let payload;
        try {
            payload = await response.json();
        } catch (error) {
            if (response.ok) {
                throw new Error('Отримано некоректну JSON-відповідь від сервера');
            }
            payload = null;
        }

        if (!response.ok) {
            throw new ApiError(response.status, payload);
        }

        return payload;
    }

    /** Текст помилки для користувача: повідомлення бекенду або перше поле з помилкою валідації. */
    function describeError(error) {
        const details = error.payload?.error?.details;
        if (Array.isArray(details) && details.length) {
            return details.map((d) => d.message || d.issue || d.field).join('; ');
        }
        return error.message;
    }

    return {
        get: (path) => request(path),
        post: (path, options = {}) => request(path, { ...options, method: 'POST' }),
        del: (path) => request(path, { method: 'DELETE' }),
        logout: () => request('/auth/logout/', { method: 'POST', absolute: true }),
        describeError
    };
})();

/** Створює елемент з текстом без innerHTML (дані з API не потрапляють у розмітку як HTML). */
function el(tag, { className = '', text = '', attrs = {} } = {}, children = []) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    children.forEach((child) => child && node.append(child));
    return node;
}
