/*
 * «Імпорт із САЗ» (диспетчер): POST /api/v1/sync/ (multipart: file, semester_start) і журнал GET /api/v1/sync-logs/.
 * Примітка щодо використання ШІ: скрипт згенеровано ШІ (Claude).
 */
document.addEventListener('unispace:user', (event) => {
    const form = document.getElementById('import-form');
    const importButton = document.getElementById('btn-import');
    const resultPanel = document.getElementById('result-panel');
    const resultNotice = document.getElementById('result-notice');
    const resultStats = document.getElementById('result-stats');
    const resultWarnings = document.getElementById('result-warnings');
    const logsBox = document.getElementById('sync-logs');

    if (event.detail.role !== 'dispatcher') {
        const notice = document.getElementById('access-notice');
        notice.hidden = false;
        notice.className = 'notice notice-error';
        notice.textContent = 'Імпорт розкладу доступний лише диспетчеру.';
        document.getElementById('import-panel').hidden = true;
        logsBox.closest('.panel').hidden = true;
        return;
    }

    const STATUS_LABELS = { success: 'Успішно', failed: 'Помилка', in_progress: 'Виконується' };
    const STATS = [
        ['lessons_created', 'нових занять'],
        ['lessons_updated', 'оновлено занять'],
        ['bookings_created', 'бронювань створено'],
        ['conflicts_created', 'конфліктів виявлено'],
        ['teachers_created', 'нових викладачів'],
        ['online_lessons', 'дистанційних занять'],
    ];
    const dateTime = new Intl.DateTimeFormat('uk-UA', { dateStyle: 'short', timeStyle: 'short' });

    function showResult(log) {
        resultPanel.hidden = false;
        resultStats.replaceChildren();
        resultWarnings.replaceChildren();

        if (log.status !== 'success') {
            resultNotice.className = 'notice notice-error';
            resultNotice.textContent = `Імпорт не вдався: ${log.error_message || 'невідома помилка'}. Попередні дані не змінено.`;
            return;
        }
        resultNotice.className = 'notice notice-success';
        resultNotice.textContent = 'Розклад імпортовано.';

        STATS.forEach(([key, label]) => {
            resultStats.append(el('div', { className: 'stat' }, [
                el('div', { className: 'stat-value', text: String(log.summary[key]) }),
                el('div', { className: 'stat-label', text: label }),
            ]));
        });
        if (log.summary.warnings.length) {
            resultWarnings.append(
                el('p', { text: `Попередження (${log.summary.warnings.length}):` }),
                el('ul', { className: 'warnings' }, log.summary.warnings.map((w) => el('li', { text: w }))),
            );
        }
    }

    async function loadLogs() {
        try {
            const logs = await UniSpaceApi.get('sync-logs/');
            if (!logs.length) {
                logsBox.replaceChildren(el('div', { className: 'state-message', text: 'Синхронізацій ще не було.' }));
                return;
            }
            const rows = logs.slice(0, 20).map((log) => el('tr', {}, [
                el('td', { text: dateTime.format(new Date(log.started_at)) }),
                el('td', {}, [el('span', { className: `status-${log.status}`, text: STATUS_LABELS[log.status] || log.status })]),
                el('td', { text: log.trigger === 'manual' ? 'Вручну' : 'За розкладом' }),
                el('td', { text: log.error_message || '—' }),
            ]));
            logsBox.replaceChildren(el('table', { className: 'data-table' }, [
                el('thead', {}, [el('tr', {}, ['Час', 'Статус', 'Запуск', 'Помилка'].map((h) => el('th', { text: h })))]),
                el('tbody', {}, rows),
            ]));
        } catch (error) {
            logsBox.replaceChildren(el('div', { className: 'notice notice-error', text: UniSpaceApi.describeError(error) }));
        }
    }

    form.addEventListener('submit', async (submitEvent) => {
        submitEvent.preventDefault();
        if (!form.reportValidity()) return;

        importButton.disabled = true;
        importButton.replaceChildren(el('i', { className: 'fa-solid fa-spinner fa-spin' }), el('span', { text: 'Імпортуємо…' }));
        try {
            showResult(await UniSpaceApi.post('sync/', { body: new FormData(form) }));
            form.reset();
        } catch (error) {
            resultPanel.hidden = false;
            resultStats.replaceChildren();
            resultWarnings.replaceChildren();
            resultNotice.className = 'notice notice-error';
            resultNotice.textContent = UniSpaceApi.describeError(error);
        } finally {
            importButton.disabled = false;
            importButton.replaceChildren(el('i', { className: 'fa-solid fa-file-import' }), el('span', { text: 'Імпортувати' }));
            loadLogs();
        }
    });

    loadLogs();
});
