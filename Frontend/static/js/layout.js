document.addEventListener('DOMContentLoaded', async function () {
    const isLoginPage = window.location.pathname.includes('/login/');

    // Адреса бекенду - з BACKEND_API_URL (<body data-backend-origin>), як у кнопці входу Microsoft,
    // щоб запити йшли на той самий хост, де бекенд створив сесію. Запасний варіант - як було раніше.
    const isLocalhost = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
    const BACKEND_BASE_URL = document.body.dataset.backendOrigin
        || (isLocalhost ? `http://${window.location.hostname}:8000` : 'https://unispace-wtf6.onrender.com');

    // 1. ЗАХИСТ СТОРІНОК ТА ОДЕРЖАННЯ ПРОФІЛЮ З БЕКЕНДУ
    if (!isLoginPage) {
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/me/`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' },
                credentials: 'include'
            });

            if (!response.ok) {
                window.location.href = '/login/';
                return;
            }

            // Отримуємо дані користувача з БД
            const userData = await response.json();

            // Зберігаємо глобально (корисно з main) та диспачимо подію
            window.currentUser = userData;

            const profileElement = document.querySelector('.user-profile');
            if (profileElement) {
                profileElement.innerHTML = `<i class="fa-solid fa-circle-user" style="font-size: 1.5rem; color: var(--color-primary);"></i> ${userData.full_name || userData.email}`;
            }

            // --- ВАШІ РОЛІ ТА КЛАСИ (працюють надійтно) ---
            if (userData.role === 'teacher' || userData.role === 'dispatcher') {
                document.querySelectorAll('.js-teacher-dispatcher-only').forEach(el => {
                    el.style.display = 'flex';
                });
            }

            if (userData.role === 'dispatcher') {
                const adminHeading = document.querySelector('.js-admin-heading');
                if (adminHeading) adminHeading.style.display = 'block';

                document.querySelectorAll('.js-dispatcher-only').forEach(el => {
                    el.style.display = 'flex';
                });
            }

            // Додатково підтримуємо data-roles з main (якщо десь використовуються)
            document.querySelectorAll('[data-roles]').forEach((item) => {
                if (userData.role) {
                    item.hidden = !item.dataset.roles.split(' ').includes(userData.role);
                }
            });

            // Повідомляємо інші скрипти про завантаження користувача (з main)
            document.dispatchEvent(new CustomEvent('unispace:user', { detail: userData }));

        } catch (error) {
            // 403 або помилка мережі — на сторінку входу
            console.error("Не вдалося перевірити авторизацію:", error);
            window.location.href = '/login/';
            return;
        }
    }

    // 2. ЗГОРТАННЯ САЙДБАРУ
    const sidebarToggleBtn = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');

    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            const icon = sidebarToggleBtn.querySelector('i');
            if (sidebar.classList.contains('collapsed')) {
                icon.classList.remove('fa-chevron-left');
                icon.classList.add('fa-chevron-right');
            } else {
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-left');
            }
        });
    }

    // 3. ЛОГІКА МОДАЛЬНОГО ВІКНА ТА СПРАВЖНЬОГО ВИХОДУ
    const modalOverlay = document.getElementById('global-logout-modal');
    const btnLogoutTriggers = document.querySelectorAll('.js-logout-trigger');
    const btnCancel = document.getElementById('btn-global-cancel');
    const btnConfirm = document.getElementById('btn-global-confirm');

    function toggleModal(show) {
        if (modalOverlay) {
            show ? modalOverlay.classList.add('active') : modalOverlay.classList.remove('active');
        }
    }

    btnLogoutTriggers.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            toggleModal(true);
        });
    });

    if (btnCancel) {
        btnCancel.addEventListener('click', () => toggleModal(false));
    }

    if (btnConfirm) {
        // Запит на вихід до бекенду з урахуванням динамічного URL
        btnConfirm.addEventListener('click', async () => {
            try {
                await fetch(`${BACKEND_BASE_URL}/auth/logout/`, {
                    method: 'POST',
                    credentials: 'include'
                });
            } catch (error) {
                console.error("Помилка при виході:", error);
            }
            window.location.href = "/login/";
        });
    }
});
