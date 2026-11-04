# Corporate IS: учебный интернет-магазин

Проект курса «Разработка корпоративных ИС», лабораторные №1–6. Идея мини-ИС: магазин с каталогом товаров, поиском, корзиной, заказами, личным кабинетом покупателя и рабочим местом менеджера. Приложение `employees` сохраняет учёт сотрудников и отделов из первых лабораторных; пользователь может быть связан с карточкой сотрудника.

Актуальная версия — ветка `develop`. `main` содержит этап лабораторной №3; выпуск магазина в `main` через `release/*` относится к следующей лабораторной. Текущий Compose — стенд разработки.

## Что реализовано

| Лабораторная | Результат |
|---|---|
| №1 | Django, PostgreSQL в Docker, сотрудники, admin, конфигурация через окружение |
| №2 | Отделы, обязательная связь сотрудника с отделом (`PROTECT`), CRUD API, работа через PR |
| №3 | Настройки base/dev/prod, собственный User, логирование, Debug Toolbar, исправление N+1 |
| №4 | Docker для приложения, разделение зависимостей, Ruff, pre-commit, git-flow |
| №5 | Дерево категорий, товары, русский полнотекстовый поиск, фильтры, отзывы, API каталога |
| №6 | Корзины, оформление и отмена заказов, промокоды, письма, панель менеджера, JWT и права, тесты и покрытие |

Дополнительные задания №5 тоже реализованы: валидация старой цены в admin, подсветка поиска, фильтр рейтинга и галерея. Подробности: [docs/catalog-extras.md](docs/catalog-extras.md).

Результаты проверки и оставшиеся замечания: [docs/labs-review.md](docs/labs-review.md). Наличие функциональности в таблице не означает отсутствие всех замечаний к сдаче.

## Стек и структура

Python 3.13, Django 6.1.1, DRF 3.18.1, PostgreSQL 16, django-environ, django-filter, Pillow, SimpleJWT; Mailpit для писем. Версии закреплены в `requirements/base.txt` и `requirements/dev.txt`.

- `accounts` — User на основе AbstractUser, телефон, связь OneToOne с Employee, регистрация.
- `employees` — Department и Employee, admin и API.
- `catalog` — категории, товары, отзывы, изображения, витрина и API.
- `cart` — корзина в БД, гостевой `cart_id` в сессии, объединение при входе.
- `orders` — заказы, снимки товаров и цен, промокоды, история, сервисы, письма и API.
- `config/settings` — base, dev, prod и отдельные test-настройки.

## Запуск в Docker

Нужны Git и работающий Docker с Compose. Python на компьютере для запуска сайта не требуется. Команды выполняются из корня репозитория.

```bash
git clone --branch develop https://github.com/GlebNagornikov/corporate-is-lab1.git
cd corporate-is-lab1
```

Создать `.env` из примера (только при первом запуске):

```powershell
Copy-Item .env.example .env
```

В Git Bash, Linux и macOS: `cp .env.example .env`.

В `.env` заменить `SECRET_KEY` и `POSTGRES_PASSWORD`, указать тот же пароль в `DATABASE_URL`. Использовать длинный случайный ключ. Значения с `$` заключать в одинарные кавычки, чтобы Compose не подставлял переменные. Спецсимволы в пароле внутри URL должны быть URL-кодированы. Настоящий `.env` не коммитить.

| Переменная | Назначение / значение по умолчанию |
|---|---|
| `SECRET_KEY` | Секрет Django, обязательно заменить `change-me` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | База, пользователь и пароль PostgreSQL |
| `POSTGRES_HOST_PORT` | Порт БД на компьютере, по умолчанию 5432 |
| `DATABASE_URL` | Для команд с компьютера: PostgreSQL на localhost; в web Compose задаёт хост `db` и порт 5432 |
| `DB_CONN_MAX_AGE` | Время повторного использования соединений, 60 секунд |
| `ALLOWED_HOSTS` | Разрешённые хосты для prod; dev использует localhost и 127.0.0.1 |
| `LOG_LEVEL` | Уровень логов приложений employees/orders, INFO |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP: по умолчанию localhost:1025; Compose задаёт mailpit:1025 |
| `DEFAULT_FROM_EMAIL` | Отправитель, по умолчанию `Магазин <shop@example.com>` |
| `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS` | Срок access/refresh, 15 минут / 7 дней |
| `CSRF_TRUSTED_ORIGINS` | Необязательный список доверенных HTTPS-источников для prod |
| `DJANGO_SETTINGS_MODULE` | Выбор настроек; manage.py по умолчанию dev, WSGI/ASGI — prod |

