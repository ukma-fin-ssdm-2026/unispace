/**
 * Спільна ініціалізація Flatpickr та кастомного меню місяців для всіх сторінок.
 */

function attachCustomMonthMenu(instance) {
    const calendarEl = instance.calendarContainer;
    const nativeSelect = calendarEl?.querySelector('.flatpickr-monthDropdown-months');
    const currentMonthEl = calendarEl?.querySelector('.flatpickr-current-month');
    if (!calendarEl || !nativeSelect || !currentMonthEl) return;

    currentMonthEl.querySelector('.fp-custom-month')?.remove();
    calendarEl.querySelector('.fp-month-popover')?.remove();

    nativeSelect.classList.add('fp-native-month-hidden');

    const monthBtn = el('button', {
        className: 'fp-custom-month',
        attrs: { type: 'button', 'aria-expanded': 'false' }
    }, [
        el('span', { className: 'fp-custom-month-label' }),
        el('i', { className: 'fa-solid fa-chevron-down', attrs: { 'aria-hidden': 'true' } })
    ]);

    const popoverEl = el('div', { className: 'fp-month-popover', attrs: { hidden: '' } });

    const syncLabel = () => {
        const selectedOpt = nativeSelect.options[nativeSelect.selectedIndex];
        const labelEl = monthBtn.querySelector('.fp-custom-month-label');
        if (labelEl && selectedOpt) {
            labelEl.textContent = selectedOpt.textContent.trim();
        }
        popoverEl.querySelectorAll('.fp-month-item').forEach((itemBtn) => {
            itemBtn.classList.toggle('is-active', Number(itemBtn.dataset.monthIndex) === instance.currentMonth);
        });
    };

    const closePopover = () => {
        popoverEl.hidden = true;
        monthBtn.setAttribute('aria-expanded', 'false');
    };

    const togglePopover = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const willOpen = popoverEl.hidden;
        if (willOpen) {
            popoverEl.replaceChildren();
            Array.from(nativeSelect.options).forEach((opt, idx) => {
                const isActive = idx === instance.currentMonth;
                const itemBtn = el('button', {
                    className: `fp-month-item${isActive ? ' is-active' : ''}`,
                    text: opt.textContent.trim(),
                    attrs: { type: 'button' }
                });
                itemBtn.dataset.monthIndex = String(idx);
                itemBtn.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    instance.changeMonth(idx, false);
                    nativeSelect.value = String(idx);
                    nativeSelect.dispatchEvent(new Event('change'));
                    syncLabel();
                    closePopover();
                });
                popoverEl.append(itemBtn);
            });
            popoverEl.hidden = false;
            monthBtn.setAttribute('aria-expanded', 'true');
        } else {
            closePopover();
        }
    };

    monthBtn.addEventListener('click', togglePopover);
    document.addEventListener('click', (e) => {
        if (!popoverEl.hidden && !popoverEl.contains(e.target) && !monthBtn.contains(e.target)) {
            closePopover();
        }
    });

    currentMonthEl.prepend(monthBtn);
    calendarEl.append(popoverEl);

    const origRedraw = instance.redraw.bind(instance);
    instance.redraw = () => {
        origRedraw();
        syncLabel();
    };

    syncLabel();
}

function initDatePicker(inputEl, options = {}) {
    if (!inputEl || typeof flatpickr !== 'function') return null;

    if (inputEl._flatpickr) {
        inputEl._flatpickr.destroy();
    }

    const localeConfig = (flatpickr.l10ns && flatpickr.l10ns.uk)
        ? {
            ...flatpickr.l10ns.uk,
            firstDayOfWeek: 1
        }
        : { firstDayOfWeek: 1 };

    const instance = flatpickr(inputEl, {
        locale: localeConfig,
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'd.m.Y',
        allowInput: true,
        disableMobile: true,
        onChange(_selectedDates, _dateStr, fpInstance) {
            if (fpInstance.altInput && !fpInstance.input.value) {
                fpInstance.altInput.value = '';
            }
            inputEl.dispatchEvent(new Event('change', { bubbles: true }));
        },
        ...options
    });

    inputEl._flatpickr = instance;
    attachCustomMonthMenu(instance);
    return instance;
}

function setPickerDate(inputEl, isoDate) {
    if (!inputEl) return;
    if (inputEl._flatpickr) {
        inputEl._flatpickr.setDate(isoDate || '', false);
    } else {
        inputEl.value = isoDate || '';
    }
}
