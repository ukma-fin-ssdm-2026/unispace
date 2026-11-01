document.addEventListener('DOMContentLoaded', () => {
    // Логіка анімації привітальної картки
    const actionButtons = document.querySelectorAll('.hero-actions a');
    actionButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => { this.style.transform = ''; }, 150);
        });
    });
});

// Логіка для головного дашборду
document.addEventListener('unispace:user', async (event) => {
    const user = event.detail;
    const greetingEl = document.getElementById('dashboard-greeting');
    const actionsBox = document.getElementById('quick-actions');
    const lessonsBox = document.getElementById('dashboard-lessons');

    if (!greetingEl) return;

    // 1. Персоналізоване привітання
    const dateOptions = { weekday: 'long', day: 'numeric', month: 'long' };
    const todayStr = new Intl.DateTimeFormat('uk-UA', dateOptions).format(new Date());

    greetingEl.textContent = `Вітаємо, ${user.full_name || user.email}! Сьогодні ${todayStr}.`;

    // 2. Генерація швидких дій
    if (user.role === 'teacher' || user.role === 'dispatcher') {
        actionsBox.append(el('a', { className: 'btn-primary-pill', attrs: { href: '/bookings/' } }, [
            el('i', { className: 'fa-solid fa-bookmark' }), el('span', { text: ' Керування бронюваннями' })
        ]));
    }

    if (user.role === 'dispatcher') {
        actionsBox.append(el('a', { className: 'btn-secondary-pill', attrs: { href: '/saz-import/' } }, [
            el('i', { className: 'fa-solid fa-cloud-arrow-down' }), el('span', { text: ' Імпорт розкладу із САЗ' })
        ]));
    }

    actionsBox.append(el('a', { className: 'btn-secondary-pill', attrs: { href: '#' } }, [
        el('i', { className: 'fa-solid fa-magnifying-glass' }), el('span', { text: ' Знайти аудиторію' })
    ]));

    // 3. Завантаження найближчих занять
    try {
        const today = new Date().toISOString().slice(0, 10);
        const items = await UniSpaceApi.get(`schedule/?date_from=${today}&limit=3`);

        lessonsBox.replaceChildren();

        if (!items.length) {
            lessonsBox.append(el('div', { className: 'state-message' }, [
                el('i', { className: 'fa-regular fa-calendar-check' }),
                el('span', { text: 'На найближчий час занять немає.' })
            ]));
        } else {
            items.forEach(item => {
                const roomBadge = item.room
                    ? el('span', { className: 'badge badge-room' }, [
                        el('i', { className: 'fa-solid fa-door-open' }),
                        el('span', { text: `${item.room.number} (корпус ${item.room.building})` })
                      ])
                    : el('span', { className: 'badge badge-none', text: 'Без аудиторії' });

                const changedBadge = item.room_changed
                    ? el('span', { className: 'badge badge-changed', text: 'Змінено' })
                    : null;

                // Форматуємо дату заняття (короткий формат)
                const itemDateObj = new Date(item.date);
                let dateStr = new Intl.DateTimeFormat('uk-UA', { weekday: 'short', day: 'numeric', month: 'short' }).format(itemDateObj);
                dateStr = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);

                const card = el('div', { className: 'lesson-card' }, [
                    // ВИПРАВЛЕНО ТУТ: Використання `div` та `attrs: { style: ... }` для правильного відображення
                    el('div', {
                        className: 'lesson-time',
                        attrs: { style: 'display: flex; flex-direction: column; gap: 4px; min-width: 100px;' }
                    }, [
                        el('div', { text: dateStr, attrs: { style: 'font-size: 0.85rem; color: var(--text-muted); font-weight: 500;' } }),
                        el('div', { text: `${item.start_time.slice(0,5)}–${item.end_time.slice(0,5)}`, attrs: { style: 'font-size: 1.05rem; color: var(--text-main); font-weight: 700;' } })
                    ]),

                    // Блок інформації про предмет
                    el('div', { attrs: { style: 'flex-grow: 1;' } }, [
                        el('div', { className: 'lesson-subject', text: item.subject }),
                        el('div', { className: 'lesson-meta' }, [
                            el('span', { text: item.group }),
                            el('span', { text: item.teacher }),
                            roomBadge,
                            changedBadge
                        ])
                    ])
                ]);
                lessonsBox.append(card);
            });
        }

        // 4. Логіка інформаційної плашки
        if (user.role === 'student' || user.role === 'teacher' || user.role === 'dispatcher') {
            const banner = document.getElementById('student-summary-banner');
            const countEl = document.getElementById('summary-lessons-count');
            const syncEl = document.getElementById('summary-sync-time');

            const todayItems = items.filter(i => i.date === today);
            const count = todayItems.length;

            let lessonWord = 'пар';
            if (count === 1) lessonWord = 'пара';
            else if (count > 1 && count < 5) lessonWord = 'пари';

            countEl.textContent = count === 0
                ? 'Сьогодні у вас немає занять.'
                : `Сьогодні у вас ${count} ${lessonWord}.`;

            try {
                const logs = await UniSpaceApi.get('sync-logs/?limit=1');
                const lastLog = logs.find(log => log.status === 'success');

                if (lastLog) {
                    const syncDate = new Date(lastLog.started_at);
                    syncEl.textContent = new Intl.DateTimeFormat('uk-UA', {
                        day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'
                    }).format(syncDate);
                } else {
                    syncEl.textContent = 'ще не проводилось';
                }
            } catch (error) {
                syncEl.textContent = 'невідомо';
                console.warn('Не вдалося отримати час синхронізації:', error);
            }

            banner.hidden = false;
        }

    } catch (error) {
        lessonsBox.replaceChildren(el('div', { className: 'notice notice-error', text: UniSpaceApi.describeError(error) }));
    }
});
