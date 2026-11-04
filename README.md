# Corporate IS — учебный интернет-магазин

Django, PostgreSQL, REST API с JWT. Реализованы лабораторные №1–7 и **все 12**
доработок пункта 8.2, выпущенных в **1.1.0**. Текущая версия — **1.1.1** (исправление демосценария).

Покупатель ищет товары, выбирает вариант, оформляет доставку и оплачивает заказ
в учебном шлюзе. Менеджер управляет каталогом, вариантами и статусами, импортирует CSV
и смотрит отчёт продаж. Реальные платежи не выполняются.

## Быстрый запуск разработки

Нужны Git и запущенный Docker Desktop с Compose. Локальный Python не требуется.
Команды выполняются из корня репозитория; примеры рассчитаны на PowerShell.

```powershell
git clone --branch develop git@github.com:GlebNagornikov/corporate-is-lab1.git
cd corporate-is-lab1
Copy-Item .env.example .env
```

В новом `.env` заменить SECRET_KEY, POSTGRES_PASSWORD и пароль в DATABASE_URL.
Значения SECRET_KEY и PAYMENT_WEBHOOK_SECRET можно сгенерировать так:

```powershell
docker run --rm python:3.13-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Не заменять существующий `.env`: пароль в уже созданном томе PostgreSQL от этого
не изменится. В пароль внутри URL допускаются буквы, цифры, `_` и `-`; остальные
спецсимволы требуют URL-кодирования. Значения с `$` заключать в одинарные кавычки.

```powershell
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_catalog --images
docker compose exec web python manage.py setup_demo --password "DemoShop2026!"
```

`seed_catalog` создаёт 30 товаров и картинки; повторный запуск **обновляет** цены и
остатки демокаталога. Для своей базы этот шаг пропустить. `setup_demo` добавляет пять
отдельных DEMO-товаров с вариантами, характеристиками и фото, промокод CHECKPOINT10,
покупателя и менеджера. Повторный запуск не меняет существующие пароли; для явного
сброса есть `--reset-password`. Аккаунт с несовпадающей ролью не изменяется.

| Аккаунт | Логин | Пароль при приведённой выше команде |
|---|---|---|
| Покупатель | buyer_demo | DemoShop2026! |
| Менеджер, staff без superuser | manager_demo | DemoShop2026! |

Это публичные **демонстрационные** реквизиты; использовать для локальной лабораторной.
Существующие аккаунты при клонировании не переносятся. Для полного администратора:
`docker compose exec web python manage.py createsuperuser`.

| Назначение | Dev | Prod |
|---|---|---|
| Магазин | http://127.0.0.1:8000/ | https://localhost/ |
| Админка | http://127.0.0.1:8000/admin/ | https://localhost/admin/ |
| Swagger API | http://127.0.0.1:8000/api/docs/ | https://localhost/api/docs/ (только staff) |
| Схема OpenAPI | http://127.0.0.1:8000/api/schema/ | https://localhost/api/schema/ (только staff) |
| Mailpit | http://localhost:8025/ | http://localhost:8026/ |

Выход выполняется POST-формой. Для dev после работы с HTTPS использовать 127.0.0.1:
HSTS у localhost действует на все порты ещё 60 секунд.

## Прод-подобный стенд

Чистый checkout релиза исключает незавершённые локальные изменения из образа.
На новом компьютере можно клонировать сразу тег `v1.1.1`. Для существующей рабочей
папки с изменениями использовать отдельный `git worktree add --detach <папка> v1.1.1`.

```powershell
Copy-Item .env.prod.example .env.prod
New-Item -ItemType Directory -Force nginx/certs
& 'C:/Program Files/Git/usr/bin/openssl.exe' req -x509 -nodes -newkey rsa:2048 -days 365 -keyout nginx/certs/localhost.key -out nginx/certs/localhost.crt -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
```

В `.env.prod` установить APP_VERSION=1.1.1, отдельные случайные SECRET_KEY,
PAYMENT_WEBHOOK_SECRET и POSTGRES_PASSWORD. Prod использует собственную БД shop.
В Git Bash вместо пути к openssl использовать `openssl`; при преобразовании пути
заменить `-subj '/CN=localhost'` на `-subj '//CN=localhost'`.

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py seed_catalog --images
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py setup_demo --password "DemoShop2026!"
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py createsuperuser
```

