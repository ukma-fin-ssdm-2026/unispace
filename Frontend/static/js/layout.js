document.addEventListener('DOMContentLoaded', function () {
    // --- Логіка згортання сайдбару ---
    const sidebarToggleBtn = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');

    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');

            // Змінюємо стрілочку в залежності від стану сайдбару
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

    // --- Модальне вікно виходу ---
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

    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) toggleModal(false);
        });
    }

    if (btnConfirm) {
        btnConfirm.addEventListener('click', () => {
            console.log("Очищення сесії...");
            // window.location.href = "/login/";
        });
    }
});
