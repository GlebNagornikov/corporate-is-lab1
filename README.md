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
docker compose exec web python manage.py test --settings=config.settings.test
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

После части 6 эти запросы требуют JWT. Получите access-токен через `/api/auth/token/`
(безопасный пример ввода пароля приведён ниже) и сохраните его в переменную `ACCESS`.
Для чтения нужны `employees.view_employee` / `employees.view_department`,
для записи — соответствующие права `add`, `change`, `delete`.
Группа «Менеджеры магазина» этих прав не получает.

Создать отдел:
```bash
curl -H "Authorization: Bearer $ACCESS" -X POST http://127.0.0.1:8000/api/departments/   -H "Content-Type: application/json"   -d '{"name": "Продажи", "description": "Отдел продаж"}'
```

Получить список сотрудников:
```bash
curl -H "Authorization: Bearer $ACCESS" http://127.0.0.1:8000/api/employees/
```

Создать сотрудника:
```bash
curl -H "Authorization: Bearer $ACCESS" -X POST http://127.0.0.1:8000/api/employees/   -H "Content-Type: application/json"   -d '{"full_name": "Иванова Анна", "position": "Менеджер", "hired_at": "2026-09-15", "department": 1}'
```

Ответ (`201 Created`):
```json
{"id": 3, "full_name": "Иванова Анна", "position": "Менеджер", "hired_at": "2026-09-15", "department": 1}
```

Получить, частично обновить и удалить сотрудника:
```bash
curl -H "Authorization: Bearer $ACCESS" http://127.0.0.1:8000/api/employees/1/
curl -H "Authorization: Bearer $ACCESS" -X PATCH http://127.0.0.1:8000/api/employees/1/   -H "Content-Type: application/json"   -d '{"position": "Ведущий менеджер"}'
curl -H "Authorization: Bearer $ACCESS" -X DELETE http://127.0.0.1:8000/api/employees/2/
```

> На Windows запускайте примеры в Git Bash: в PowerShell `curl` — это алиас `Invoke-WebRequest`, поэтому используйте `curl.exe` и экранируйте кавычки в JSON.

Проверить данные напрямую в Postgres:
```bash
docker compose exec db psql -U corporate_is -d corporate_is -c "SELECT full_name, department_id FROM employees_employee;"
```


## Catalog extras (Lab 5)

Implementation notes and verification: [docs/catalog-extras.md](docs/catalog-extras.md).


## Лабораторная №6: корзина, заказы и панель менеджера (части 2–5)

Реконструированы части 2–4 и выполнена часть 5: корзина, оформление, промокоды, кабинет, Mailpit, панель менеджера, группа с 12 правами и тесты. Части 6–7 (JWT/API, права, быстрые тесты и покрытие) реализованы ниже.

После первого запуска выполнить:

```powershell
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_groups
docker compose exec web python manage.py test --settings=config.settings.test
```

На момент завершения части 5 проходили 51 тест; первый полный прогон — 13.420 с (без создания тестовой БД). В проекте было 33 теста лабораторной №5, добавлено 12 из методички и 6 проверок админки/прав.

Менеджер — staff, не superuser, член группы «Менеджеры магазина», связан с карточкой сотрудника отдела продаж. В новом окружении его создают в admin после `setup_groups`. Локальные пароли не входят в репозиторий.

Подробности: [часть 5](docs/lab6-part5.md). История реконструкции незапушенных частей 2–4: [контрольная точка](docs/lab6-restoration.md).

## Лабораторная №6: REST API, JWT и права (часть 6)

Ветка `feature/orders-api` от `develop`. Зависимость: `djangorestframework-simplejwt==5.5.1`.
После изменения зависимостей пересобрать образ:

```bash
docker compose up -d --build
docker compose exec web python manage.py check
docker compose exec web python manage.py test --settings=config.settings.test
```

По умолчанию API закрыт (`IsAuthenticated`). JWT проверяется раньше сессии:
аноним получает **401 вместо прежнего 403**, а вошедший без прав — **403**.
Категории и товары явно открыты (`AllowAny`), создание отзыва требует входа.
`/api/employees/` требует `view_employee`, `/api/departments/` — `view_department`;
стандартные права создания/изменения/удаления тоже проверяются.