Миграции выполняет отдельный сервис: **db healthy → migrate Exited (0) → web healthy → nginx**.
Worker также ждёт миграции и Redis. В браузере подтвердить исключение для собственного
самоподписанного сертификата. Статика и media раздаются nginx из отдельных томов.

Prod-образ содержит Gunicorn и зависимости base, работает от app (UID 1000), не содержит
Debug Toolbar, Ruff и Coverage. Код копируется в образ, bind mount исходников отсутствует.
Файл Dockerfile имеет четыре этапа: base, dev, builder, prod. Dev использует target dev.

## Переменные окружения

Шаблоны: [.env.example](.env.example), [.env.prod.example](.env.prod.example).
Настоящие файлы, сертификаты, ключи и backups не коммитятся и не включаются в образ.

| Переменная | Назначение |
|---|---|
| SECRET_KEY | Случайный ключ Django; отдельный для dev/prod |
| PAYMENT_WEBHOOK_SECRET | Отдельный случайный HMAC-секрет учебного платёжного шлюза |
| APP_VERSION | Prod-тег образа shop-web; текущий релиз 1.1.1 |
| POSTGRES_DB / USER / PASSWORD | Учётные данные отдельной БД окружения |
| POSTGRES_HOST_PORT | Dev-порт PostgreSQL, 5432; prod БД наружу не публикуется |
| DATABASE_URL | Для manage.py с хоста; Compose устанавливает внутренний адрес db |
| DB_CONN_MAX_AGE | Повторное использование соединения БД, 60 секунд |
| ALLOWED_HOSTS | Хосты prod без схемы и порта; localhost |
| CSRF_TRUSTED_ORIGINS | HTTPS-источники prod; https://localhost |
| SITE_URL | Абсолютные ссылки писем; dev http://127.0.0.1:8000, prod https://localhost |
| REDIS_CACHE_URL | Redis DB1, кэш каталога; ошибки соединения не ломают витрину |
| CELERY_BROKER_URL | Redis DB0, очередь писем; AOF и noeviction |
| REDIS_THROTTLE_URL | Redis DB2, ограничения API; при отказе локальный лимит каждого процесса |
| EMAIL_HOST / EMAIL_PORT | SMTP; Compose задаёт mailpit:1025 |
| DEFAULT_FROM_EMAIL | Отправитель писем |
| GUNICORN_WORKERS | Число prod-worker процессов, 3 |
| LOG_LEVEL | Уровень JSON-логов приложений, INFO |
| JWT_ACCESS_MINUTES / JWT_REFRESH_DAYS | Сроки access/refresh, 15 минут / 7 дней |
| DJANGO_SETTINGS_MODULE | manage.py по умолчанию dev, prod-образ и WSGI — prod |

## Все индивидуальные доработки и проверка

Каждая реализована отдельной feature-веткой и PR в develop; бизнес-правила вынесены
в сервисы/модели. У каждой не менее трёх тестов, включая негативные сценарии.

