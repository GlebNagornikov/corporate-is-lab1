# Corporate IS — учебный интернет-магазин

Django, PostgreSQL, REST API с JWT. В версии **1.1.0** выпущены **все 12** доработок
пункта 8.2. В версии **1.2.0** на HTTPS-стенде работает витрина React.

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
docker compose exec web python manage.py seed_demo --password "DemoShop2026!"
```

`seed_demo` загружает 21 конкретное англоязычное печатное издание с локальными обложками.
Повторный запуск сохраняет существующие пароли, цены, остатки и фотографии. На старой
базе сначала просмотрите список учебных товаров командой `docker compose exec web python manage.py archive_legacy_demo`;
для архивации именно показанных известных позиций выполните её с `--apply`. Ссылки
заказов и сами товары сохраняются. Источники и условия — в [описании обложек](docs/lab11-cover-research.md).

| Аккаунт | Логин | Пароль при приведённой выше команде |
|---|---|---|
| Покупатель | buyer_demo | DemoShop2026! |
| Менеджер, staff без superuser | manager_demo | DemoShop2026! |

Это публичные **демонстрационные** реквизиты; использовать для локальной лабораторной.
Существующие аккаунты при клонировании не переносятся. Для полного администратора:
`docker compose exec web python manage.py createsuperuser`.

| Назначение | Dev | Prod |
|---|---|---|
| React-магазин | http://127.0.0.1:5173/ | https://localhost/ |
| Django-витрина | http://127.0.0.1:8000/ | — |
| Админка | http://127.0.0.1:8000/admin/ | https://localhost/admin/ |
| Swagger API | http://127.0.0.1:8000/api/docs/ | https://localhost/api/docs/ (только staff) |
| Схема OpenAPI | http://127.0.0.1:8000/api/schema/ | https://localhost/api/schema/ (только staff) |
| Mailpit | http://localhost:8025/ | http://localhost:8026/ |

Выход выполняется POST-формой. Для dev после работы с HTTPS использовать 127.0.0.1:
HSTS у localhost действует на все порты ещё 60 секунд.

### Тесты React-витрины

Из папки `frontend`:

```powershell
npm ci
npx playwright install chromium
npm run typecheck
npm run lint
npm test
npm run e2e
```

Для Playwright нужен запущенный React-магазин на `http://127.0.0.1:5173`, книги в наличии
и демо-менеджер из `seed_demo`. Адрес и реквизиты менеджера можно задать через
`E2E_BASE_URL`, `E2E_MANAGER_USERNAME` и `E2E_MANAGER_PASSWORD`.
Тесты создают отдельных покупателей и заказы в базе выбранного стенда.
При падении Playwright сохраняет трассировку в `frontend/test-results/`.

## Прод-подобный стенд

Собирайте этот стенд из текущей версии репозитория с каталогом книг. На новом компьютере
используйте тот же checkout, что и для запуска разработки. Для прежнего релиза
`v1.2.0` используйте инструкции из README самого тега.

```powershell
Copy-Item env/production.example .env.prod
New-Item -ItemType Directory -Force nginx/certs
& 'C:/Program Files/Git/usr/bin/openssl.exe' req -x509 -nodes -newkey rsa:2048 -days 365 -keyout nginx/certs/localhost.key -out nginx/certs/localhost.crt -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
```

