document.addEventListener('DOMContentLoaded', function() {
    const isLocalhost = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
    const devLoginSection = document.querySelector('.dev-login-section');

    if (devLoginSection) {
        // Приховуємо блок, якщо це не локальна розробка (Render)
        devLoginSection.style.display = isLocalhost ? 'block' : 'none';
    }
});
