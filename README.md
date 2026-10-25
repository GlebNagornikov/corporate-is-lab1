# Corporate IS

Учебный проект курса «Разработка корпоративных ИС»: Django + PostgreSQL в Docker Compose (лабораторная работа №1), модели со связями и REST API на Django REST Framework (лабораторная работа №2).

## Стек

- Python 3 + Django
- Django REST Framework
- PostgreSQL 16 (через Docker Compose)
- psycopg2-binary, django-environ

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

4. Скопировать пример конфигурации и заполнить `.env`:
   ```bash
   cp .env.example .env
   ```
   Для локальной базы из `docker-compose.yml`:
   ```dotenv
   SECRET_KEY=<новый-секретный-ключ>
   DATABASE_URL=postgres://corporate_is:corporate_is_password@localhost:5432/corporate_is
   ALLOWED_HOSTS=localhost,127.0.0.1
   DB_CONN_MAX_AGE=60
   ```
   Сгенерировать ключ:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
   Подставить результат вместо `<новый-секретный-ключ>`. Настоящий `.env` не коммитить; `.env.example` содержит только образец. Если проброшенный порт PostgreSQL изменён, указать его в `DATABASE_URL`.

   `manage.py` по умолчанию использует `config.settings.dev`; WSGI и ASGI — `config.settings.prod`. Проверить prod-настройки можно командой:
   ```bash
   python manage.py check --deploy --settings=config.settings.prod
   ```
   Для реальной отправки писем в prod дополнительно требуется настроить SMTP-сервер; выбор SMTP-backend сам по себе отправку не настраивает.

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

## Лабораторная №3: почему потребовалось пересоздать базу

Изначально проект использовал стандартного пользователя Django, поэтому миграции уже создали таблицу `auth_user` и связанные с ней таблицы. В частности, миграция `admin.0001_initial` была применена к базе со стандартной моделью пользователя.

После добавления `accounts.User` и настройки `AUTH_USER_MODEL = "accounts.User"` зависимость миграции админки стала указывать на первую миграцию приложения `accounts`. Но в существующей базе `admin.0001_initial` уже отмечена как выполненная, а `accounts.0001_initial` ещё не применена. Получается нарушенный порядок зависимостей, поэтому Django останавливается с ошибкой `InconsistentMigrationHistory`. Простая смена настройки не переносит старых пользователей и не перестраивает существующие связи в базе.

В учебной работе эту проблему решаем пересозданием базы: сначала сохраняем отделы и сотрудников в `../employees_backup.json`, затем удаляем том PostgreSQL, применяем миграции к чистой базе, восстанавливаем отделы и сотрудников и заново создаём суперпользователя. Такой способ удаляет прежние данные базы; резервная копия приложения `employees` не сохраняет учётные записи пользователей и остальные данные Django.

В рабочем проекте с важными данными удалять базу нельзя: нужна отдельная продуманная миграция данных и связей. Поэтому собственную модель пользователя лучше создавать в самом начале проекта, до первого применения миграций.

## Лабораторная №3: исправление N+1 запросов

При открытии `/api/employees/` количество SQL-запросов проверялось через SQL-панель Django Debug Toolbar:

| Состояние | Количество SQL-запросов |
|---|---|
| До исправления | 18 |
| После исправления | 4 |

При выводе поля `department_name` обращение к `employee.department` вызывало дополнительные запросы за отделами сотрудников. Чтобы убрать проблему N+1, в `EmployeeViewSet` используется:

```python
queryset = Employee.objects.select_related("department")
```

`select_related` загружает сотрудников вместе с отделами одним запросом с SQL JOIN, без отдельного запроса за отделом каждого сотрудника. Указанные числа — общее количество запросов страницы, показанное панелью, а не только запросы за списком сотрудников.

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