В `.env.prod` установить `APP_VERSION=lab11`, отдельные случайные `SECRET_KEY`,
`PAYMENT_WEBHOOK_SECRET` и `POSTGRES_PASSWORD`. Отдельный тег позволяет собрать стенд
из текущего кода и сохранить образы прежнего релиза. Prod использует собственную БД `shop`.
Если `.env.prod` и том PostgreSQL уже есть, сохраните действующие реквизиты БД.
В Git Bash вместо пути к openssl использовать `openssl`; при преобразовании пути
заменить `-subj '/CN=localhost'` на `-subj '//CN=localhost'`.

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py seed_demo --password "DemoShop2026!"
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py createsuperuser
```

Миграции выполняет отдельный сервис: **db healthy → migrate Exited (0) → web healthy → nginx**.
Worker также ждёт миграции и Redis. В браузере подтвердить исключение для собственного
самоподписанного сертификата. Статика и media раздаются nginx из отдельных томов.
Образ `shop-nginx` содержит сборку витрины и конфигурацию nginx. Сертификаты подключаются при запуске.

Prod-образ содержит Gunicorn и зависимости base, работает от app (UID 1000), не содержит
Debug Toolbar, Ruff и Coverage. Код копируется в образ, bind mount исходников отсутствует.
Файл Dockerfile имеет четыре этапа: base, dev, builder, prod. Dev использует target dev.

## Переменные окружения

Шаблоны: [.env.example](.env.example), [env/production.example](env/production.example).
Настоящие файлы, сертификаты, ключи и backups не коммитятся и не включаются в образ.

| Переменная | Назначение |
|---|---|
| SECRET_KEY | Случайный ключ Django; отдельный для dev/prod |
| PAYMENT_WEBHOOK_SECRET | Отдельный случайный HMAC-секрет учебного платёжного шлюза |
| APP_VERSION | Общий тег образов `shop-web` и `shop-nginx`. Для проверки текущей версии используйте `lab11` |
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
Для сценариев с `DEMO-1`–`DEMO-5` на отдельной тестовой базе выполните
`docker compose exec web python manage.py setup_demo --password "DemoShop2026!"`.

| № | Доработка | Как проверить вручную | Тесты |
|---|---|---|---|
| 1 | Избранное | Войти, добавить из каталога/карточки дважды; открыть «Избранное». Снять товар с продажи — появляется отметка. Другой пользователь не видит список. | catalog.tests.test_wishlist |
| 2 | Сравнение | У гостя выбрать четыре DEMO-товара. Пятый и товар другой корневой категории отклоняются; разные характеристики подсвечены. | catalog.tests.test_comparison |
| 3 | Варианты | У DEMO-товара выбрать S и L с разными ценами/остатками в admin. В корзине две строки; заказ сохраняет названия и цены; отмена возвращает соответствующие остатки. | catalog.tests.test_variants |
| 4 | Поступление | Открыть DEMO-5 с нулевым остатком, оставить email. В admin увеличить остаток одного варианта: приходит одно письмо. Повторное увеличение не рассылает снова. | catalog.tests.test_restock |
| 5 | CSV-импорт | На тестовой базе после `seed_demo` выполните `docker compose exec web python manage.py import_products /app/examples/products.csv --dry-run`, затем без флага. Повторный импорт сохраняет один товар. Отрицательная цена или неизвестная категория приводят к отклонению файла с номерами строк. В admin товаров есть «Импорт CSV». | catalog.tests.test_importing |
| 6 | Отчёт | Под manager_demo открыть «Панель менеджера → Заказы → Отчёт по продажам», выбрать период и скачать CSV. Покупателю 403. Выручка исключает отменённые заказы. SQL-запросов всегда шесть. | orders.tests.test_reporting |
| 7 | Адреса | Создать два адреса. При оформлении основной уже в поле «Адрес доставки». Стрелка в поле позволяет выбрать другой адрес. Изменение в адресной книге не меняет оформленный заказ. Чужой адрес недоступен. | accounts.test_addresses, orders.tests.test_views |
| 8 | Оплата | Оформить заказ → «Оплатить» → учебный успех/отказ. При успехе paid, далее менеджер confirmed/shipped/delivered. Повторный webhook не дублирует переход; неверная HMAC даёт 403. Покупатель paid не отменяет. | orders.tests.test_payments |
| 9 | Redis-кэш | Повторно открыть карточку и посмотреть SQL в Debug Toolbar. Изменить цену или отзыв и обновить страницу товара. Новое значение видно при следующем запросе. Остановить Redis и проверить работу HTML-каталога. | catalog.tests.test_caching |
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
binding (hardcover/paperback), ordering, page. Поиск по названию и автору работает
без учёта регистра. Для `война мирво` PostgreSQL предлагает «Война миров / The War of the Worlds».

## Автоматические проверки сдачи

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web coverage run --rcfile=/app/pyproject.toml manage.py test --settings=config.settings.test
docker compose exec web coverage report --rcfile=/app/pyproject.toml --fail-under=80
docker compose exec web python manage.py spectacular --validate --fail-on-warn --settings=config.settings.test
uvx --from pre-commit==4.7.0 pre-commit run --all-files
```

