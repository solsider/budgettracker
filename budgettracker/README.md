# BudgetTracker

BudgetTracker — это личный финансовый трекер на Flask. Приложение помогает учитывать доходы и расходы, управлять категориями, смотреть аналитику по периодам и экспортировать отчёты в CSV, Excel и PDF.

## Возможности

- регистрация и вход через Flask-Login и Flask-WTF;
- автоматическое создание базовых категорий при регистрации;
- учёт транзакций с фильтрами, пагинацией и пересчётом баланса;
- управление пользовательскими категориями;
- аналитика на Chart.js с API на Flask и агрегациями через pandas;
- экспорт отчётов в CSV, XLSX и PDF;
- поддержка SQLite для разработки и PostgreSQL для production;
- Docker Compose с Flask, PostgreSQL и Nginx.

## Быстрый старт локально

1. Перейдите в каталог проекта:

   ```bash
   cd budgettracker
   ```

2. Создайте виртуальное окружение и активируйте его:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```

4. Скопируйте переменные окружения:

   ```bash
   copy .env.example .env
   ```

5. Выполните миграции и запустите приложение:

   ```bash
   flask --app app.py db upgrade
   python app.py
   ```

6. Откройте в браузере [http://localhost:8000](http://localhost:8000).

## Запуск через Docker Compose

1. Перейдите в каталог проекта:

   ```bash
   cd budgettracker
   ```

2. Создайте `.env` на основе `.env.example` и при необходимости укажите PostgreSQL-строку подключения.

3. Запустите контейнеры:

   ```bash
   docker compose up --build
   ```

4. Приложение будет доступно по адресу [http://localhost](http://localhost).

## Переменные окружения

- `SECRET_KEY` — секрет приложения.
- `FLASK_ENV` — режим запуска (`development` или `production`).
- `DATABASE_URL` — строка подключения к SQLite или PostgreSQL.
- `PORT` — порт приложения внутри контейнера или локального запуска.
- `FLASK_RUN_HOST` — хост встроенного сервера Flask.

## Миграции

Flask-Migrate уже настроен. Полезные команды:

```bash
flask --app app.py db init
flask --app app.py db migrate -m "Initial schema"
flask --app app.py db upgrade
```

Каталог миграций хранится в `migrations/`.

## Запуск тестов

```bash
cd budgettracker
pytest
```

## Структура проекта

```text
budgettracker/
├── app.py
├── config.py
├── models.py
├── forms.py
├── routes.py
├── requirements.txt
├── conftest.py
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── .env.example
├── README.md
├── utils/
│   └── export.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── transactions.html
│   ├── transaction_form.html
│   ├── categories.html
│   ├── category_form.html
│   ├── category_delete.html
│   └── analytics.html
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── analytics.js
│       └── transaction_form.js
├── nginx/
│   └── default.conf
├── tests/
│   └── test_app.py
└── migrations/
    ├── README
    ├── env.py
    ├── script.py.mako
    └── versions/
        └── 0001_initial.py
```
