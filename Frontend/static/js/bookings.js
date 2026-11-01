/*
 * «Мої бронювання»: найближчі заняття викладача (диспетчер бачить усі) з GET /schedule/,
 * підбір іншої аудиторії (GET /bookings/{id}/alternatives/, FR-010: спершу свій корпус, потім розширення),
 * перенесення (POST /bookings/{id}/change/) і скасування (DELETE /bookings/{id}/).
 *
 * Примітка щодо використання ШІ: скрипт згенеровано ШІ (Claude).
 */
document.addEventListener('unispace:user', (event) => {
    const lessonsBox = document.getElementById('lessons');
    const pageNotice = document.getElementById('page-notice');

    if (event.detail.role === 'student') {
        lessonsBox.replaceChildren(el('div', { className: 'state-message' }, [
            el('i', { className: 'fa-solid fa-lock' }),
            el('span', { text: 'Ця сторінка для викладачів і диспетчерів. Свій розклад дивіться в розділі «Розклад».' }),
        ]));
        return;
    }

    const changeModal = document.getElementById('change-modal');
    const roomList = document.getElementById('room-list');
    const changeNotice = document.getElementById('change-notice');
    const expandButton = document.getElementById('btn-expand');
    const confirmChange = document.getElementById('btn-change-confirm');
    const reasonInput = document.getElementById('change-reason');

    const cancelModal = document.getElementById('cancel-modal');
    const confirmCancel = document.getElementById('btn-cancel-confirm');

    let current = null; // заняття, з яким працює відкрите вікно
    let selectedRoomId = null;

    const weekdayFormat = new Intl.DateTimeFormat('uk-UA', { weekday: 'long', day: 'numeric', month: 'long' });

    function showNotice(box, kind, text) {
        box.hidden = false;
        box.className = `notice notice-${kind}`;
        box.textContent = text;
    }

    function hideNotice(box) {
        box.hidden = true;
        box.textContent = '';
    }

    function roomLabel(room) {
        return room ? `${room.number} (корпус ${room.building})` : 'без аудиторії';
    }

    function shortTime(value) {
        return value.slice(0, 5);
    }

    function today() {
        return new Date().toISOString().slice(0, 10);
    }

    // --- Список занять ---

    function lessonCard(item) {
        const roomBadge = item.room
            ? el('span', { className: 'badge badge-room' }, [el('i', { className: 'fa-solid fa-door-open' }), el('span', { text: roomLabel(item.room) })])
            : el('span', { className: 'badge badge-none', text: 'Без аудиторії' });
        const changedBadge = item.room_changed
            ? el('span', { className: 'badge badge-changed', text: 'Змінено' })
            : null;

        const actions = el('div', { className: 'lesson-actions' });
        if (item.booking_id) {
            const changeButton = el('button', { className: 'btn btn-outline' }, [
                el('i', { className: 'fa-solid fa-right-left' }), el('span', { text: 'Інша аудиторія' }),
            ]);
            changeButton.addEventListener('click', () => openChange(item));
            const cancelButton = el('button', { className: 'btn btn-ghost-danger' }, [
                el('i', { className: 'fa-solid fa-xmark' }), el('span', { text: 'Скасувати' }),
            ]);
            cancelButton.addEventListener('click', () => openCancel(item));
            actions.append(changeButton, cancelButton);
        }

        return el('div', { className: 'lesson-card' }, [
            el('div', { className: 'lesson-time', text: `${shortTime(item.start_time)}–${shortTime(item.end_time)}` }),
            el('div', {}, [
                el('div', { className: 'lesson-subject', text: item.subject }),
                el('div', { className: 'lesson-meta' }, [
                    el('span', { text: item.group }),
                    el('span', { text: item.teacher }),
                    roomBadge,
                    changedBadge,
                ]),
            ]),
            actions,
        ]);
    }

    async function loadLessons() {
        hideNotice(pageNotice);
        try {
            const items = await UniSpaceApi.get(`schedule/?date_from=${today()}&limit=100`);
            lessonsBox.replaceChildren();
            if (!items.length) {
                lessonsBox.append(el('div', { className: 'state-message' }, [
                    el('i', { className: 'fa-regular fa-calendar' }),
                    el('span', { text: 'Найближчих занять немає.' }),
                ]));
                return;
            }
            const byDate = new Map();
            items.forEach((item) => {
                if (!byDate.has(item.date)) byDate.set(item.date, []);
                byDate.get(item.date).push(item);
            });
            byDate.forEach((dayItems, date) => {
                const title = weekdayFormat.format(new Date(`${date}T00:00:00`));
                lessonsBox.append(el('section', { className: 'day-group' }, [
                    el('h2', { className: 'day-title', text: title }),
                    ...dayItems.map(lessonCard),
                ]));
            });
        } catch (error) {
            lessonsBox.replaceChildren();
            showNotice(pageNotice, 'error', `Не вдалося завантажити заняття: ${UniSpaceApi.describeError(error)}`);
        }
    }

    // --- Підбір і перенесення ---

    function setModal(modal, open) {
        modal.classList.toggle('active', open);
    }

    function renderRooms(result) {
        roomList.replaceChildren();
        selectedRoomId = null;
        confirmChange.disabled = true;

        if (result.message) {
            showNotice(changeNotice, 'info', result.message);
        } else {
            hideNotice(changeNotice);
        }
        // Пропонуємо розширити пошук, доки ще шукали лише в одному корпусі
        expandButton.hidden = result.expanded;

        result.rooms.forEach((room) => {
            const features = [`${room.capacity} місць`];
            if (room.projector_working) features.push('проєктор');
            if (room.has_computers) features.push("комп'ютери");
            const option = el('div', { className: 'room-option', attrs: { tabindex: '0', role: 'button' } }, [
                el('div', {}, [
                    el('div', { className: 'room-option-title', text: roomLabel(room) }),
                    el('div', { className: 'room-option-meta' }, features.map((f) => el('span', { text: f }))),
                ]),
                el('i', { className: 'fa-regular fa-circle-check' }),
            ]);
            const select = () => {
                roomList.querySelectorAll('.room-option').forEach((node) => node.classList.remove('selected'));
                option.classList.add('selected');
                selectedRoomId = room.id;
                confirmChange.disabled = false;
            };
            option.addEventListener('click', select);
            option.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') select();
            });
            roomList.append(option);
        });
    }

    async function loadAlternatives(expand) {
        roomList.replaceChildren(el('div', { className: 'state-message', text: 'Шукаємо вільні аудиторії…' }));
        try {
            const query = expand ? '?expand=true' : '';
            renderRooms(await UniSpaceApi.get(`bookings/${current.booking_id}/alternatives/${query}`));
        } catch (error) {
            roomList.replaceChildren();
            showNotice(changeNotice, 'error', UniSpaceApi.describeError(error));
        }
    }

    function openChange(item) {
        current = item;
        reasonInput.value = '';
        document.getElementById('change-lesson').textContent =
            `${item.subject} · ${item.date} ${shortTime(item.start_time)}–${shortTime(item.end_time)} · зараз: ${roomLabel(item.room)}`;
        setModal(changeModal, true);
        void loadAlternatives(false);
    }

    expandButton.addEventListener('click', () => {
        void loadAlternatives(true);
    });
    document.getElementById('btn-change-cancel').addEventListener('click', () => setModal(changeModal, false));

    confirmChange.addEventListener('click', async () => {
        confirmChange.disabled = true;
        try {
            await UniSpaceApi.post(`bookings/${current.booking_id}/change/`, {
                json: { room_id: selectedRoomId, reason: reasonInput.value.trim() },
            });
            setModal(changeModal, false);
            showNotice(pageNotice, 'success', `Заняття «${current.subject}» перенесено. Групу сповіщено.`);
            void loadLessons();
        } catch (error) {
            // 409: аудиторію щойно зайняли - оновлюємо список варіантів
            showNotice(changeNotice, 'error', UniSpaceApi.describeError(error));
            if (error.status === 409) void loadAlternatives(expandButton.hidden);
        }
    });

    // --- Скасування ---

    function openCancel(item) {
        current = item;
        document.getElementById('cancel-lesson').textContent =
            `${item.subject}, ${item.date} о ${shortTime(item.start_time)} (${roomLabel(item.room)}). Аудиторія звільниться.`;
        setModal(cancelModal, true);
    }

    document.getElementById('btn-cancel-back').addEventListener('click', () => setModal(cancelModal, false));
    confirmCancel.addEventListener('click', async () => {
        confirmCancel.disabled = true;
        try {
            await UniSpaceApi.del(`bookings/${current.booking_id}/`);
            setModal(cancelModal, false);
            showNotice(pageNotice, 'success', `Бронювання «${current.subject}» скасовано.`);
            void loadLessons();
        } catch (error) {
            setModal(cancelModal, false);
            showNotice(pageNotice, 'error', `Не вдалося скасувати: ${UniSpaceApi.describeError(error)}`);
        } finally {
            confirmCancel.disabled = false;
        }
    });

    document.getElementById('btn-refresh').addEventListener('click', () => {
        void loadLessons();
    });
    void loadLessons();
});
