# Corporate IS — Lab 1

Учебный проект: Django + PostgreSQL в Docker Compose. Лабораторная работа №1 курса «Разработка корпоративных ИС».

## Стек

- Python 3 + Django
- PostgreSQL 16 (через Docker Compose)
- psycopg2-binary, python-dotenv

## Как запустить проект локально

1. Склонировать репозиторий:
   ```bash
   git clone git@github.com:GlebNagornikov/corporate-is-lab1.git
   cd corporate-is-lab1
   ```

2. Создать и активировать виртуальное окружение:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Установить зависимости:
   ```bash
   pip install django psycopg2-binary python-dotenv
   ```

4. Создать файл `.env` в корне проекта со следующим содержимым:
   ```
   POSTGRES_DB=corporate_is
   POSTGRES_USER=corporate_is
   POSTGRES_PASSWORD=corporate_is_password
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   ```

5. Поднять базу данных:
   ```bash
   docker compose up -d
   ```

6. Применить миграции и создать суперпользователя:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

7. Запустить сервер разработки:
   ```bash
   python manage.py runserver
   ```

Проект будет доступен на `http://127.0.0.1:8000/`, admin panel — на `http://127.0.0.1:8000/admin/`.

## Приложения

- **employees** — учёт сотрудников (ФИО, должность, дата приёма на работу)