Последняя команда запускается на компьютере с Git и uv; pre-commit в контейнере без
Git не используется. Ruff можно отдельно проверить `docker compose exec -w /app web ruff check backend scripts docker`.
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

Ожидаются редирект 301 на HTTPS, значение `APP_VERSION` в `/healthz/` и подвале витрины,
а также ответ 200 для CSS.
Импорт `debug_toolbar` завершается `ModuleNotFoundError`.

Сквозные сценарии на стенде создают тестовых покупателей и заказы. После `npm ci --prefix frontend`
и `npx --prefix frontend playwright install chromium` запустите их в PowerShell:

```powershell
$env:E2E_BASE_URL = 'https://localhost'
npm --prefix frontend run e2e
```

## История выпусков, откат и данные

v1.0.0 — первый релиз, v1.0.1 — нормализация телефонов, v1.1.0 — все 12 доработок.
v1.1.1 исправляет демосценарий, v1.1.2 — витрину, оформление заказа и отчёт.
v1.2.0 переносит витрину React на HTTPS-стенд.
Каждый тег аннотированный, находится на merge-коммите main, версия кода совпадает с тегом.
Feature PR идут в develop, релизная ветка сливается в main, затем main сливается обратно в develop.
Подробности выпусков: [CHANGELOG](CHANGELOG.md), [лабораторная №7](docs/lab7-prod-stack.md).

При откате переключитесь на Git-тег нужной версии и задайте соответствующий `APP_VERSION`.
Так Compose получит конфигурацию того же выпуска. Затем запустите
`docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build`, если его образы уже собраны.
Для возврата повторите те же шаги с `v1.2.0`. Откат кода сохраняет текущую схему и данные PostgreSQL.

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

## Итоговый проект: рабочий вариант КТ1

Предметная область — независимый книжный магазин «Книжная полка». Зачётный вариант
М1 «Отзывы и рейтинг» и официальный шифр требуют подтверждения преподавателя;
М2–М4 также запланированы. Демокаталог содержит книжные издания; прежние товары сохраняются до явной архивации. Новые функции появятся на следующих шагах. В репозитории Django находится
в `backend/`, React — в `frontend/`; общие Compose и стенд остаются в корне.
Основные зависимости: `pip install -r backend/requirements.txt`; для разработки —
`pip install -r backend/requirements/dev.txt`. Локально запускать из корня командой
`python backend/manage.py runserver`; медиа и `.env` остаются в корне.

Роли: гость просматривает каталог, покупатель управляет своей корзиной и заказами,
менеджер магазина работает с заказами и каталогом согласно правам Django.

Сценарии: 1) поиск и фильтрация каталога; 2) просмотр карточки и вариантов;
3) регистрация и вход; 4) добавление в корзину; 5) перенос гостевой корзины при
входе; 6) оформление доставки и применение промокода; 7) учебная оплата;
8) просмотр и отмена своих заказов; 9) смена статуса менеджером; 10) управление
каталогом и отчётом в Django admin/существующих серверных страницах. React-кабинет
каталога и отчёты запланированы, сейчас React-кабинет поддерживает заказы.

Текущие API перечислены выше в разделе «Заказы и REST API». Планируемые адреса (контракт может
уточняться при реализации): `/api/manager/` — операции сотрудников;
`POST /api/promo/check/` — проверка промокода; уведомления о поступлении и SSE
заказов — ещё не реализованы, их окончательные адреса не утверждены.

Примеры тел запросов существующего API (цены рассчитывает сервер):

```json
{"username":"buyer_demo","password":"DemoShop2026!"}
```

```json
{"product":1,"variant":null,"quantity":1}
```

```json
{"status":"confirmed"}
```