| № | Доработка | Как проверить вручную | Тесты |
|---|---|---|---|
| 1 | Избранное | Войти, добавить из каталога/карточки дважды; открыть «Избранное». Снять товар с продажи — появляется отметка. Другой пользователь не видит список. | catalog.tests.test_wishlist |
| 2 | Сравнение | У гостя выбрать четыре DEMO-товара. Пятый и товар другой корневой категории отклоняются; разные характеристики подсвечены. | catalog.tests.test_comparison |
| 3 | Варианты | У DEMO-товара выбрать S и L с разными ценами/остатками в admin. В корзине две строки; заказ сохраняет названия и цены; отмена возвращает соответствующие остатки. | catalog.tests.test_variants |
| 4 | Поступление | Открыть DEMO-5 с нулевым остатком, оставить email. В admin увеличить остаток одного варианта: приходит одно письмо. Повторное увеличение не рассылает снова. | catalog.tests.test_restock |
| 5 | CSV-импорт | Команда import_products examples/products.csv --dry-run, затем без флага. Повторить — дубля нет. Добавить отрицательную цену/неизвестную категорию — весь файл отклонён с номерами строк. В admin товаров есть «Импорт CSV». | catalog.tests.test_importing |
| 6 | Отчёт | Под manager_demo открыть «Отчёт», выбрать период и скачать CSV. Покупателю 403. Выручка исключает отменённые заказы; SQL-запросов всегда шесть. | orders.tests.test_reporting |
| 7 | Адреса | В «Адресах» создать два адреса и сменить основной. Выбрать при заказе, потом изменить адрес в книге: старый заказ не меняется. Чужой адрес недоступен. | accounts.test_addresses |
| 8 | Оплата | Оформить заказ → «Оплатить» → учебный успех/отказ. При успехе paid, далее менеджер confirmed/shipped/delivered. Повторный webhook не дублирует переход; неверная HMAC даёт 403. Покупатель paid не отменяет. | orders.tests.test_payments |
| 9 | Redis-кэш | Повторно открыть карточку, посмотреть SQL в Debug Toolbar. Изменить цену/отзыв — сразу новое значение. Остановить redis: HTML-каталог продолжает работать. | catalog.tests.test_caching |
| 10 | Celery | Остановить mailpit, оформить заказ: ответ приходит без ожидания SMTP. Запустить mailpit, дождаться письма; смотреть logs worker. Для повторной постановки сохранённых писем — dispatch_notifications. | orders.tests.test_tasks |
| 11 | API docs и лимиты | Открыть /api/docs/. В prod доступ есть только у staff. 11-я попытка получения токена в минуту даёт 429 и Retry-After. spectacular --validate --fail-on-warn проходит. | config.test_api_docs |
| 12 | JSON/request-id | Взять X-Request-ID ответа; найти его в logs nginx web, для писем также worker. Запись заказа содержит order_id. | config.test_logging |

Пример запуска отдельного набора:

```powershell
docker compose exec web python manage.py test catalog.tests.test_variants --settings=config.settings.test
```

Ключевые правила совместимости: остатки custom-вариантов суммируются для витрины,
цена товара — минимальная активного варианта; стандартный вариант поддерживает обычные
товары. Подписка сообщает о появлении любого варианта. Импорт поддерживает дополнительные
variant_sku/variant_name/variant_price/variant_stock и attributes (JSON).
Избранное/сравнение относятся к товару, а покупка — к выбранному варианту.
Отчёт считает неотменённые заказы независимо от оплаты; сумма включает скидку и доставку,
топ товаров считается по стоимости позиций до скидки заказа и доставки.
Кэш хранит только общие данные, без чужих форм, CSRF и пользовательских признаков.

## Заказы и REST API

Новый заказ резервирует склад в транзакции с блокировкой корзины, товаров и вариантов.
Сохраняются снимки товара, варианта, цены и адреса. Курьер требует адрес; доставка 500 ₽,
бесплатно от 5000 ₽ после скидки; самовывоз бесплатен. Гостевая корзина объединяется при входе.
Телефон нормализуется к +7XXXXXXXXXX. Письма ставятся в очередь после commit.

Статусы: **new → paid → confirmed → shipped → delivered**. Покупатель отменяет только new;
менеджер также отменяет paid/confirmed с возвратом остатков. Webhook принимает HMAC-SHA256
в X-Payment-Signature от точных байтов JSON. Каждая попытка записана в Payment.

| API | Назначение |
|---|---|
| POST /api/auth/token/; /api/auth/token/refresh/ | JWT access/refresh |
| GET /api/catalog/categories/; /api/catalog/products/ | Каталог, фильтры и поиск; детали по slug |
| GET/POST /api/catalog/products/<slug>/reviews/ | Отзывы; публикация требует входа |
| GET /api/cart/; POST /api/cart/items/ | Корзина; добавление product, variant, quantity |
| PATCH/DELETE /api/cart/items/<product_id>/?variant=<id> | Изменить/удалить конкретный вариант |
| GET/POST /api/orders/; GET /api/orders/<id>/ | Свои заказы / оформление; address_book — ID своего адреса |
| POST /api/orders/<id>/cancel/; /status/ | Отмена покупателем / смена статуса менеджером |
| GET/POST/DELETE /api/wishlist/ | Только своё избранное; DELETE принимает product |
| DELETE /api/wishlist/<product_id>/ | Удалить своё избранное |
| POST /payments/webhook/ | Подписанный результат оплаты; JWT не требуется |
| /api/employees/; /api/departments/ | CRUD с соответствующими правами Django |

