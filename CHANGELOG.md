# Changelog

Усі помітні зміни в цьому проєкті будуть документуватися в цьому файлі.

Формат базується на [Keep a Changelog](https://keepachangelog.com/uk/1.0.0/), 
а цей проєкт дотримується [Семантичного версіонування](https://semver.org/lang/uk/).

## [0.3.3](https://github.com/ukma-fin-ssdm-2026/unispace/compare/v0.3.2...v0.3.3) (2026-11-11)


### Documentation

* update TeamCharter with Lab09 roles and responsibilities ([#328](https://github.com/ukma-fin-ssdm-2026/unispace/issues/328)) ([a828582](https://github.com/ukma-fin-ssdm-2026/unispace/commit/a8285829120c8b0271ba70c2477f7ae6cfb7a66d))

## [0.3.2](https://github.com/ukma-fin-ssdm-2026/unispace/compare/v0.3.1...v0.3.2) (2026-11-11)


### Documentation

* update Lab09 reliability risk analysis ([c90a589](https://github.com/ukma-fin-ssdm-2026/unispace/commit/c90a5897e4a5097b16d92af3e695bef492f0dbcb))

## [0.3.1](https://github.com/ukma-fin-ssdm-2026/unispace/compare/v0.3.0...v0.3.1) (2026-11-10)


### Documentation

* add release-please automation info to readme ([53f8da9](https://github.com/ukma-fin-ssdm-2026/unispace/commit/53f8da95791dec75fce0e915d5be84a7533c85cd))

## [0.3.0](https://github.com/ukma-fin-ssdm-2026/unispace/compare/v0.2.2...v0.3.0) (2026-11-10)


### Features

* add ALLOW_DEV_LOGIN setting to allow dev login on production via environment variable ([4f11ec1](https://github.com/ukma-fin-ssdm-2026/unispace/commit/4f11ec18e09d5d53dfb959a9b66120d8e2683b01))

### Bug Fixes

* add timeouts, strict JSON and CSRF validation to api.js ([79d245b](https://github.com/ukma-fin-ssdm-2026/unispace/commit/79d245bc8f06bcf270c5e6aad78cae7cc38bce3b))
* close SyncLog as failed on unexpected import errors (REL-H07) ([939e271](https://github.com/ukma-fin-ssdm-2026/unispace/commit/939e271dc7014ec7b65b3a21284ba3d0d95f21b5))
* sync release version 0.2.2 in configs and changelog ([01cc379](https://github.com/ukma-fin-ssdm-2026/unispace/commit/01cc37970afab83695942b0b5298e6855953663d))
* update traceability script and exceptions for nested test folders ([314a98a](https://github.com/ukma-fin-ssdm-2026/unispace/commit/314a98a5022910f798eccf8a36ccc7128e98c52e))
* validate rowspan/colspan in SAZ parser (REL-H04) ([87c47bb](https://github.com/ukma-fin-ssdm-2026/unispace/commit/87c47bb330416b8e878ace4da3d6612a59fdcda1))

### Documentation

* add ALLOW_DEV_LOGIN environment variable to Render deployment instructions ([9ee1f88](https://github.com/ukma-fin-ssdm-2026/unispace/commit/9ee1f886816d29b56d9a9cb25e302ffc3b1ec150))
* add Lab08 video link to video_Trekurova.txt ([1fa314c](https://github.com/ukma-fin-ssdm-2026/unispace/commit/1fa314cd1de6c3aa01aa4ed04d0658ba7f89a083))
* add Lab09 reliability scavenger hunt ([433e185](https://github.com/ukma-fin-ssdm-2026/unispace/commit/433e1857459115d90e458486f8ea89a08cce9694))
* restructure README and add Lab 09 reliability files ([7ef4405](https://github.com/ukma-fin-ssdm-2026/unispace/commit/7ef44051724bef3fe9433d13ff753a069b5a0513))
* update test paths and pytest commands in README ([34e21bd](https://github.com/ukma-fin-ssdm-2026/unispace/commit/34e21bd205610861bb630fb6a5788b57db410907))

## [0.2.2] - 2026-11-05

### Changed
- Оновлено звіт `sonarcloud-report.md`: 
  - Додано детальні результати фінального регресійного прогону в `main` після злиття всіх цілей рефакторингу.
  - Додано зведену таблицю всіх виконаних рефакторингів (з авторами, техніками та посиланнями на коміти) та розгорнуту нотатку про верифікацію коду, згенерованого ШІ-агентом.
- Оновлено тестову документацію (`testing-strategy.md`, `test-plan.md`, `rtm.md`): зафіксовано зростання покриття коду до 95%, збільшення загальної кількості тестів до 344 та відображено покриття вимоги FR-004 новими характеризаційними тестами.

### Refactoring
- **Replace Magic Number with Constant:** винесено межі робочого дня ("08:00"/"20:00") у константи в `AvailableSlotsAPIView.get` (Ціль A1).
- **Extract Method:** винесено логіку обчислення зайнятих інтервалів з `AvailableSlotsAPIView.get` у виділений сервіс `services/available_slots.py` (Ціль A2).
- **Extract Method:** винесено логіку обчислення дати заняття та формування `source_key` з функції `import_schedule` у допоміжні функції в `services/saz_import.py` (Ціль B1).
- **Extract Method:** винесено блок `update_or_create` з підрахунком лічильників з `import_schedule` в окрему функцію `_upsert_lesson` (Ціль B2).
- **Extract Method:** замінено 11 однакових блоків перевірки `is_valid()` з поверненням помилки 400 на єдиний загальний хелпер у `views.py` (Ціль C).
- **Extract Method:** виділено допоміжні функції `_existing_file`, `_parse_semester_start`, `_read_page` та `_write_summary` з довгого методу `handle` команди `import_saz`.
- **Extract Method:** виділено спільну перевірку автентифікації та ролей у функцію `has_allowed_role` у `views.py` (для `IsTeacherOrDispatcher` та `IsDispatcher`).

## [0.2.1] - 2026-11-04

### Added
- **Security Testing:** додано вимірюваний тест `test_sec001_write_access.py` для перевірки вимоги SEC-001 (заборона створення та зміни бронювань для студентів і анонімів).
- **Characterization Testing:** додано 11 тестувальних сценаріїв у `test_import_saz_command.py` для фіксації поточної поведінки команди `import_saz` перед її рефакторингом (покриття підвищено з 0% до 100%).

### Changed
- Оновлено `TeamCharter.md`: затверджено нові ролі та обов'язки команди для Лабораторної роботи №8.
- Оновлено архітектурну документацію та вимоги: задокументовано перехід від автоматичної синхронізації до ручного імпорту розкладу САЗ диспетчером (оновлено `ADR-003`, UML-діаграми, `threat-model.md`, `traceability-matrix.md`, `requirements.md` та `README.md`).
- Оновлено звіт `sonarcloud-report.md`:
  - Задокументовано виправлення вразливостей CI/CD, що дозволило покращити Security Rating у SonarQube Cloud з C до A.
  - Додано комплексний аналіз безпеки (Security Analyst Role): проаналізовано знахідки SonarQube, залишкові ризики та встановлено traceability з моделлю загроз STRIDE (Lab 3) і статичним аналізом (Lab 5).
  - Додано секцію бонусів: зафіксовано налаштування SonarQube Quality Gate як обов'язкової перевірки для гілки `main`.
  - Додано бонус "Характеризаційні тести перед рефакторингом" для модуля `import_saz`.
- Оновлено тестову документацію (`test-plan.md`, `quality-attributes.md`, `rtm.md`, `testing-strategy.md`): відображено актуальний стан покриття вимог, додано посилання на новий вимірюваний тест SEC-001 та виправлено таблицю плану тестування.

## [0.2.0] - 2026-11-01

### Added (Новий функціонал)
- Додано email-сповіщення про зміну аудиторії.
- Додано можливість локального входу для розробки (dev-login).
- Реалізовано імпорт розкладу із САЗ та відповідний фронтенд.
- Додано перегляд попередніх занять (`feat/previous-lesson-view`).
- Реалізовано перегляд журналу аудиту (`feat: audit-log-view`).
- Додано логіку розрахунку доступних слотів для кімнат на основі активних бронювань.
- Додано команду для заповнення бази даних демо-даними та відповідні тести.
- Інтегровано фронтенд-логін з бекендом на Render.
- Додано код до `admin.py`.

### Changed & Refactored (Зміни та Рефакторинг)
- Оновлено конфігураційний файл pyproject.toml для фронтенду: зафіксовано версію 0.2.0.
- Оновлено README: додано посилання на файл CHANGELOG.md.
- **Refactoring**: Оновлено дизайн головної сторінки, додано розклад та швидкі дії.
- Забезпечено узгодженість документації для midterm.
- Оновлено документацію щодо конкурентності для реалізації PostgreSQL.
- Оновлено посилання на сторінку входу Web UI у README.
- Додано інструкції щодо локальної авторизації та демо-даних до README.
- Оновлено README з інструкціями щодо локального запуску та розгортання на Render.
- Оновлено документацію перед проміжним контролем (midterm).
- Оновлено `progress.md` для відображення інтеграції CRUD та Microsoft SSO.

### CI/CD & Tests (Налаштування та Тести)
- Написано тести для покриття граничних випадків та накладань доступних слотів.

## [0.1.1] - 2026-10-31

### Fixed (Виправлення)
- Виправлено збереження авторизації Microsoft на локальному хості URI редиректу.
- Виправлено відображення бічної панелі, скинуто вікно привітання та приховано логін розробника.
- Оновлено перевірку cookie CSRF у тестах авторизації Microsoft.
- Додано повернення помилки 409, коли PostgreSQL перериває конкурентне бронювання через дедлок.
- Налаштовано CORS та довірені джерела CSRF для інтеграції фронтенду.
- Виправлено область видимості альтернативних кімнат.
- Додано `gunicorn` до вимог фронтенду.
- Додано `whitenoise` та налаштовано статичний корінь для розгортання на Render.
- Виправлено статичний корінь фронтенду.

### CI/CD, Tests & Docs (Налаштування, Тести, Документація)
- **Refactoring**: Повернено `wsgi.py` до чистого стану та використано команду запуску для міграцій бази даних на Render.
- Додано автоматизовані міграції бази даних під час запуску WSGI на Render.
- Виключено згенеровані файли з аналізу SonarCloud.
- Додано індивідуальні посилання на відео для лабораторної 8 та презентації.
- Оновлено README з виправленнями для midterm та вимогами до лабораторної 8.
- Написано тести для покриття конфліктів конкурентного бронювання (REL-001).
- Створено початковий звіт аналізу SonarQube Cloud.
- Зафіксовано точні версії pip та залежностей для розробки в CI.
- Застосовано прапорець `--only-binary` до кроку встановлення.
- Зафіксовано pip та залежності розробки фронтенду в CI.
- Обмежено розгортання GitHub Pages лише для довірених робочих процесів.
- Видалено застарілі згадки про гілки та виправлено шлях до модуля mutmut.

## [0.1.0] - 2026-10-30

### Added
- Початковий стан проєкту до запровадження семантичного версіонування та початку роботи над спринтом якості.

> **Примітка щодо використання ШІ:** структурування та генерація тексту для журналу змін виконані за допомогою ШІ-асистента (Gemini) на основі історії комітів, PR та скриншотів. Результат перевірено та відредаговано людиною (Мельник Дар'я).
