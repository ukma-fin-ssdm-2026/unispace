document.addEventListener('DOMContentLoaded', () => {
    console.log("Головна сторінка ініціалізована");

    // Обробка кліків по кнопках на головній картці
    const actionButtons = document.querySelectorAll('.hero-actions a');

    actionButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const actionName = this.innerText.trim();
            console.log(`Навігація до: ${actionName}`);

            // Легкий візуальний ефект натискання
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
});
