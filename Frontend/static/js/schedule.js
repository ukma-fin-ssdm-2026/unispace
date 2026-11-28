/**
 * Логіка сторінки розкладу занять (GET /api/v1/schedule/ та GET /api/v1/groups/).
 * Використовує UniSpaceApi, el(), formatGroupName() та formatSubjectName() із api.js,
 * а також initDatePicker() та setPickerDate() із datepicker.js.
 * Примітка щодо використання ШІ: скрипт згенеровано ШІ.
 */

document.addEventListener('unispace:user', (event) => {
    const currentUser = event.detail;
    const scheduleListEl = document.getElementById('schedule-list');
    const noticeEl = document.getElementById('schedule-notice');
    const dateFromInput = document.getElementById('filter-date-from');
    const dateToInput = document.getElementById('filter-date-to');

    const dropdownEl = document.getElementById('group-dropdown');
    const groupTriggerBtn = document.getElementById('filter-group-trigger');
    const groupMenuEl = document.getElementById('filter-group-menu');
    const groupOptionsEl = document.getElementById('filter-group-options');
    const groupLabelEl = document.getElementById('filter-group-label');
    const groupIdInput = document.getElementById('filter-group-id');

    const prevWeekBtn = document.getElementById('btn-prev-week');
    const currentWeekBtn = document.getElementById('btn-current-week');
    const nextWeekBtn = document.getElementById('btn-next-week');
    const resetFiltersBtn = document.getElementById('btn-reset-filters');

    if (!scheduleListEl) return;

    const PAGE_SIZE = 100;
    const MAX_SINGLE_PAGE_DAYS = 7;
    const MS_PER_DAY = 24 * 60 * 60 * 1000;

    let scheduleItems = [];
    let hasMoreItems = false;
    let isLoadingMore = false;

    function formatIsoDate(dateObj) {
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function getWeekRange(baseDate) {
        const start = new Date(baseDate);
        const dayOfWeek = start.getDay();
        const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
        start.setDate(start.getDate() + diffToMonday);

        const end = new Date(start);
        end.setDate(start.getDate() + 6);

        return {
            dateFrom: formatIsoDate(start),
            dateTo: formatIsoDate(end)
        };
    }

    function setWeekRange(baseDate) {
        const { dateFrom, dateTo } = getWeekRange(baseDate);
        setPickerDate(dateFromInput, dateFrom);
        setPickerDate(dateToInput, dateTo);
    }

   function shiftCurrentRange(daysOffset) {
        const baseDate = dateFromInput.value ? new Date(`${dateFromInput.value}T00:00:00`) : new Date();
        baseDate.setDate(baseDate.getDate() + daysOffset);
        setWeekRange(baseDate);
        void loadSchedule();
    }

    function isLongerThanWeek() {
        if (!dateFromInput.value || !dateToInput.value) return true;
        const fromDate = new Date(`${dateFromInput.value}T00:00:00`);
        const toDate = new Date(`${dateToInput.value}T00:00:00`);
        if (Number.isNaN(fromDate.getTime()) || Number.isNaN(toDate.getTime())) return false;
        const diffDays = Math.round((toDate - fromDate) / MS_PER_DAY) + 1;
        return diffDays > MAX_SINGLE_PAGE_DAYS;
    }

    function formatDayHeading(isoDate) {
        const dateObj = new Date(`${isoDate}T00:00:00`);
        const formatted = new Intl.DateTimeFormat('uk-UA', {
            weekday: 'long',
            day: 'numeric',
            month: 'long'
        }).format(dateObj);
        return formatted.charAt(0).toUpperCase() + formatted.slice(1);
    }

    function showNotice(message, type = 'error') {
        noticeEl.hidden = false;
        noticeEl.replaceChildren(el('div', { className: `notice notice-${type}`, text: message }));
    }

    function clearNotice() {
        noticeEl.hidden = true;
        noticeEl.replaceChildren();
    }

    function isDropdownOpen() {
        return Boolean(dropdownEl && groupMenuEl && !groupMenuEl.hidden);
    }

    function openDropdown() {
        if (!dropdownEl || !groupMenuEl || !groupTriggerBtn) return;
        groupMenuEl.hidden = false;
        dropdownEl.classList.add('is-open');
        groupTriggerBtn.setAttribute('aria-expanded', 'true');
    }

    function closeDropdown() {
        if (!dropdownEl || !groupMenuEl || !groupTriggerBtn) return;
        groupMenuEl.hidden = true;
        dropdownEl.classList.remove('is-open');
        groupTriggerBtn.setAttribute('aria-expanded', 'false');
    }

    function syncSelectedOptionStyles() {
        if (!groupOptionsEl) return;
        const selectedId = groupIdInput ? groupIdInput.value : '';
        groupOptionsEl.querySelectorAll('.group-option-item').forEach((btn) => {
            const isSelected = btn.dataset.groupId === selectedId;
            btn.classList.toggle('is-selected', isSelected);
            btn.setAttribute('aria-selected', String(isSelected));
            const icon = btn.querySelector('.group-option-check');
            if (icon) {
                icon.style.visibility = isSelected ? 'visible' : 'hidden';
            }
        });
    }

    function selectGroup(groupId, label, shouldReload = true) {
        if (groupIdInput) groupIdInput.value = groupId;
        if (groupLabelEl) groupLabelEl.textContent = label;
        syncSelectedOptionStyles();
        closeDropdown();
        if (shouldReload) {
            void loadSchedule();
        }
    }

    function createOptionButton({ id, label, fullName, isAll = false }) {
        const isSelected = (groupIdInput ? groupIdInput.value : '') === id;
        const btn = el('button', {
            className: `group-option-item${isAll ? ' group-option-item--all' : ''}${isSelected ? ' is-selected' : ''}`,
            attrs: {
                type: 'button',
                role: 'option',
                'aria-selected': String(isSelected),
                ...(fullName ? { title: fullName } : {})
            }
        }, [
            el('span', { text: label }),
            el('i', {
                className: 'fa-solid fa-check group-option-check',
                attrs: {
                    'aria-hidden': 'true',
                    style: `visibility: ${isSelected ? 'visible' : 'hidden'}`
                }
            })
        ]);
        btn.dataset.groupId = id;
        btn.addEventListener('click', () => selectGroup(id, label, true));
        return btn;
    }

    async function loadGroups() {
        if (!groupOptionsEl || currentUser.role !== 'dispatcher') return;

        try {
            const groups = await UniSpaceApi.get('groups/');
            const fragment = document.createDocumentFragment();
            fragment.append(createOptionButton({ id: '', label: 'Усі групи', isAll: true }));

            const grouped = new Map();
            groups.forEach((group) => {
                const shortName = formatGroupName(group.name);
                const category = shortName.split(/[,\s(]/)[0] || 'Інші';
                if (!grouped.has(category)) {
                    grouped.set(category, []);
                }
                grouped.get(category).push({ id: group.id, label: shortName, fullName: group.name });
            });

            grouped.forEach((items, category) => {
                fragment.append(el('div', { className: 'group-option-heading', text: category }));
                items.forEach((item) => {
                    fragment.append(createOptionButton({ ...item, isAll: false }));
                });
            });

            groupOptionsEl.replaceChildren(fragment);
        } catch (error) {
            showNotice(`Не вдалося завантажити список груп: ${UniSpaceApi.describeError(error)}`, 'error');
        }
    }

    function buildLessonCard(lesson) {
        const roomBadge = lesson.room
            ? el('span', { className: 'badge badge-room' }, [
                el('i', { className: 'fa-solid fa-door-open' }),
                el('span', { text: `${lesson.room.number} (корпус ${lesson.room.building})` })
            ])
            : el('span', { className: 'badge badge-none', text: 'Без аудиторії' });

        const changedBadge = lesson.room_changed
            ? el('span', { className: 'badge badge-changed', text: 'Змінено' })
            : null;

        const actionsEl = el('div', { className: 'lesson-actions' });
        const canManage = currentUser.role === 'teacher' || currentUser.role === 'dispatcher';
        if (canManage && lesson.booking_id) {
            actionsEl.append(
                el('a', {
                    className: 'btn btn-outline',
                    attrs: { href: '/bookings/' }
                }, [
                    el('i', { className: 'fa-solid fa-arrow-right-arrow-left' }),
                    el('span', { text: 'Керувати' })
                ])
            );
        }

        const cardClass = lesson.room_changed ? 'lesson-card is-changed' : 'lesson-card';

        return el('div', { className: cardClass }, [
            el('div', {
                className: 'lesson-time',
                text: `${lesson.start_time.slice(0, 5)}–${lesson.end_time.slice(0, 5)}`
            }),
            el('div', {}, [
                el('div', {
                    className: 'lesson-subject',
                    text: formatSubjectName(lesson.subject)
                }),
                el('div', { className: 'lesson-meta' }, [
                    el('span', { className: 'lesson-group', attrs: { title: lesson.group } }, [
                        el('i', { className: 'fa-solid fa-users' }),
                        el('span', { text: formatGroupName(lesson.group) })
                    ]),
                    el('span', { className: 'lesson-teacher' }, [
                        el('i', { className: 'fa-solid fa-chalkboard-user' }),
                        el('span', { text: lesson.teacher })
                    ]),
                    roomBadge,
                    changedBadge
                ])
            ]),
            actionsEl
        ]);
    }

    function buildLoadMoreButton() {
        if (!hasMoreItems) return null;

        const btn = el('button', {
            className: 'btn btn-outline',
            text: isLoadingMore ? 'Завантаження…' : 'Завантажити ще',
            attrs: {
                type: 'button',
                id: 'btn-load-more',
                ...(isLoadingMore ? { disabled: 'disabled' } : {})
            }
        });

        btn.addEventListener('click', () => {
            if (!isLoadingMore) {
                void loadSchedule({ append: true });
            }
        });

        return el('div', { className: 'load-more-wrap' }, [btn]);
    }

    function renderSchedule(items) {
        scheduleListEl.replaceChildren();

        if (!items.length) {
            scheduleListEl.append(
                el('div', { className: 'panel state-message' }, [
                    el('i', { className: 'fa-regular fa-calendar-xmark' }),
                    el('span', { text: 'За обраний період занять не знайдено.' })
                ])
            );
            return;
        }

        const lessonsByDate = new Map();
        items.forEach((lesson) => {
            if (!lessonsByDate.has(lesson.date)) {
                lessonsByDate.set(lesson.date, []);
            }
            lessonsByDate.get(lesson.date).push(lesson);
        });

        lessonsByDate.forEach((dayLessons, isoDate) => {
            const groupEl = el('div', { className: 'day-group' }, [
                el('h2', { className: 'day-title', text: formatDayHeading(isoDate) }),
                ...dayLessons.map(buildLessonCard)
            ]);
            scheduleListEl.append(groupEl);
        });

        const loadMoreEl = buildLoadMoreButton();
        if (loadMoreEl) {
            scheduleListEl.append(loadMoreEl);
        }
    }

    async function loadSchedule({ append = false } = {}) {
        if (append && isLoadingMore) return;

        clearNotice();

        if (!append) {
            scheduleItems = [];
            hasMoreItems = false;
            scheduleListEl.replaceChildren(
                el('div', { className: 'state-message' }, [
                    el('i', { className: 'fa-solid fa-spinner fa-spin' }),
                    el('span', { text: 'Завантаження занять…' })
                ])
            );
        } else {
            isLoadingMore = true;
            renderSchedule(scheduleItems);
        }

        const usePagination = isLongerThanWeek();
        const params = new URLSearchParams({
            limit: String(PAGE_SIZE),
            offset: String(append ? scheduleItems.length : 0)
        });

        if (dateFromInput.value) params.set('date_from', dateFromInput.value);
        if (dateToInput.value) params.set('date_to', dateToInput.value);
        if (currentUser.role === 'dispatcher' && groupIdInput && groupIdInput.value) {
            params.set('group_id', groupIdInput.value);
        }

        try {
            const batch = await UniSpaceApi.get(`schedule/?${params.toString()}`);
            const rows = Array.isArray(batch) ? batch : (batch?.items || []);

            if (usePagination) {
                hasMoreItems = Array.isArray(batch)
                    ? rows.length === PAGE_SIZE
                    : Boolean(batch?.has_more);
            } else {
                hasMoreItems = false;
            }

            scheduleItems = append ? scheduleItems.concat(rows) : rows;
            renderSchedule(scheduleItems);
        } catch (error) {
            if (!append) scheduleListEl.replaceChildren();
            showNotice(UniSpaceApi.describeError(error), 'error');
        } finally {
            isLoadingMore = false;
            if (append) {
                renderSchedule(scheduleItems);
            }
        }
    }

    initDatePicker(dateFromInput, {
        onChange(selectedDates) {
            if (selectedDates[0] && dateToInput._flatpickr) {
                const currentTo = dateToInput._flatpickr.selectedDates[0];
                if (!currentTo || currentTo < selectedDates[0]) {
                    const nextWeekEnd = new Date(selectedDates[0]);
                    nextWeekEnd.setDate(nextWeekEnd.getDate() + 6);
                    dateToInput._flatpickr.setDate(nextWeekEnd, false);
                }
            }
            dateFromInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });
    initDatePicker(dateToInput);

    dateFromInput.addEventListener('change', () => {
        void loadSchedule();
    });
    dateToInput.addEventListener('change', () => {
        void loadSchedule();
    });

    if (groupTriggerBtn) {
        groupTriggerBtn.addEventListener('click', (clickEvent) => {
            clickEvent.stopPropagation();
            if (isDropdownOpen()) {
                closeDropdown();
            } else {
                openDropdown();
            }
        });
    }

    document.addEventListener('click', (clickEvent) => {
        if (isDropdownOpen() && dropdownEl && !dropdownEl.contains(clickEvent.target)) {
            closeDropdown();
        }
    });

    document.addEventListener('keydown', (keyEvent) => {
        if (keyEvent.key === 'Escape' && isDropdownOpen()) {
            closeDropdown();
            groupTriggerBtn?.focus();
        }
    });

    prevWeekBtn.addEventListener('click', () => shiftCurrentRange(-7));
    nextWeekBtn.addEventListener('click', () => shiftCurrentRange(7));
    currentWeekBtn.addEventListener('click', () => {
        setWeekRange(new Date());
        void loadSchedule();
    });

    resetFiltersBtn.addEventListener('click', () => {
        selectGroup('', 'Усі групи', false);
        setWeekRange(new Date());
        void loadSchedule();
    });

    setWeekRange(new Date());
    void loadGroups();
    void loadSchedule();
});
