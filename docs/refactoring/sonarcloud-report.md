# SonarQube Cloud Report Unispace

## Оцінки до рефакторингу

| Критерій       | Оцінка / Рейтинг | Показник / Кількість    |
|----------------|------------------|-------------------------|
| Code Smells    | A                | 0 запахів коду          |
| Maintainability| A                | 0 проблем               |
| Technical Debt | A                | 0 г                     |
| Duplications   | A                | 0.0% дубльованих рядків |
| Reliability    | A                | 0 проблем               |
| Security       | C                |12 вразливостей          |

## 3. Обрані критерії
 
1. **Code Smells**
2. **Technical Debt**
3. **Duplications**

Обґрунтування: це три метрики підтримуваності, які вимагає лабораторна 8. Усі три вже мали
найкращу оцінку (A / 0) до рефакторингу, тому в них нема що покращувати за метриками Sonar —
вони виступають як **контрольні**: рефакторинг не повинен їх погіршити.

## Аналіз проблем безпеки

| № | Проблема | Локація | Рівень небезпеки | План виправлення | Статус після рефакторингу |
|---|---|---|---|---|---|
| 1 | Make sure that no untrusted code is executed from a fork. | `.github/workflows/pages.yml` (L30) | **High** | Додати перевірку репозиторію та гілки (`if: github.repository == '...' && github.ref == 'refs/heads/main'`) або обмежити права токена `permissions`, щоб запобігти виконанню довільного коду з форків. | ✅ Виправлено |
| 2 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L65) | **Medium** | Зафіксувати точні версії залежностей бекенду за допомогою lock-файлу (`pip-compile` / `requirements.lock`) замість плаваючих версій. | ✅ Виправлено |
| 3 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L65) | **Medium** | Додати прапорець `--only-binary :all:` до команди `pip install`, щоб встановлювати виключно pre-built wheels і блокувати запуск сторонніх `setup.py`. | ✅ Виправлено |
| 4 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L68) | **Medium** | Зафіксувати точні версії для `requirements-dev.txt` у бекенді через lock-файл із хешами пакетів. | ✅ Виправлено |
| 5 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L68) | **Medium** | Заборонити збірку tarball-пакетів при встановленні dev-залежностей бекенду, додавши прапорець `--only-binary :all:`. | ✅ Виправлено |
| 6 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L195) | **Medium** | Створити та підключити окремий lock-файл із зафіксованими версіями для основного середовища фронтенду. | ✅ Виправлено |
| 7 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L195) | **Medium** | Використати `--only-binary :all:` під час встановлення продакшн-пакетів фронтенду для унеможливлення RCE через вразливі setup-скрипти. | ✅ Виправлено |
| 8 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L198) | **Medium** | Зафіксувати повне дерево транзитивних залежностей розробника для фронтенду (`requirements-dev.lock`). | ✅ Виправлено |
| 9 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L198) | **Medium** | Додати параметр `--only-binary :all:` при встановленні dev-інструментів фронтенду в CI-раннері. | ✅ Виправлено |
| 10 | Add integrity and crossorigin="anonymous" attributes to this element to enforce integrity checks. | `docs/api/index.html` (L7) | **Low** | Додати атрибути SRI (`integrity="sha384-..."` та `crossorigin="anonymous"`) до тегу підключення зовнішнього CSS/JS або завантажити ресурс локально. | 🚫 Файл виключено з аналізу, код не змінювався |
| 11 | Add integrity and crossorigin="anonymous" attributes to this element to enforce integrity checks. | `docs/api/index.html` (L14) | **Low** | Додати криптографічний хеш `integrity` та `crossorigin="anonymous"` для валідації цілісності завантажуваного CDN-файлу. | 🚫 Файл виключено з аналізу, код не змінювався |
| 12 | Add integrity and crossorigin="anonymous" attributes to this element to enforce integrity checks. | `docs/api/index.html` (L15) | **Low** | Захистити підключення третього зовнішнього ресурсу документації шляхом додавання перевірки SRI (`integrity` + `crossorigin="anonymous"`). | 🚫 Файл виключено з аналізу, код не змінювався |

## Метрики до та після
 
| Критерій | До | Після | Зміна |
|---|---|---|---|
| Security Rating | C (12 проблем: 1 High, 8 Medium, 3 Low) | A (0 проблем) | С -> А |
| Code Smells | A / 0 | A / 0 | - |
| Technical Debt | A / 0 г | A / 0 г | - |
| Duplications | A / 0.0% | A / 0.0% | - |
| Reliability | A / 0 | A / 0 | - |

> **Примітка щодо використання ШІ:** ШІ-агент (Gemini) використовувався для аналізу проблем безпеки та створення плану виправлень. Результати перевірено людиною (Тимохина Ксенія).

## Результат регресійного тестування

Відповідальна: Ольга Михайлик (інженерка з тестування). Тести запускалися локально командою `python -m pytest -q` у `Backend/` на PostgreSQL 16 у Docker; ті самі тести проганяє CI на кожен PR.

### Базовий прогін (до рефакторингу)

| Гілка / коміт | Команда | Результат |
|---|---|---|
| `main`, `1f0ddfa` | `python -m pytest -q` | **327 passed** |

### Прогони за цілями

