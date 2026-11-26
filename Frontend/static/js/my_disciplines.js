/**
 * Логіка сторінки «Мої дисципліни» для студента.
 * Працює з GET /api/v1/disciplines/available/ та CRUD /api/v1/my-disciplines/.
 */

document.addEventListener('unispace:user', (event) => {
    const currentUser = event.detail;
    const noticeEl = document.getElementById('disciplines-notice');
    const addFormEl = document.getElementById('add-discipline-form');
    const searchInputEl = document.getElementById('discipline-search-input');
    const autocompleteWrapEl = document.getElementById('discipline-autocomplete');
    const suggestionsEl = document.getElementById('discipline-suggestions');
    const groupSelectEl = document.getElementById('discipline-group-select');
    const addButtonEl = document.getElementById('btn-add-discipline');
    const listContainerEl = document.getElementById('my-disciplines-list');

    const courseDropdownEl = document.getElementById('course-filter-dropdown');
    const courseTriggerBtn = document.getElementById('course-filter-trigger');
    const courseMenuEl = document.getElementById('course-filter-menu');
    const courseOptionsEl = document.getElementById('course-filter-options');
    const courseLabelEl = document.getElementById('course-filter-label');
    const courseValueInput = document.getElementById('course-filter-value');

    if (!listContainerEl) return;

    if (currentUser.role !== 'student') {
        listContainerEl.replaceChildren(
            el('div', { className: 'state-message' }, [
                el('i', { className: 'fa-solid fa-lock' }),
                el('span', { text: 'Ця сторінка доступна лише для студентів.' })
            ])
        );
        if (addFormEl) addFormEl.hidden = true;
        return;
    }

    let availableDisciplines = [];
    let selectedDisciplines = [];
    let activeDiscipline = null;

    function showNotice(message, type = 'error') {
        noticeEl.hidden = false;
        noticeEl.replaceChildren(el('div', { className: `notice notice-${type}`, text: message }));
    }

    function clearNotice() {
        noticeEl.hidden = true;
        noticeEl.replaceChildren();
    }

    function extractCourseLabel(groupName) {
        const shortName = formatGroupName(groupName || '');
        return shortName.split(',')[0].trim() || 'Інші';
    }

    function getSelectedSubjectsSet() {
        return new Set(selectedDisciplines.map((item) => item.subject.toLowerCase()));
    }

    function closeSuggestions() {
        suggestionsEl.hidden = true;
        searchInputEl.setAttribute('aria-expanded', 'false');
    }

    function isCourseFilterOpen() {
        return Boolean(courseDropdownEl && courseMenuEl && !courseMenuEl.hidden);
    }

    function openCourseFilter() {
        if (!courseDropdownEl || !courseMenuEl || !courseTriggerBtn) return;
        courseMenuEl.hidden = false;
        courseDropdownEl.classList.add('is-open');
        courseTriggerBtn.setAttribute('aria-expanded', 'true');
    }

    function closeCourseFilter() {
        if (!courseDropdownEl || !courseMenuEl || !courseTriggerBtn) return;
        courseMenuEl.hidden = true;
        courseDropdownEl.classList.remove('is-open');
        courseTriggerBtn.setAttribute('aria-expanded', 'false');
    }

    function closeAllRowDropdowns(exceptDropdown = null) {
        listContainerEl.querySelectorAll('.group-dropdown.is-open').forEach((dropdown) => {
            if (dropdown === exceptDropdown) return;
            dropdown.classList.remove('is-open');
            const menu = dropdown.querySelector('.group-dropdown-menu');
            const trigger = dropdown.querySelector('.group-dropdown-trigger');
            if (menu) menu.hidden = true;
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        });
    }

    function selectCourseFilter(courseValue, label) {
        if (courseValueInput) courseValueInput.value = courseValue;
        if (courseLabelEl) courseLabelEl.textContent = label;
        closeCourseFilter();
        populateCourseFilter();
        renderMyDisciplines();
    }

    function createCourseOptionButton({ value, label, isAll = false }) {
        const currentValue = courseValueInput ? courseValueInput.value : '';
        const isSelected = currentValue === value;
        const btn = el('button', {
            className: `group-option-item${isAll ? ' group-option-item--all' : ''}${isSelected ? ' is-selected' : ''}`,
            attrs: {
                type: 'button',
                role: 'option',
                'aria-selected': String(isSelected)
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
        btn.addEventListener('click', (clickEvent) => {
            clickEvent.stopPropagation();
            selectCourseFilter(value, label);
        });
        return btn;
    }

    function populateCourseFilter() {
        if (!courseDropdownEl || !courseOptionsEl) return;

        const courses = Array.from(
            new Set(selectedDisciplines.map((record) => extractCourseLabel(record.group?.name)))
        ).sort((first, second) => first.localeCompare(second, 'uk'));

        if (courses.length <= 1) {
            courseDropdownEl.hidden = true;
            if (courseValueInput) courseValueInput.value = '';
            if (courseLabelEl) courseLabelEl.textContent = 'Усі курси';
            return;
        }

        courseDropdownEl.hidden = false;
        if (courseValueInput && courseValueInput.value && !courses.includes(courseValueInput.value)) {
            courseValueInput.value = '';
            if (courseLabelEl) courseLabelEl.textContent = 'Усі курси';
        }

        const fragment = document.createDocumentFragment();
        fragment.append(createCourseOptionButton({ value: '', label: 'Усі курси', isAll: true }));
        courses.forEach((course) => {
            fragment.append(createCourseOptionButton({ value: course, label: course, isAll: false }));
        });
        courseOptionsEl.replaceChildren(fragment);
    }

    function resetGroupSelect(placeholderText = 'Спочатку оберіть дисципліну') {
        groupSelectEl.replaceChildren(el('option', { text: placeholderText, attrs: { value: '' } }));
        groupSelectEl.disabled = true;
        addButtonEl.disabled = true;
    }

    function populateGroupSelect(groups) {
        groupSelectEl.replaceChildren();
        groups.forEach((group) => {
            groupSelectEl.append(
                el('option', {
                    text: formatGroupName(group.name),
                    attrs: { value: group.id, title: group.name }
                })
            );
        });
        groupSelectEl.disabled = groups.length === 0;
        addButtonEl.disabled = groups.length === 0;
    }

    function selectAvailableDiscipline(discipline) {
        activeDiscipline = discipline;
        searchInputEl.value = discipline.subject;
        populateGroupSelect(discipline.groups);
        closeSuggestions();
    }

    function renderSuggestions(queryText) {
        const normalizedQuery = queryText.trim().toLowerCase();
        const alreadyAdded = getSelectedSubjectsSet();

        const matches = availableDisciplines
            .filter((item) => !normalizedQuery || item.subject.toLowerCase().includes(normalizedQuery))
            .slice(0, 30);

        suggestionsEl.replaceChildren();

        if (!matches.length) {
            suggestionsEl.append(el('div', { className: 'autocomplete-empty', text: 'Дисциплін не знайдено.' }));
        } else {
            matches.forEach((discipline) => {
                const isAdded = alreadyAdded.has(discipline.subject.toLowerCase());
                const optionBtn = el('button', {
                    className: 'autocomplete-item',
                    attrs: {
                        type: 'button',
                        role: 'option',
                        ...(isAdded ? { disabled: 'disabled' } : {})
                    }
                }, [
                    el('span', { text: discipline.subject }),
                    isAdded ? el('span', { className: 'autocomplete-tag', text: 'Вже додано' }) : null
                ]);

                if (!isAdded) {
                    optionBtn.addEventListener('click', (clickEvent) => {
                        clickEvent.stopPropagation();
                        selectAvailableDiscipline(discipline);
                    });
                }
                suggestionsEl.append(optionBtn);
            });
        }

        suggestionsEl.hidden = false;
        searchInputEl.setAttribute('aria-expanded', 'true');
    }

    function buildDisciplineRow(record) {
        const groups = record.available_groups?.length ? record.available_groups : [record.group];
        let currentGroupId = record.group.id;

        const labelEl = el('span', {
            className: 'group-dropdown-value',
            text: formatGroupName(record.group.name),
            attrs: { title: record.group.name }
        });

        const triggerBtn = el('button', {
            className: 'group-dropdown-trigger',
            attrs: {
                type: 'button',
                'aria-haspopup': 'listbox',
                'aria-expanded': 'false',
                'aria-label': `Група для ${record.subject}`
            }
        }, [
            labelEl,
            el('i', { className: 'fa-solid fa-chevron-down group-dropdown-chevron', attrs: { 'aria-hidden': 'true' } })
        ]);

        const optionsListEl = el('div', { className: 'group-dropdown-list', attrs: { role: 'listbox' } });
        const menuEl = el('div', { className: 'group-dropdown-menu', attrs: { hidden: 'hidden' } }, [optionsListEl]);
        const dropdownEl = el('div', { className: 'group-dropdown' }, [triggerBtn, menuEl]);

        function renderOptions() {
            optionsListEl.replaceChildren();
            groups.forEach((group) => {
                const isSelected = group.id === currentGroupId;
                const optionBtn = el('button', {
                    className: `group-option-item${isSelected ? ' is-selected' : ''}`,
                    attrs: {
                        type: 'button',
                        role: 'option',
                        'aria-selected': String(isSelected),
                        title: group.name
                    }
                }, [
                    el('span', { text: formatGroupName(group.name) }),
                    el('i', {
                        className: 'fa-solid fa-check group-option-check',
                        attrs: {
                            'aria-hidden': 'true',
                            style: `visibility: ${isSelected ? 'visible' : 'hidden'}`
                        }
                    })
                ]);

                optionBtn.addEventListener('click', (clickEvent) => {
                    clickEvent.stopPropagation();
                    dropdownEl.classList.remove('is-open');
                    menuEl.hidden = true;
                    triggerBtn.setAttribute('aria-expanded', 'false');

                    if (group.id === currentGroupId) return;
                    currentGroupId = group.id;
                    labelEl.textContent = formatGroupName(group.name);
                    labelEl.title = group.name;
                    renderOptions();
                    void handleUpdateGroup(record.id, group.id, triggerBtn);
                });

                optionsListEl.append(optionBtn);
            });
        }

        renderOptions();

        triggerBtn.addEventListener('click', (clickEvent) => {
            clickEvent.stopPropagation();
            const willOpen = menuEl.hidden;
            closeSuggestions();
            closeCourseFilter();
            closeAllRowDropdowns(dropdownEl);

            menuEl.hidden = !willOpen;
            dropdownEl.classList.toggle('is-open', willOpen);
            triggerBtn.setAttribute('aria-expanded', String(willOpen));
        });

        const deleteBtn = el('button', {
            className: 'btn btn-ghost-danger btn-icon-danger',
            attrs: { type: 'button', title: 'Видалити дисципліну', 'aria-label': `Видалити ${record.subject}` }
        }, [
            el('i', { className: 'fa-solid fa-trash-can' })
        ]);

        deleteBtn.addEventListener('click', () => {
            void handleDeleteDiscipline(record.id, deleteBtn);
        });

        return el('div', { className: 'discipline-row' }, [
            el('div', { className: 'discipline-name', text: record.subject }),
            dropdownEl,
            deleteBtn
        ]);
    }

    function renderMyDisciplines() {
        listContainerEl.replaceChildren();

        if (!selectedDisciplines.length) {
            listContainerEl.append(
                el('div', { className: 'state-message' }, [
                    el('i', { className: 'fa-solid fa-book-open' }),
                    el('span', { text: 'Ви ще не додали жодної дисципліни. Скористайтеся пошуком вище.' })
                ])
            );
            return;
        }

        const activeCourse = courseValueInput ? courseValueInput.value : '';
        const visibleDisciplines = activeCourse
            ? selectedDisciplines.filter((record) => extractCourseLabel(record.group?.name) === activeCourse)
            : selectedDisciplines;

        if (!visibleDisciplines.length) {
            listContainerEl.append(
                el('div', { className: 'state-message' }, [
                    el('i', { className: 'fa-solid fa-filter-circle-xmark' }),
                    el('span', { text: `Для курсу «${activeCourse}» дисциплін не знайдено.` })
                ])
            );
            return;
        }

        const wrapperEl = el('div', { className: 'discipline-list' }, visibleDisciplines.map(buildDisciplineRow));
        listContainerEl.append(wrapperEl);
    }

    async function loadInitialData() {
        clearNotice();
        try {
            const [available, mine] = await Promise.all([
                UniSpaceApi.get('disciplines/available/'),
                UniSpaceApi.get('my-disciplines/')
            ]);
            availableDisciplines = Array.isArray(available) ? available : [];
            selectedDisciplines = Array.isArray(mine) ? mine : [];
            populateCourseFilter();
            renderMyDisciplines();
        } catch (error) {
            listContainerEl.replaceChildren();
            showNotice(`Не вдалося завантажити дані: ${UniSpaceApi.describeError(error)}`, 'error');
        }
    }

    async function handleAddDiscipline(submitEvent) {
        submitEvent.preventDefault();
        clearNotice();

        if (!activeDiscipline || !groupSelectEl.value) return;

        addButtonEl.disabled = true;
        try {
            const created = await UniSpaceApi.post('my-disciplines/', {
                json: {
                    subject: activeDiscipline.subject,
                    group_id: groupSelectEl.value
                }
            });
            selectedDisciplines.push(created);
            selectedDisciplines.sort((first, second) => first.subject.localeCompare(second.subject, 'uk'));

            activeDiscipline = null;
            searchInputEl.value = '';
            resetGroupSelect();
            populateCourseFilter();
            renderMyDisciplines();
            showNotice(`Дисципліну «${created.subject}» додано.`, 'success');
        } catch (error) {
            addButtonEl.disabled = false;
            showNotice(UniSpaceApi.describeError(error), 'error');
        }
    }

    async function handleUpdateGroup(recordId, newGroupId, triggerBtn) {
        clearNotice();
        triggerBtn.disabled = true;
        try {
            const updated = await UniSpaceApi.patch(`my-disciplines/${recordId}/`, {
                json: { group_id: newGroupId }
            });
            selectedDisciplines = selectedDisciplines.map((item) => (item.id === recordId ? updated : item));
            populateCourseFilter();
            renderMyDisciplines();
            showNotice(`Групу для «${updated.subject}» оновлено.`, 'success');
        } catch (error) {
            showNotice(UniSpaceApi.describeError(error), 'error');
            renderMyDisciplines();
        } finally {
            triggerBtn.disabled = false;
        }
    }

    async function handleDeleteDiscipline(recordId, buttonEl) {
        clearNotice();
        buttonEl.disabled = true;
        try {
            await UniSpaceApi.del(`my-disciplines/${recordId}/`);
            selectedDisciplines = selectedDisciplines.filter((item) => item.id !== recordId);
            populateCourseFilter();
            renderMyDisciplines();
            showNotice('Дисципліну видалено зі списку.', 'info');
        } catch (error) {
            buttonEl.disabled = false;
            showNotice(UniSpaceApi.describeError(error), 'error');
        }
    }

    if (courseTriggerBtn) {
        courseTriggerBtn.addEventListener('click', (clickEvent) => {
            clickEvent.stopPropagation();
            if (isCourseFilterOpen()) {
                closeCourseFilter();
            } else {
                closeSuggestions();
                closeAllRowDropdowns();
                openCourseFilter();
            }
        });
    }

    searchInputEl.addEventListener('focus', () => {
        closeCourseFilter();
        closeAllRowDropdowns();
        renderSuggestions(searchInputEl.value);
    });

    searchInputEl.addEventListener('input', () => {
        if (activeDiscipline && searchInputEl.value !== activeDiscipline.subject) {
            activeDiscipline = null;
            resetGroupSelect();
        }
        renderSuggestions(searchInputEl.value);
    });

    document.addEventListener('click', (clickEvent) => {
        if (!suggestionsEl.hidden && !autocompleteWrapEl.contains(clickEvent.target)) {
            closeSuggestions();
        }
        if (isCourseFilterOpen() && courseDropdownEl && !courseDropdownEl.contains(clickEvent.target)) {
            closeCourseFilter();
        }
        closeAllRowDropdowns();
    });

    document.addEventListener('keydown', (keyEvent) => {
        if (keyEvent.key === 'Escape') {
            if (!suggestionsEl.hidden) {
                closeSuggestions();
            }
            if (isCourseFilterOpen()) {
                closeCourseFilter();
                courseTriggerBtn?.focus();
            }
            closeAllRowDropdowns();
        }
    });

    addFormEl.addEventListener('submit', (submitEvent) => {
        void handleAddDiscipline(submitEvent);
    });

    void loadInitialData();
});
