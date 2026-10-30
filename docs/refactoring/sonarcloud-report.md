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