| Метод | URL | Назначение |
|---|---|---|
| POST | `/api/auth/token/` | Логин и пароль → access + refresh |
| POST | `/api/auth/token/refresh/` | Refresh → новый access |
| GET | `/api/cart/` | Собственная корзина |
| POST | `/api/cart/items/` | Добавить товар: product, quantity |
| PATCH / DELETE | `/api/cart/items/<product_id>/` | Изменить количество / удалить строку |
| GET / POST | `/api/orders/` | Список / оформление из корзины |
| GET | `/api/orders/<id>/` | Заказ с позициями и историей |
| POST | `/api/orders/<id>/cancel/` | Покупатель отменяет свой новый заказ |
| POST | `/api/orders/<id>/status/` | Менеджер меняет статус по допустимым переходам |

`access` действует 15 минут, `refresh` — 7 дней. Настраивается переменными
`JWT_ACCESS_MINUTES` и `JWT_REFRESH_DAYS`. JWT подписан, но не зашифрован;
токены и пароли нельзя добавлять в Git или публиковать в логах.

Покупатель видит только свои заказы, чужой номер даёт 404. Право `orders.view_order`
открывает менеджеру все заказы; `orders.change_order` разрешает смену статуса.
Фильтр очереди: `/api/orders/?status=new`. PUT/PATCH/DELETE для заказов отсутствуют.
Суммы, состав, статус и история не принимаются от клиента при оформлении.
Курьер без непустого адреса отклоняется сервисом с ответом 400, без записи заказа.

Пример получения токена (Git Bash; настоящий пароль не сохранять в файле/истории):

```bash
read -r -p 'Username: ' SHOP_USER
read -r -s -p 'Password: ' SHOP_PASSWORD; echo
TOKENS=$(printf '%s' "$SHOP_PASSWORD" | python3 -c 'import json,sys; print(json.dumps({"username":sys.argv[1],"password":sys.stdin.read()}))' "$SHOP_USER" | curl -sS http://localhost:8000/api/auth/token/ -H 'Content-Type: application/json' --data-binary @-)
unset SHOP_PASSWORD
ACCESS=$(printf '%s' "$TOKENS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access"])')
curl -sS http://localhost:8000/api/orders/ -H "Authorization: Bearer $ACCESS"
unset ACCESS TOKENS
```

Проверка части 6: **66 тестов, OK**, 11.358 с (без создания тестовой базы).
Это прежние 51 тест + 15 новых API/сервисных проверок; число 29 в методичке
относится к минимальному эталону, а не к этому расширенному проекту.
Проверены JWT/refresh, права, изоляция корзин и заказов, оформление, отмена,
смена статуса и фильтр, запрет записи вычисляемых полей и прямого изменения заказа.
Ruff check и форматирование выполняются в контейнере.

Живая проверка через `curl.exe`: token → корзина → курьер без адреса (400) →
самовывоз (201) → отказ покупателю в смене статуса (403) → подтверждение
менеджером (200) → недопустимый переход (400) → refresh (200).
В Mailpit получены оба письма — оформление и подтверждение. Созданные специально
для проверки пользователи, товар, категория, корзина и заказ после проверки удалены;
существующие данные магазина не изменялись.

Части 6–7 подготовлены единым коммитом в ветке `feature/orders-api` для PR в `develop`.
Изменение поведения API: «API для анонимов теперь отвечает
401 вместо 403; /api/employees/ требует права view_employee».

## Лабораторная №6: быстрые тесты и покрытие (часть 7)

Обычный запуск тестов теперь использует отдельный модуль `config.settings.test`:

```bash
docker compose exec web python manage.py test --settings=config.settings.test
```

Этот модуль наследует `base`, а не `dev`: без debug toolbar и с быстрым
`MD5PasswordHasher` **только для тестов**. В `base`, `dev`, `prod` остаются
безопасные рабочие хешеры; MD5 для настоящих паролей недопустим.

`coverage==7.16.2` добавлен в dev-зависимости. После обновления зависимостей:

```bash
docker compose up -d --build
docker compose exec web coverage run manage.py test --settings=config.settings.test
docker compose exec web coverage report
docker compose exec web coverage html
```

