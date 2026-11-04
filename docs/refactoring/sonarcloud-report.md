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

### Обрані критерії
* Code Smells
* Technical Debt
* Duplications

## Аналіз проблем безпеки

| № | Проблема | Локація | Рівень небезпеки | План виправлення |
|---|---|---|:---:|---|
| 1 | Make sure that no untrusted code is executed from a fork. | `.github/workflows/pages.yml` (L30) | **High** | Додати перевірку репозиторію та гілки (`if: github.repository == '...' && github.ref == 'refs/heads/main'`) або обмежити права токена `permissions`, щоб запобігти виконанню довільного коду з форків. |
| 2 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L65) | **Medium** | Зафіксувати точні версії залежностей бекенду за допомогою lock-файлу (`pip-compile` / `requirements.lock`) замість плаваючих версій. |
| 3 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L65) | **Medium** | Додати прапорець `--only-binary :all:` до команди `pip install`, щоб встановлювати виключно pre-built wheels і блокувати запуск сторонніх `setup.py`. |
| 4 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L68) | **Medium** | Зафіксувати точні версії для `requirements-dev.txt` у бекенді через lock-файл із хешами пакетів. |
| 5 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L68) | **Medium** | Заборонити збірку tarball-пакетів при встановленні dev-залежностей бекенду, додавши прапорець `--only-binary :all:`. |
| 6 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L195) | **Medium** | Створити та підключити окремий lock-файл із зафіксованими версіями для основного середовища фронтенду. |
| 7 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L195) | **Medium** | Використати `--only-binary :all:` під час встановлення продакшн-пакетів фронтенду для унеможливлення RCE через вразливі setup-скрипти. |
| 8 | Using dependencies without locking resolved versions is security-sensitive. | `.github/workflows/ci.yml` (L198) | **Medium** | Зафіксувати повне дерево транзитивних залежностей розробника для фронтенду (`requirements-dev.lock`). |
| 9 | Omitting "--only-binary :all:" can lead to the execution of setup scripts. Make sure it is safe here. | `.github/workflows/ci.yml` (L198) | **Medium** | Додати параметр `--only-binary :all:` при встановленні dev-інструментів фронтенду в CI-раннері. |
| 10 | Add integrity and crossorigin="anonymous" attributes to this element to enforce integrity checks. | `docs/api/index.html` (L7) | **Low** | Додати атрибути SRI (`integrity="sha384-..."` та `crossorigin="anonymous"`) до тегу підключення зовнішнього CSS/JS або завантажити ресурс локально. |
| 11 | Add integrity and crossorigin="anonymous" attributes to this element to enforce integrity checks. | `docs/api/index.html` (L14) | **Low** | Додати криптографічний хеш `integrity` та `crossorigin="anonymous"` для валідації цілісності завантажуваного CDN-файлу. |
| 12 | Add integrity and crossorigin="anonymous" attributes to this element to enforce integrity checks. | `docs/api/index.html` | **Low** | Захистити підключення третього зовнішнього ресурсу документації шляхом додавання перевірки SRI (`integrity` + `crossorigin="anonymous"`). |

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