Аноним на закрытом API получает 401, вошедший без прав — 403, чужой заказ — 404.
Непустой отдел при удалении — 409. JWT проверяется раньше сессии; сессия требует CSRF.
Параметры каталога: q, category (slug), price_min/max, in_stock, on_sale, rating_min,
ordering, page. Поиск использует PostgreSQL russian/pg_trgm, пример опечатки: «наушнеки».

## Автоматические проверки сдачи

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web coverage run manage.py test --settings=config.settings.test
docker compose exec web coverage report --fail-under=80
docker compose exec web python manage.py spectacular --validate --fail-on-warn --settings=config.settings.test
uvx --from pre-commit==4.7.0 pre-commit run --all-files
```

Последняя команда запускается на компьютере с Git и uv; pre-commit в контейнере без
Git не используется. Ruff можно отдельно проверить `docker compose exec web ruff check .`.
Тесты используют PostgreSQL, быстрый тестовый хешер, LocMemCache и синхронный Celery.
Результаты контрольной проверки: [docs/checkpoint-verification.md](docs/checkpoint-verification.md).

Prod:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod ps -a
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py check --deploy
curl.exe -I http://localhost/
curl.exe -k https://localhost/healthz/
curl.exe -kI https://localhost/static/admin/css/base.css
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python -c "import debug_toolbar"
```

Ожидается 301 на HTTPS, healthz версии 1.1.1, CSS 200; импорт debug_toolbar должен
завершиться ModuleNotFoundError. Для автоматической HTTPS-покупки с локальным Python:
`python scripts/check_prod.py --expected-version 1.1.1 --purchase`.
Она создаёт нового тестового покупателя и заказ, списывает одну единицу товара.

## История выпусков, откат и данные

v1.0.0 — первый релиз; v1.0.1 — нормализация телефонов; v1.1.0 — все 12 доработок.
Каждый тег аннотированный, находится на merge-коммите main, версия кода совпадает с тегом.
Feature PR идут в develop; релиз — release/1.1.0 → main и обратно в develop.
Подробности выпусков: [CHANGELOG](CHANGELOG.md), [лабораторная №7](docs/lab7-prod-stack.md).

Для отката поменять APP_VERSION на ранее собранный тег и запустить **без сборки**:
`docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build`.
Вернуть 1.1.1 той же командой. Выпущенные теги образов не пересобирать.
Если nginx сохранил старый адрес контейнера и отвечает 502, перезапустить nginx.
Откат кода не откатывает схему/данные; 1.0.1 не понимает новые варианты и paid, поэтому
для проверки отката использовать healthz, а для реальной работы вернуть 1.1.1.

Резервная копия PostgreSQL (PowerShell):

```powershell
New-Item -ItemType Directory -Force backups
docker compose -f docker-compose.prod.yml --env-file .env.prod exec db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/shop.dump'
docker compose -f docker-compose.prod.yml --env-file .env.prod cp db:/tmp/shop.dump backups/shop.dump
```

Не перенаправлять бинарный pg_dump через `>` в PowerShell 5. Media, .env.prod и
сертификаты сохраняются отдельно. Полный цикл восстановления проверен в части 5.

Остановка: `docker compose down` или prod-команда с теми же -f/--env-file и down.
**Не добавлять -v: это удаляет тома с БД, Redis и изображениями.** Dev и prod используют
разные проекты/тома. Изменение исходников не требует dev-пересборки; изменение зависимостей
требует `up -d --build`. При запуске новых worker после изменения кода перезапустить worker.

Hotfix 1.1.1 устраняет конфликт старого STUDENT10 с демосценарием: setup_demo создаёт
отдельный CHECKPOINT10, а scripts/check_checkpoint.py поддерживает --promo-code.
Старые промокоды, их сроки и скидки не перезаписываются. Перед повторной проверкой
существующего стенда выполнить setup_demo ещё раз с прежним демопаролем.
