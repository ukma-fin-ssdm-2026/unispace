document.addEventListener('DOMContentLoaded', async function () {
    const isLoginPage = window.location.pathname.includes('/login/');

    // 1. ЗАХИСТ СТОРІНОК, ПРОФІЛЬ І МЕНЮ ЗА РОЛЛЮ (дані з бекенду, /api/v1/auth/me/)
    if (!isLoginPage) {
        try {
            const user = await UniSpaceApi.get('auth/me/');
            window.currentUser = user;

            const nameElement = document.querySelector('.js-user-name');
            if (nameElement) {
                nameElement.textContent = user.full_name || user.email;
            }

            // Пункти меню з data-roles показуємо лише відповідним ролям
            document.querySelectorAll('[data-roles]').forEach((item) => {
                item.hidden = !item.dataset.roles.split(' ').includes(user.role);
            });

            document.dispatchEvent(new CustomEvent('unispace:user', { detail: user }));
        } catch (error) {
            // 403 (не увійшли) або бекенд недоступний - на сторінку входу
            console.error('Не вдалося перевірити авторизацію:', error);
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
        // Справжній запит на вихід до бекенду
        btnConfirm.addEventListener('click', async () => {
            try {
                await UniSpaceApi.logout();
            } catch (error) {
                console.error("Помилка при виході:", error);
            }
            window.location.href = "/login/";
        });
    }
});
