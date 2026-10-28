# Corporate IS

Учебный проект курса «Разработка корпоративных ИС»: Django + PostgreSQL в Docker Compose (лабораторная работа №1), модели со связями и REST API на Django REST Framework (лабораторная работа №2).

## Стек

- Python 3 + Django
- Django REST Framework
- PostgreSQL 16 (через Docker Compose)
- psycopg2-binary, django-environ

## Запуск в Docker

Для запуска нужны Git и Docker с Compose. Python на хосте для запуска приложения не требуется.

1. Склонировать репозиторий и перейти в его корень:
   ```bash
   git clone git@github.com:GlebNagornikov/corporate-is-lab1.git
   cd corporate-is-lab1
   ```

2. При первом запуске скопировать пример конфигурации:
   ```bash
   cp .env.example .env
   ```
   Заполнить `SECRET_KEY` и `POSTGRES_PASSWORD`; тот же пароль указать в `DATABASE_URL`. Значение `SECRET_KEY` заключить в одинарные кавычки, чтобы Docker Compose не подставлял переменные вместо символов `$`. Настоящий `.env` не коммитить.

   Если база уже существует, сохранить прежние `.env`, `SECRET_KEY` и параметры доступа к базе: изменение `POSTGRES_*` не меняет пользователя и пароль в существующем томе PostgreSQL.

   `DATABASE_URL` в `.env` оставляется с `localhost` для команд с хоста. В контейнере `web` Compose переопределяет хост базы на `db`. Если порт PostgreSQL на хосте занят другим проектом, изменить `POSTGRES_HOST_PORT` и порт в `DATABASE_URL` на одинаковое свободное значение, например `5433`.

3. Собрать образ и запустить Django вместе с PostgreSQL:
   ```bash
   docker compose up -d --build
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py createsuperuser
   ```
   Создание суперпользователя нужно при первом запуске новой базы; при сохранённой базе можно использовать существующую учётную запись.

Сайт: http://localhost:8000/, admin panel: http://localhost:8000/admin/, REST API: http://localhost:8000/api/.
У корневого адреса `/` может быть ответ 404: для проверки приложения открыть `/admin/` или `/api/employees/`.

### Проверка и повседневная работа

```bash
docker compose ps
docker compose logs web --tail 30
docker compose exec web python manage.py test
```

У `db` должен быть статус `healthy`, у `web` — `Up`; в логах Django — успешная проверка настроек и запуск сервера. Изменения кода подхватываются через bind mount, после изменения зависимостей нужно повторить `docker compose up -d --build`.

`docker compose down` сохраняет том базы. **Не выполнять `docker compose down -v`, если данные нужны: эта команда удаляет том PostgreSQL.** Для сохранения прежнего тома также нельзя менять имя Compose-проекта. Команды выполнять из обычной папки репозитория, а не из служебной папки `docker-desktop-bind-mounts`; если имя папки изменилось, для существующего стенда использовать `docker compose -p corporate-is-lab1 ...` во всех командах.

### Для разработки на хосте: IDE и pre-commit

Виртуальное окружение нужно для подсказок IDE и Git-хуков; само приложение запускается в Docker. Команды для Linux, WSL и macOS:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements/dev.txt
pre-commit install
pre-commit run --all-files
```

Если доступна только команда `python3`, использовать её вместо `python`. На Windows PowerShell окружение активируется командой `venv\Scripts\Activate.ps1`.

Ruff проверяет код и форматирование; pre-commit запускает проверки перед коммитом. Если хук исправил файлы, проверить diff, повторить `git add` для нужных файлов и повторить коммит.

`manage.py` по умолчанию использует `config.settings.dev`; WSGI и ASGI — `config.settings.prod`. Проверка prod-настроек:

```bash
docker compose exec web python manage.py check --deploy --settings=config.settings.prod
```

Для реальной отправки писем в prod дополнительно требуется настроить SMTP-сервер; выбор SMTP-backend сам по себе отправку не настраивает.

### Ветки

`main` — релизы, `develop` — разработка, задачи — `feature/*` от `develop`. Изменения отправляются через Pull Request в `develop` и сливаются через **Create a merge commit**, без squash и rebase.

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

API построен на Django REST Framework (`ModelViewSet` + `DefaultRouter`). После запуска контейнеров (`docker compose up -d --build`) в браузере открывается browsable API: `http://127.0.0.1:8000/api/`.

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


## Catalog extras (Lab 5)

Implementation notes and verification: [docs/catalog-extras.md](docs/catalog-extras.md).


## Лабораторная №6: корзина, заказы и панель менеджера (части 2–5)

Реконструированы части 2–4 и выполнена часть 5: корзина, оформление, промокоды, кабинет, Mailpit, панель менеджера, группа с 12 правами и тесты. JWT/API и покрытие из частей 6–7 ещё не реализованы.

После первого запуска выполнить:

```powershell
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_groups
docker compose exec web python manage.py test
```

Все 51 тест проходят; первый полный прогон после части 5 — 13.420 с (без создания тестовой БД). В проекте было 33 теста лабораторной №5, добавлено 12 из методички и 6 проверок админки/прав.

Менеджер — staff, не superuser, член группы «Менеджеры магазина», связан с карточкой сотрудника отдела продаж. В новом окружении его создают в admin после `setup_groups`. Локальные пароли не входят в репозиторий.

Подробности: [часть 5](docs/lab6-part5.md). История реконструкции незапушенных частей 2–4: [контрольная точка](docs/lab6-restoration.md).
