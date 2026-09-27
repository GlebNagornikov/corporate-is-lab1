# Corporate IS

Учебный проект курса «Разработка корпоративных ИС»: Django + PostgreSQL в Docker Compose (лабораторная работа №1), модели со связями и REST API на Django REST Framework (лабораторная работа №2).

## Стек

- Python 3 + Django
- Django REST Framework
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
   pip install -r requirements.txt
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

Проект будет доступен на `http://127.0.0.1:8000/`, admin panel — на `http://127.0.0.1:8000/admin/`, REST API — на `http://127.0.0.1:8000/api/`.

## Приложения

- **employees** — учёт сотрудников и отделов:
  - `Department` — отдел (название — уникальное, описание);
  - `Employee` — сотрудник (ФИО, должность, дата приёма на работу, отдел). Отдел обязателен, связь через `ForeignKey` с `on_delete=PROTECT`: отдел нельзя удалить, пока в нём есть сотрудники. Сотрудники отдела доступны через `department.employees.all()`.

## REST API

API построен на Django REST Framework (`ModelViewSet` + `DefaultRouter`). После запуска сервера (`python manage.py runserver`) в браузере открывается browsable API: `http://127.0.0.1:8000/api/`.

| Метод | URL | Действие |
|-------|-----|----------|
| GET | `/api/employees/` | список сотрудников |
| POST | `/api/employees/` | создать сотрудника |
| GET | `/api/employees/<id>/` | получить сотрудника |
| PUT / PATCH | `/api/employees/<id>/` | обновить сотрудника (полностью / частично) |
| DELETE | `/api/employees/<id>/` | удалить сотрудника |
| GET, POST | `/api/departments/` | список отделов / создать отдел |
| GET, PUT, PATCH, DELETE | `/api/departments/<id>/` | операции с одним отделом |

Поля сотрудника: `id`, `full_name`, `position`, `hired_at` (формат `YYYY-MM-DD`), `department` (id отдела, обязательное).
Поля отдела: `id`, `name`, `description`.

### Примеры запросов

Создать отдел:
```bash
curl -X POST http://127.0.0.1:8000/api/departments/   -H "Content-Type: application/json"   -d '{"name": "Продажи", "description": "Отдел продаж"}'
```

Получить список сотрудников:
```bash
curl http://127.0.0.1:8000/api/employees/
```

Создать сотрудника:
```bash
curl -X POST http://127.0.0.1:8000/api/employees/   -H "Content-Type: application/json"   -d '{"full_name": "Иванова Анна", "position": "Менеджер", "hired_at": "2026-09-15", "department": 1}'
```

Ответ (`201 Created`):
```json
{"id": 3, "full_name": "Иванова Анна", "position": "Менеджер", "hired_at": "2026-09-15", "department": 1}
```

Получить, частично обновить и удалить сотрудника:
```bash
curl http://127.0.0.1:8000/api/employees/1/
curl -X PATCH http://127.0.0.1:8000/api/employees/1/   -H "Content-Type: application/json"   -d '{"position": "Ведущий менеджер"}'
curl -X DELETE http://127.0.0.1:8000/api/employees/2/
```

> На Windows запускайте примеры в Git Bash: в PowerShell `curl` — это алиас `Invoke-WebRequest`, поэтому используйте `curl.exe` и экранируйте кавычки в JSON.

Проверить данные напрямую в Postgres:
```bash
docker compose exec db psql -U corporate_is -d corporate_is -c "SELECT full_name, department_id FROM employees_employee;"
```
