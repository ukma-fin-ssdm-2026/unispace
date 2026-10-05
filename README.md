# UniSpace [![CI Pipeline](https://github.com/ukma-fin-ssdm-2026/unispace/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/unispace/actions/workflows/ci.yml)

**Інтерактивна API Документація [(Swagger UI на GitHub Pages)](https://ukma-fin-ssdm-2026.github.io/unispace/)**

## Опис проєкту
Розклад університету публікується в САЗ, але САЗ фіксує лише початковий стан: яка пара, у якої групи, в якій аудиторії. Реальні зміни — перенесення пари в інший кабінет, тимчасова зайнятість приміщення, накладки двох занять в одній аудиторії — відбуваються поза системою, узгоджуються в месенджерах і часто доходять до студентів із запізненням або не доходять узагалі.

UniSpace — вебзастосунок, який працює як шар керування аудиторним фондом поверх САЗу. Система періодично імпортує розклад із САЗу і створює на його основі бронювання аудиторій за замовчуванням. Викладач може змінити аудиторію свого заняття; система при цьому гарантує, що дві пари не опиняться в одному приміщенні одночасно, підбирає вільні альтернативи за місткістю та корпусом і повідомляє всіх, кого зміна стосується. Джерелом істини щодо самого розкладу — предметів, груп, часу занять — лишається САЗ; UniSpace керує виключно розподілом приміщень.

## Інструкція із запуску (Локально)
Оскільки архітектура передбачає фізичне розділення на два незалежні Django-проєкти, для повноцінної роботи системи необхідно запустити обидва сервери:

**1. Запуск Backend (REST API та Документація)**
- Клонуйте репозиторій та перейдіть у папку бекенду: `cd Backend`
- Встановіть залежності: `pip install -r requirements.txt`
- Запустіть сервер розробки: `python manage.py runserver 8000`
- *Специфікація OpenAPI генерується автоматично. Swagger UI доступний за адресою: `http://localhost:8000/api/docs/`*

**2. Запуск Frontend (Web UI)**
- Відкрийте нову вкладку терміналу та перейдіть у папку фронтенду: `cd Frontend`
- Встановіть залежності: `pip install -r requirements.txt`
- Запустіть сервер розробки на іншому порту: `python manage.py runserver 8001`
- *Клієнтський вебзастосунок доступний за адресою: `http://localhost:8001/`*

## Проєктування та реалізація API
Усі артефакти, що стосуються RESTful API та Code-First підходу, зберігаються в директоріях `src/api/` та `docs/api/`:
* Вихідний код API з анотаціями [(API Source Code)](src/api/)
* Специфікація OpenAPI [(OpenAPI YAML)](docs/api/openapi-generated.yaml)
* Дизайн API [(API Design)](docs/api/api-design.md)
* Атрибути якості API [(Quality Attributes)](docs/api/quality-attributes.md)
* Файл Swagger UI [(Swagger UI Index)](docs/api/index.html)

## Архітектура системи
Архітектурна документація, моделі даних та діаграми зберігаються в директорії `docs/architecture/`:
* Архітектурний огляд [(High-Level Design)](docs/architecture/high-level-design.md)
* Матриця простежуваності архітектури [(Traceability Matrix)](docs/architecture/traceability-matrix.md)
* Модель даних [(Data Model)](docs/architecture/data-model.md)
* Модель загроз STRIDE [(Threat Model)](docs/architecture/threat-model.md)
* Архітектурні рішення [(ADR)](docs/architecture/decisions/)
* UML Діаграми [(UML)](docs/architecture/uml/)

## Артефакти вимог
Усі вимоги, користувацькі історії та матриця простежуваності зберігаються в директорії `docs/requirements/`:
* Вимоги до системи [(FR та NFR)](docs/requirements/requirements.md)
* Користувацькі історії [(User Stories)](docs/requirements/user-stories.md)
* Матриця простежуваності [(RTM)](docs/requirements/rtm.md)

## Документація
Детальніше з проєктом та правилами нашої роботи можна ознайомитися у файлах:
* Опис проєкту [(Project Description)](Project-Description.md)
* Статут команди [(Team Charter)](TeamCharter.md)

## Інформація про команду
| Учасниця                | GitHub                                                 | Постійні ролі                                                                         | Ролі (Лабораторна 4) |
|:------------------------|:-------------------------------------------------------|:--------------------------------------------------------------------------------------|:---------------------|
| **Дар'я Мельник**       | [@DarkHeavenAngel](https://github.com/DarkHeavenAngel) | Супроводжувач репо, Керівник якості, Керівник архітектури                             | Backend Lead         |
| **Ольга Михайлик**      | [@plusikkk](https://github.com/plusikkk)               | Супроводжувач СІ, Керівник простежуваності                                            | Integration Lead     |
| **Анастасія Трекурова** | [@stacytrek](https://github.com/stacytrek)             | Керівник документації                                                                 | Documentation Lead   |
| **Ксенія Тимохина**     | [@XenonTim](https://github.com/XenonTim)               | Керівник трекера завдань, Керівник вимог, Керівник UML                                | API Design Lead      |
| **Дар'я Спіріна**       | [@Hedgehog-blue](https://github.com/Hedgehog-blue)     | Керівник опису проєкту, Керівник функціональних вимог, Керівник моделі даних і загроз | Quality Lead         |