Последние необязательные параметры можно добавить в `.env`; они читаются кодом, хотя отсутствуют в `.env.example`.

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_groups
docker compose exec web python manage.py createsuperuser
```

Для новой демонстрационной базы дополнительно:

```bash
docker compose exec web python manage.py seed_catalog --images
```

Команда создаёт 10 категорий и 30 товаров с картинками. Повторный запуск не дублирует записи и сообщает «новых 0», но **обновляет демонстрационные названия, цены и остатки**. Не запускать её поверх изменённого каталога, если эти изменения нужно сохранить.

| Страница | Адрес |
|---|---|
| Витрина | http://localhost:8000/ |
| Регистрация / вход | http://localhost:8000/accounts/signup/ / http://localhost:8000/accounts/login/ |
| Корзина | http://localhost:8000/cart/ |
| Оформление / мои заказы | http://localhost:8000/orders/checkout/ / http://localhost:8000/orders/ |
| Админка | http://localhost:8000/admin/ |
| Каталог API | http://localhost:8000/api/catalog/ |
| Письма Mailpit | http://localhost:8025/ |

`/api/` — корень роутера сотрудников и отделов, а не полный список всех API проекта. Выход из аккаунта выполняется POST-формой.

### Проверка запуска и сохранность данных

```bash
docker compose ps
docker compose logs web --tail 30
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate --check
```

`db` должен быть healthy, `web` — Up. Код смонтирован в контейнер, runserver подхватывает изменения. После изменения зависимостей пересобрать образ: `docker compose up -d --build`.

`docker compose down` сохраняет базу в томе `pgdata`. **`docker compose down -v` удаляет базу.** Для существующей базы сохранить прежние `.env` и пароль: изменение `POSTGRES_PASSWORD` не меняет пароль в уже созданном томе. В Compose закреплено имя проекта `corporate-is-lab1`; для второго независимого стенда нужно другое имя проекта и свободные порты. При занятом порте БД изменить `POSTGRES_HOST_PORT` и порт в `DATABASE_URL` одинаково.

`media/`, база, учётные записи и локальные пароли не передаются через Git. Сохранять их отдельно.

## Каталог и заказы

Каталог поддерживает `q`, `category` (slug, включая подкатегории), `price_min`, `price_max`, `in_stock`, `on_sale`, `rating_min` (0–5), `ordering` и `page`. Сортировка: `price`, `created_at`, `rating`, `name`, с `-` для убывания. Витрина показывает 12 товаров на странице, API товаров — 20.

Примеры: `/?q=ноутбуки`, `/?q=наушнеки`, `/?rating_min=4&ordering=price`. Поиск использует словарь PostgreSQL `russian`, websearch-синтаксис и подсказки при опечатках; `search_vector` — GeneratedField, для поиска установлены GIN-индексы и расширение `pg_trgm`. Рейтинг учитывает только опубликованные отзывы. Один пользователь может оставить один отзыв на товар.

Количество в корзине ограничено остатком; при входе гостевая корзина объединяется с пользовательской. Недоступные товары пропускаются с предупреждением.

Оформление выполняется в одной транзакции: товары блокируются по pk, проверяются остатки и промокод, фиксируются название и цена, списывается склад, очищается корзина. Курьер требует адрес. Самовывоз бесплатен; курьер стоит 500 при сумме после скидки меньше 5000, иначе бесплатен. Письма отправляются после commit; `OSError` отправки логируется и не отменяет заказ.

Переходы: `new → confirmed → shipped → delivered`; из `new` и `confirmed` разрешён `cancelled`. Покупатель отменяет только свой новый заказ; отмена возвращает товары на склад. Чужой заказ для покупателя даёт 404.

### Менеджер магазина

После `migrate` выполнить `setup_groups`. Команда идемпотентно задаёт группе «Менеджеры магазина» ровно 12 прав. Создать в admin обычного пользователя со `is_staff=True`, без `is_superuser`, добавить в группу и связать с карточкой сотрудника отдела продаж. Группа управляет товарами, отзывами, промокодами и обработкой заказов; права сотрудников и пользователей ей не выдаются.

В admin суммы, позиции и история заказа доступны только для чтения; статус меняется действиями через сервис, создание и удаление заказов запрещены. Локальные пользователи не создаются при клонировании. Пароль существующего менеджера задаётся интерактивно:

```bash
docker compose exec web python manage.py changepassword manager
```

## REST API и права

JWT проверяется раньше сессии. Анонимный запрос к закрытому API получает **401**, вошедший без прав — **403**. Каталог открыт; публикация отзыва требует входа. При сессионной аутентификации изменяющие запросы требуют CSRF.

| Метод | URL | Назначение |
|---|---|---|
| POST | `/api/auth/token/` | username + password → access и refresh |
| POST | `/api/auth/token/refresh/` | refresh → новый access |
| GET | `/api/catalog/categories/`, `/api/catalog/categories/<slug>/` | Категории |
| GET | `/api/catalog/products/`, `/api/catalog/products/<slug>/` | Товары и фильтры |
| GET / POST | `/api/catalog/products/<slug>/reviews/` | Чтение / создание отзыва |
| GET | `/api/cart/` | Собственная корзина |
| POST | `/api/cart/items/` | Добавить: product (id), quantity |
| PATCH / DELETE | `/api/cart/items/<product_id>/` | Изменить quantity / удалить строку |
| GET / POST | `/api/orders/` | Список / оформление из корзины |
| GET | `/api/orders/<id>/` | Заказ, позиции, история |
| POST | `/api/orders/<id>/cancel/` | Отмена покупателем |
| POST | `/api/orders/<id>/status/` | Смена статуса менеджером: status, comment |
| GET / POST | `/api/employees/`, `/api/departments/` | Список / создание |
| GET / PUT / PATCH / DELETE | `/api/employees/<id>/`, `/api/departments/<id>/` | Операции с записью |

При оформлении передаются `full_name`, `phone`, `email`, `delivery_method` (`pickup` / `courier`), при необходимости `address`, `comment`, `promo_code`. Суммы, позиции и статус рассчитывает сервер. Прямые PUT/PATCH/DELETE заказа отсутствуют.

`orders.view_order` открывает все заказы, `orders.change_order` разрешает смену статуса; фильтр очереди — `/api/orders/?status=new`. Для сотрудников и отделов нужны соответствующие права `view`, `add`, `change`, `delete`. Менеджер магазина этих прав не имеет. DELETE непустого отдела возвращает **409 Conflict** с пояснением, что в отделе есть сотрудники; отдел и сотрудники сохраняются. Пустой отдел удаляется с ответом **204 No Content** при наличии права `delete_department`.

Ответ сотрудника содержит `id`, `full_name`, `position`, `hired_at`, `department`, `department_name`; отдела — `id`, `name`, `description`. Пагинируемые списки возвращают `count`, `next`, `previous`, `results`.

Пример JWT и запроса (Git Bash/Linux/macOS, требуется Python на компьютере; если команда называется python3, заменить python):

```bash
read -r -p 'Username: ' SHOP_USER
read -r -s -p 'Password: ' SHOP_PASSWORD; echo
TOKENS=$(printf '%s' "$SHOP_PASSWORD" | python -c 'import json,sys; print(json.dumps({"username":sys.argv[1],"password":sys.stdin.read()}))' "$SHOP_USER" | curl -sS http://localhost:8000/api/auth/token/ -H 'Content-Type: application/json' --data-binary @-)
unset SHOP_PASSWORD
ACCESS=$(printf '%s' "$TOKENS" | python -c 'import json,sys; print(json.load(sys.stdin)["access"])')
curl -sS http://localhost:8000/api/orders/ -H "Authorization: Bearer $ACCESS"
# Для пользователя с employees.add_department:
curl -sS http://localhost:8000/api/departments/ -H "Authorization: Bearer $ACCESS" -H 'Content-Type: application/json' -d '{"name":"Продажи API","description":"Пример"}'
unset ACCESS TOKENS
```

JWT подписан, но не зашифрован. Не сохранять токены и пароли в Git и логах. Для Windows эти shell-примеры выполнять в Git Bash.

## Настройки, собственный User и N+1

`manage.py` использует `config.settings.dev`, WSGI/ASGI — `config.settings.prod`. Dev включает Debug Toolbar, prod — HTTPS-перенаправление и защищённые cookies. Проверка:

```bash
docker compose exec web python manage.py check --deploy --settings=config.settings.prod
```

Успешная проверка настроек не означает готовое production-развёртывание: текущий Compose запускает runserver, SMTP подключён к Mailpit. Упаковка production-стенда относится к следующей лабораторной.

При переходе со стандартного User на `accounts.User` уже применённая миграция `admin.0001_initial` стала зависеть от ещё не выполненной `accounts.0001_initial`. Смена `AUTH_USER_MODEL` сама не переносит пользователей и связи; поэтому Django сообщил `InconsistentMigrationHistory`. В ЛР №3 сотрудники и отделы были сохранены в fixture, учебная база пересоздана, миграции применены заново, сотрудники восстановлены, суперпользователь создан заново. Fixture employees не сохраняет остальные данные и аккаунты. Это объяснение выполненного этапа, **не инструкция повторно удалять текущую базу**. В системе с ценными данными нужен отдельный план миграции; собственный User лучше создавать до первых миграций.

Замер SQL из ЛР №3 на `/api/employees/`: **18 запросов до, 4 после**. `department_name` вызывал отдельную загрузку отдела каждого сотрудника; `select_related("department")` заменил её JOIN. Это исторический замер всей страницы через Debug Toolbar, а не обещание такого же числа после добавления JWT и пагинации. Для витрины отдельный тест проверяет постоянные 4 запроса без N+1.

Логи employees/orders идут в консоль; уровень меняется через `LOG_LEVEL`. Создание сотрудника пишется с INFO, удаление — WARNING. SQL-логирование в dev оставлено выключенным; Debug Toolbar подключён только в dev.

## Тесты, покрытие и качество кода

```bash
docker compose exec web python manage.py test --settings=config.settings.test
docker compose exec web coverage run manage.py test --settings=config.settings.test
docker compose exec web coverage report
docker compose exec web coverage html
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web ruff check .
docker compose exec web ruff format --check .
```

Тесты требуют PostgreSQL; Django создаёт и удаляет отдельную тестовую базу. Test-настройки наследуют base без Debug Toolbar и используют MD5PasswordHasher только для ускорения тестов. В dev/prod остаются безопасные рабочие хешеры.

Проверка 04.11.2026: **79 тестов, OK; под coverage — 4.228 с** без времени создания тестовой базы. **Общее покрытие 91% (979/1070 строк)**; orders/services.py — 97%, cart/api.py — 96%, orders/notifications.py — 100%. HTML-отчёт: `htmlcov/index.html`. Миграции, тестовые пакеты и файлы tests.py, config и manage.py исключены из измерения; `.coverage` и `htmlcov/` — из Git.

Историческое сравнение одинаковых 66 тестов в ЛР №6: 11.358 с с обычным хешером и 3.166 с с тестовым. Время зависит от компьютера и нагрузки. Дополнительно проверяются все три сценария самостоятельного задания: сбой отправки письма, ограничение PATCH остатком и запрет отмены чужого заказа. Непокрыты, среди прочего, `seed_catalog` и некоторые ветки ошибок HTML-форм; зелёные тесты не гарантируют отсутствие ошибок во всём проекте.

### Почему отмена не возвращает использование промокода

`used_count` растёт при успешном оформлении и не уменьшается при отмене. Лимит означает число успешных применений к оформленным заказам. Это сохраняет историю и исключает повторное использование ограниченного промокода через цикл «оформить → отменить». Недостаток: добросовестный покупатель тоже теряет применение после отмены. Если бизнес решит возвращать его, потребуется строго однократный возврат под блокировкой с тестами повторной и параллельной отмены.

## Разработка и Git

Для IDE и Git-хуков на компьютере:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt
pre-commit install
pre-commit run --all-files
```

Linux/macOS: активировать окружение через `source venv/bin/activate`. После исправлений хуками проверить diff, повторно добавить нужные файлы и повторить коммит.

`main` — релизы, `develop` — разработка, `feature/*` создаются от develop и возвращаются через PR. Для нового этапа: обновить develop, создать feature-ветку, внести изменения, проверить, открыть PR с описанием и шагами проверки. Слияние — **Create a merge commit**, без squash/rebase; после слияния feature-ветку удалить. `release/*` создаётся от develop, `hotfix/*` — от main; результаты обоих возвращаются в main и develop. Сообщения новых коммитов — Conventional Commits (`feat`, `fix`, `docs`, `test`, `chore`).

Исторические материалы этапов №6: [панель менеджера](docs/lab6-part5.md), [восстановление частей 2–4](docs/lab6-restoration.md). Их промежуточные числа тестов и ограничения относятся к тем этапам; текущий запуск и состояние описаны выше.