HTML-отчёт: `htmlcov/index.html` в папке проекта, открывается с ПК.
`.coverage` и `htmlcov/` исключены из Git. В измерение входят исходники проекта,
но не миграции, пакеты тестов, `config` и `manage.py` — настройки в `pyproject.toml`.

Результаты на текущем локальном стенде (время `Ran ... tests`, без создания тестовой БД):

| Проверка | Число тестов | Время |
|---|---:|---:|
| Часть 6, обычные настройки | 66 | 11.358 с |
| Те же тесты, быстрые настройки | 66 | 3.166 с |
| Итог части 7, быстрые настройки | 69 | 2.705 с |
| Итог части 7 под coverage | 69 | 4.473 с |

Это отдельные замеры; время зависит от нагрузки, прогрева и файловой системы Docker.
Менее секунды из эталона на этом стенде не достигнуто.

**Общее покрытие после исправлений: 91% (972 из 1063 исполняемых строк).**
`orders/services.py` — **97%**, `cart/api.py` — **96%**,
`orders/notifications.py` — **100%**. Покрытие строк не заменяет проверок результатов.
Остаются непокрытыми, в частности, `seed_catalog` (0%), некоторые HTML-ветки ошибок
корзины (`cart/views.py`: 68%) и заказов (`orders/views.py`: 77%).

Добавлены все три самостоятельных сценария из части 7:

- `OSError` при отправке письма: заказ сохраняется, остаток списывается, корзина
  очищается, ошибка с traceback и номером заказа попадает в лог;
- PATCH количества сверх остатка: API возвращает и сохраняет количество, равное остатку;
- отмена чужого заказа: 404, статус, история и остаток не меняются.

### Почему отмена не возвращает использование промокода

Текущее правило: `used_count` увеличивается при успешном оформлении и не уменьшается
при отмене. Лимит означает число успешных применений промокода к оформленным заказам,
а не число доставленных заказов. Для учебного магазина это осознанно сохраняет историю
использований и не позволяет многократно переиспользовать ограниченный промокод через
цикл «оформить → отменить». Недостаток: добросовестный покупатель после отмены тоже
теряет применение. Если бизнес решит возвращать его, потребуется отдельное правило
со строго однократным возвратом под блокировкой и тестами повторных/параллельных отмен;
простое уменьшение счётчика без этих гарантий небезопасно.

## Проверка готовности после лабораторной №6 (2026-10-28)

- Исправлено слияние гостевой корзины: снятые с продажи и закончившиеся товары
  пропускаются с предупреждением, доступные переносятся, вход не падает.
- Параметр `next` после добавления в корзину проверяется по текущему хосту и HTTPS;
  внешние и небезопасные адреса заменяются страницей корзины.
- Production наследует SMTP OPTIONS из `base`, включая `EMAIL_HOST` и `EMAIL_PORT`.
- Добавлено 5 регрессионных тестов: два сценария слияния, небезопасные/локальные
  перенаправления и сохранение SMTP-настроек production без MD5-хешера.
- Повторный прогон под coverage: **74 теста, OK, 5.620 с** (без создания тестовой БД);
  покрытие **91% (972/1063)**. Замеры в таблице выше относятся к предыдущему этапу.
- Django check, проверка отсутствия новых и неприменённых миграций — успешно.
- На текущем локальном стенде выполнен `setup_groups`: ровно 12 прав.
  Учебный `manager` — staff, не superuser, связан с сотрудником отдела «Продажи».
  Случайный пароль не публикуется и не хранится в репозитории. Для собственного
  входа задайте пароль интерактивно (не передавайте его аргументом команды):

```bash
docker compose exec web python manage.py changepassword manager
```

Создание локального менеджера не переносится через Git: в новом окружении
после `migrate` выполните `setup_groups` и создайте staff-пользователя в admin,
добавьте в группу «Менеджеры магазина» и привяжите карточку сотрудника отдела продаж.

Живая проверка через `curl.exe`: анонимные заказы 401, каталог 200, JWT 200,
корзина 200, курьер без адреса 400, заказ 201, смена статуса покупателем 403,
менеджером 200, запрещённый переход 400, refresh 200, API сотрудников 403
для покупателя и менеджера магазина. В Mailpit получены оба письма.
Временные покупатель, заказ, корзина, товар и категория удалены; менеджер сохранён.