| Ціль | Гілка | Цільові тести | До | Після | Повний набір після |
|---|---|---|---|---|---|
| A (A1 + A2) | `refactor/available-slots` | `test_available_slots.py` | 16 passed | 16 passed | спершу збій (див. нижче), після виправлення **327 passed** |
| B (B1 + B2) | `refactor/import-schedule` | `test_saz_import.py`, `test_saz_parser.py` | 37 passed | 37 passed | **327 passed** |
| C | _ще не створено_ | `test_bookings_crud.py`, `test_room_alternatives.py`, `test_booking_previous_lesson.py`, `test_views.py` | — | — | — |

### Виявлений збій і його причина (ціль A)

* **Симптом:** на гілці `refactor/available-slots` повний прогін переривався на етапі збору тестів: `ERROR api/tests/test_saz_import.py - FileNotFoundError: ... fixtures/saz/schedule_preview.html`. Без цього модуля результат був `309 passed, 4 errors`; усі 4 помилки в `test_saz_parser.py` мали ту саму причину.
* **Причина:** коміт `0b90eda` («[REFACTOR] Extract Method: get_occupied_intervals з AvailableSlotsAPIView.get», виконаний з ШІ-агентом) разом із рефакторингом видалив файли, не пов'язані зі зміною: анонімізовану фікстуру САЗ `Backend/api/tests/fixtures/saz/schedule_preview.html`, а також `Backend/htmlcov/`, `Backend/coverage.json` і `Backend/test-results.xml`.
* **Глибша причина:** з коміту `17baf1e` (01.11.2026) `.gitignore` містить правило `**/*.html`, тож git вважає фікстуру САЗ (і будь-які нові HTML-шаблони фронтенду) ігнорованими файлами. Під час прибирання ігнорованих звітів покриття фікстура потрапила під те саме правило й була видалена з репозиторію.
* **Чи зламав рефакторинг поведінку:** ні. Тести самого рефакторингу (`test_available_slots.py`, 16 passed) і решта набору, що не залежить від фікстури (309 passed), зелені.
* **Виправлення:** фікстуру відновлено з `main` (коміт `0e66aab`) (`git restore --source origin/main -- api/tests/fixtures/saz/schedule_preview.html`) і примусово додано в репозиторій (`git add -f`), повторний повний прогін — **327 passed**. Правило `**/*.html` у `.gitignore` варто звузити (наприклад, до `**/htmlcov/`), щоб воно не зачіпало фікстури й шаблони.
* **Висновок:** зміни, згенеровані агентом, потрібно переглядати не лише за змістом, а й за списком змінених файлів (`git diff --stat`) — регресійний прогін виявив видалення, яке не помітно в diff самого методу.

### Фінальний прогін на `main` (після злиття A, B, C)

_Заповнити після злиття всіх цілей: результат `python -m pytest -q` і покриття `python -m pytest --cov=api --cov-branch --cov-report=term -q`._

## Бонуси

### Характеризаційні тести перед рефакторингом

Що зроблено. Команда `python manage.py import_saz` (`Backend/api/management/commands/import_saz.py`) до Лаб 8 не мала жодного тесту: покриття 0% (26 рядків, 8 гілок). Спершу написано характеризаційні тести `Backend/api/tests/test_import_saz_command.py` (11 тестів), які фіксують її поточну поведінку, і лише після цього окремим комітом виконано рефакторинг Extract Method.

| Крок | Коміт | Результат тестів |
|---|---|---|
| 1. Характеризаційні тести (команда ще не змінена) | [`3cb4e7e` test: add characterization tests for import_saz command](https://github.com/ukma-fin-ssdm-2026/unispace/commit/3cb4e7e) | 11 passed; покриття `import_saz.py` 0% → 100% |
| 2. Рефакторинг (Extract Method) | [`d50bb2a` refactor: extract helpers from import_saz handle [REFACTOR]](https://github.com/ukma-fin-ssdm-2026/unispace/commit/d50bb2a) | ті самі 11 passed; повний набір 338 passed |

Зафіксована поведінка, зокрема та, що виглядає дивно:

* друкується рівно 5 лічильників у сталому порядку (`lessons_created`, `lessons_updated`, `bookings_created`, `conflicts_created`, `teachers_created`), далі попередження й рядок «Імпорт завершено»;
* лічильник `online_lessons` імпорт рахує, але команда його не друкує;
* існування файлу перевіряється раніше за дату: якщо погані обидва аргументи, повідомлення лише «Файл не знайдено»;
* невалідні байти UTF-8 у збереженій сторінці замінюються (`errors="replace"`), імпорт проходить;
* для нерозпізнаної сторінки команда падає з `CommandError «Імпорт не вдався: ...»`, але запис `failed` у `SyncLog` лишається;
* повторний імпорт друкує `lessons_created: 0`, `lessons_updated: 13`; без `--semester-start` команду відхиляє парсер аргументів.

Рефакторинг. Запах — довгий метод `handle`, що водночас перевіряв аргументи, читав файл і друкував підсумок. Техніка — Extract Method: `_existing_file`, `_parse_semester_start`, `_read_page` і `_write_summary`, перелік лічильників — константа `SUMMARY_COUNTERS`. Незмінними лишилися порядок перевірок, тексти помилок, формат виводу, заміна невалідних байтів і запис у журнал синхронізації; це доводять ті самі 11 тестів, зелені до і після.

Запуск: `cd Backend && python -m pytest api/tests/test_import_saz_command.py -v`.

Відповідальна: Ольга Михайлик.
