document.addEventListener('DOMContentLoaded', async function () {
    const isLoginPage = window.location.pathname.includes('/login/');

    // 1. ЗАХИСТ СТОРІНОК ТА ОДЕРЖАННЯ ПРОФІЛЮ З БЕКЕНДУ
    if (!isLoginPage) {
        try {
            // Звертаємося до бекенду за правильним URL
            const response = await fetch('https://unispace-wtf6.onrender.com/api/v1/auth/me/', {
                method: 'GET',
                headers: { 'Accept': 'application/json' },
                credentials: 'include' // Передаємо сесійні куки на бекенд
            });

            if (!response.ok) {
                // Якщо бекенд відповів 403 (не авторизовано) - викидаємо на логін
                window.location.href = '/login/';
                return;
            }

            // Якщо успішно, виводимо справжнє ім'я з БД
            const userData = await response.json();
            const profileElement = document.querySelector('.user-profile');
            if (profileElement) {
                profileElement.innerHTML = `<i class="fa-solid fa-circle-user" style="font-size: 1.5rem; color: var(--color-primary);"></i> ${userData.full_name}`;
            }
        } catch (error) {
            console.error("Не вдалося перевірити авторизацію:", error);
            window.location.href = '/login/';
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
                await fetch('https://unispace-wtf6.onrender.com/auth/logout/', {
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
