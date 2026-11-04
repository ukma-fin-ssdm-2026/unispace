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
 
| Критерій        | До                                      | Після         | Зміна  |
|-----------------|-----------------------------------------|---------------|--------|
| Security Rating | C (12 проблем: 1 High, 8 Medium, 3 Low) | A (0 проблем) | С -> А |
| Code Smells     | A / 0                                   | A / 0         | -      |
| Technical Debt  | A / 0 г                                 | A / 0 г       | -      |
| Duplications    | A / 0.0%                                | A / 0.0%      | -      |
| Reliability     | A / 0                                   | A / 0         | -      |

## Бонуси

### Quality Gate як обов'язкова перевірка PR
Для забезпечення високих стандартів коду, ми налаштували **SonarQube Quality Gate** як обов'язкову перевірку (branch protection) для злиття змін у гілку `main`. Тепер жоден Pull Request не може бути прийнятий, якщо він містить критичні вразливості або не відповідає метрикам надійності.

**Доказ 1: Блокування небезпечного коду**
Під час тестування ми навмисно створили коміт із критичною вразливістю (SQL-ін'єкція). Перевірка SonarCloud автоматично встановила статус *Quality Gate Failed* та заблокувала можливість злиття цього коду в `main`.
- 🔗 **Посилання на заблокований PR:** [PR #297 (Failed Status)](https://github.com/ukma-fin-ssdm-2026/unispace/pull/297)
- 🔗 **Звіт про знайдену вразливість:** [Code Scanning Alert #29](https://github.com/ukma-fin-ssdm-2026/unispace/security/code-scanning/29)

**Доказ 2: Прогін після виправлення**
Після видалення вразливого коду, автоматизований аналіз запустився повторно. Quality Gate змінив статус на *Passed*, і злиття було успішно розблоковано.
- 🔗 **Посилання на розблокований PR:** [PR #297 (Passed Status після виправлення)](https://github.com/ukma-fin-ssdm-2026/unispace/pull/297)

> **Примітка щодо використання ШІ:** ШІ-агент (Gemini) використовувався для аналізу проблем безпеки та створення плану виправлень. Результати перевірено людиною (Тимохина Ксенія). Також ШІ був використаний для стилізації та написання тексту для блоку першого бонусного завдання. Результати перевірено людиною (Мельник Дар'я).
