# Книжная полка — независимый книжный магазин

Django, PostgreSQL, REST API с JWT. В версии **1.1.0** выпущены **все 12** доработок
пункта 8.2. В версии **1.2.0** на HTTPS-стенде работает витрина React.

Покупатель ищет товары, выбирает вариант, оформляет доставку и оплачивает заказ
в учебном шлюзе. Менеджер управляет каталогом, вариантами и статусами, импортирует книги из JSON
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
заказов и сами товары сохраняются. В меню витрины остаются категории с активными товарами
и их родительские категории. Источники и условия — в [описании обложек](docs/lab11-cover-research.md).

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

Для работы с текущим кодом используйте dev-адрес `http://127.0.0.1:5173` и команды
`docker compose exec web …` из этого каталога. Фронтенд проксирует API в `web` проекта
`corporate-is-lab1`. HTTPS-стенд использует отдельно собранный релиз и свой том PostgreSQL,
поэтому аккаунты и права зависят от выбранного стенда. Список проектов показывает
`docker compose ls -a`, а контейнеры и порты текущего проекта — `docker compose ps`.

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

При оформлении действует лимит в 5 экземпляров на издание суммарно по всем вариантам.
Сервер отдельно проверяет актуальный остаток. В обоих случаях при отказе API возвращает
`400` с объяснением в `detail`, а корзина сохраняется.

Статусы: **new → paid → confirmed → shipped → delivered**. Покупатель отменяет только new;
менеджер также отменяет paid/confirmed с возвратом остатков. Webhook принимает HMAC-SHA256
в X-Payment-Signature от точных байтов JSON. Каждая попытка записана в Payment.

| API | Назначение |
|---|---|
| POST /api/auth/token/; /api/auth/token/refresh/ | JWT access/refresh |
| GET /api/catalog/categories/; /api/catalog/products/ | Каталог, фильтры и поиск; детали по slug |
| GET /api/catalog/products/<slug>/reviews/?page=1 | Публичные одобренные отзывы по 5 на страницу |
| POST /api/catalog/products/<slug>/reviews/ | Покупатель с доставленным заказом на книгу отправляет один отзыв на модерацию |
| GET /api/catalog/products/<slug>/review-eligibility/ | Личное право на отзыв и состояние своего отзыва |
| GET /api/manager/reviews/ | Очередь отзывов для сотрудника с правом просмотра |
| POST /api/manager/reviews/<id>/moderate/ | Одобрение или отклонение отзыва сотрудником с правом изменения |
| GET /api/cart/; POST /api/cart/items/ | Корзина; добавление product, variant, quantity |
| PATCH/DELETE /api/cart/items/<product_id>/?variant=<id> | Изменить/удалить конкретный вариант |
| GET/POST /api/orders/; GET /api/orders/<id>/ | Свои заказы / оформление; address_book — ID своего адреса |
| POST /api/orders/<id>/cancel/; /status/ | Отмена покупателем / смена статуса менеджером |
| POST /api/orders/<id>/simulate-payment/ | Учебная оплата владельцем нового заказа |
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

Для лабораторной №11 см. [протокол приёмки шага 12](docs/lab11-step12-acceptance.md)
с командами, негативными сценариями и отчётами Lighthouse.

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

## Итоговый проект «Книжная полка»

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
8) просмотр и отмена своих заказов; 9) фильтрация, просмотр и обработка заказов в кабинете;
10) создание, редактирование и публикация книг в кабинете. Отчёт в React запланирован в М4.

Основные API перечислены выше в разделе «Заказы и REST API». Для кабинета используйте
Bearer-токен сотрудника. `me.is_manager` соответствует праву `orders.change_order`.
Служебные операции дополнительно проверяют права на нужную модель. Гость получает 401,
покупатель получает 403. Чужой заказ в покупательском API возвращает 404.

| Метод | Адрес | Дополнительные права | Назначение |
| --- | --- | --- | --- |
| GET | `/api/manager/orders/` | `orders.view_order` | Список заказов, `status` и `page`. |
| GET | `/api/manager/orders/{id}/` | `orders.view_order` | Заказ, контакты и история. |
| POST | `/api/manager/orders/{id}/status/` | `orders.view_order` | Переход статуса из `allowed_transitions`. При отмене укажите `comment`. |
| GET | `/api/manager/catalog/` | `catalog.view_product` | Все карточки, включая скрытые. `q` ищет по названию, автору, SKU и ISBN, `page` задаёт страницу. |
| GET | `/api/manager/catalog/{id}/` | `catalog.view_product` | Карточка сотрудника и её складские варианты. |
| POST | `/api/manager/catalog/` | `catalog.add_product`, `catalog.view_category` | Создать издание через multipart. По умолчанию книга скрыта. |
| PATCH | `/api/manager/catalog/{id}/` | `catalog.view_product`, `catalog.change_product`, `catalog.view_category` | Обновить карточку через multipart. |
| DELETE | `/api/manager/catalog/{id}/` | `catalog.view_product`, `catalog.delete_product` | Удалить книгу. Для книги из истории заказов возвращает 409. |
| POST | `/api/manager/catalog/import-json/` | `catalog.view_category`, `catalog.add_product`, `catalog.change_product` | Проверить или импортировать файл с JSON-массивом книг в UTF-8 через multipart. |
| PATCH | `/api/manager/catalog/{id}/variants/{variant_id}/` | `catalog.view_product`, `catalog.change_productvariant` | Изменить цену, остаток и активность существующего складского варианта. |
| GET | `/api/manager/categories/` | `catalog.view_category` | Жанры для формы, включая пустые. Раздел «Книги» в список жанров не входит. |
| POST | `/api/manager/categories/` | `catalog.view_category`, `catalog.add_category` | Создать жанр по полю `name`. Он сразу доступен в форме книги. |

У книги сохраняются SKU и URL. Поле `image` принимает декодируемые JPEG и PNG до 5 МБ
и 20 млн пикселей. При сохранении без файла остаётся прежняя обложка. Для карточки со
складскими вариантами витрина берёт минимальную цену и суммарный остаток активных вариантов.
ISBN-13 можно вводить с дефисами или пробелами. API сохраняет 13 цифр и проверяет контрольную цифру.
Ошибки формы возвращаются как массивы сообщений по именам полей. Общая ошибка приходит в `detail`.
Прежний адрес смены статуса `POST /api/orders/{id}/status/` также доступен.
Публичный `GET /api/catalog/editorial/` возвращает подборку «Выбор редакции» независимо от страниц каталога.

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

### Приёмка кабинета сотрудника на КТ3

1. На тестовой базе запустите `docker compose up -d`, примените миграции и выполните
   `docker compose exec web python manage.py seed_demo --password "DemoShop2026!"`.
   Миграция `orders.0005_manager_catalog_permissions` добавляет существующей группе менеджеров
   права на создание жанров и удаление книг.
2. Под `buyer_demo` откройте [витрину](http://127.0.0.1:5173/catalog), положите книгу в корзину,
   оформите заказ и на его странице нажмите «Оплатить» → «Успех». Запомните номер.
   В другом профиле войдите как `manager_demo` и откройте
   [оплаченные заказы](http://127.0.0.1:5173/manager/orders?status=paid). Подтвердите заказ
   и переключите фильтр на «Подтверждён». Клик по номеру открывает контакты и историю.
3. В кабинете откройте [форму новой книги](http://127.0.0.1:5173/manager/catalog/new).
   Выберите жанр или создайте его кнопкой «Добавить жанр». Заполните поля, укажите уникальный
   адрес `proba-kt3` и уникальный SKU. Загрузите PNG или JPEG
   и проверьте предпросмотр. Сохраните черновик и найдите его по SKU в
   [каталоге сотрудника](http://127.0.0.1:5173/manager/catalog). Откройте карточку, измените цену
   и остаток, отметьте «Показывать на витрине» и сохраните. Откройте
   [карточку на витрине](http://127.0.0.1:5173/products/proba-kt3). Снимите отметку в кабинете
   и повторите открытие публичной ссылки. Витрина покажет «Не найдено».
4. Прикрепите к форме текстовый файл с расширением `.png`. Сервер вернёт 400, поле покажет
   ошибку, данные книги останутся прежними. В профиле покупателя откройте
   [каталог сотрудника](http://127.0.0.1:5173/manager/catalog). Появится «Нет доступа».
   Контракты и коды ответов доступны в [Swagger](http://127.0.0.1:8000/api/docs/).
5. Откройте [импорт книг](http://127.0.0.1:5173/manager/catalog/import), скачайте шаблон
   и укажите собственные SKU и адреса. Подставьте код жанра из списка на странице.
   Нажмите «Проверить JSON». Книги появятся в каталоге после «Импортировать книги».
   Повторный импорт обновляет карточки по SKU. Ошибка в любой записи отклоняет весь файл.
   Для обновления достаточно объекта с `sku` и меняемыми полями, например
   `[{"sku":"BOOK-JSON-001","stock":12,"old_price":null}]`.
6. Откройте карточку импортированной книги в каталоге сотрудника и нажмите «Удалить книгу».
   Карточка исчезнет из каталога, если книги нет ни в одном заказе. Ссылка из любого заказа,
   включая отменённый, блокирует удаление с ответом 409. Чтобы закрыть новые продажи,
   снимите отметку «Показывать на витрине». Существующие заказы остаются доступны для обработки.

Для проверок с отдельной базой выполните `npm --prefix frontend run e2e -- manager-catalog.spec.ts orders.spec.ts`.
Для API выполните `docker compose exec web python manage.py test catalog.tests.test_manager_api orders.tests.test_api --settings=config.settings.test`.

### Приёмка М1 · Отзывы и рейтинг

На учебной базе подготовьте каталог, доставленный заказ для `buyer_demo` и отзывы для модерации.
Команда М1 печатает ссылку на заказ. При повторном запуске она сохраняет существующие заказы
и решения по отзывам.

```powershell
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo --password "DemoShop2026!"
docker compose exec web python manage.py seed_review_demo
```

1. Гостем откройте [«Войну миров»](http://127.0.0.1:5173/products/war-of-worlds-1898).
   На чистом наборе в списке пять одобренных отзывов. «Показать ещё» добавляет шестой.
   После входа под новым покупателем без доставленной покупки карточка объясняет, когда станет
   доступен отзыв.
2. Войдите как [buyer_demo](http://127.0.0.1:5173/login?next=%2Forders) и откройте
   доставленный заказ. Перейдите на карточку книги. Выберите оценку стрелками, перейдите
   клавишей Tab к тексту и отправьте отзыв. Появится «Ваш отзыв ожидает модерации»,
   публичные оценки и список останутся прежними.
3. В другом профиле войдите как [manager_demo](http://127.0.0.1:5173/login?next=%2Fmanager%2Freviews).
   В [очереди](http://127.0.0.1:5173/manager/reviews) одобрите отзыв покупателя и отклоните один
   из отзывов «Демо М1». Обе строки сразу исчезнут. Обновите карточку в профиле покупателя.
   Одобренный отзыв войдёт в список и среднюю оценку, отклонённый останется скрыт.
4. В [Swagger](http://127.0.0.1:8000/api/docs/) получите токен покупателя через
   `POST /api/auth/token/` и авторизуйтесь с этим access-токеном. Отправьте
   `{"rating":5,"text":"Проверка"}` в `POST /api/catalog/products/{slug}/reviews/`
   со значением `war-of-worlds-1898`. Без доставленной покупки или при повторе получите 400
   с объяснением. `GET /api/manager/reviews/` с токеном покупателя вернёт 403, без токена — 401.
   Выйдите и войдите другим покупателем. Карточка проверит право для нового аккаунта.

Миграция `catalog.0011_review_status` переносит ранее опубликованные отзывы в одобренные,
а ранее скрытые — в отклонённые. Рейтинг учитывает только одобренные отзывы.
Для автоматической проверки используйте `npm --prefix frontend run e2e -- reviews.spec.ts`
на тестовом стенде с каталогом и менеджером из `seed_demo`.

### Приёмка М2 · Промокоды и скидки

В dev запустите `docker compose up -d` и примените миграции командой
`docker compose exec web python manage.py migrate`. Для пустой базы загрузите книги и
демоаккаунты командой `seed_demo`, как описано выше.

1. Войдите сотрудником в [«Промокоды»](http://127.0.0.1:5173/manager/promos).
   Создайте два кода со скидкой 10%, порогом 1000 ₽, текущим периодом действия и лимитом
   по одному использованию. У обоих счётчик `0 / 1`.
2. В отдельном профиле гостем добавьте в [каталоге](http://127.0.0.1:5173/catalog)
   книги на сумму от 1000 ₽. В [корзине](http://127.0.0.1:5173/cart) примените первый код
   и обновите страницу. Войдите покупателем и повторно откройте корзину. Гостевой код
   переносится в корзину покупателя при отсутствии сохранённого кода. При конфликте
   сохраняется код серверной корзины. Уменьшите сумму ниже порога, затем верните прежнее
   количество. Появится причина неприменимости, затем восстановится скидка.
3. Перейдите к [оформлению](http://127.0.0.1:5173/checkout) и подтвердите заказ.
   В заказе отображается скидка, корзина очищается. После обновления списка у сотрудника
   счётчик первого кода `1 / 1`. Проверьте письмо о заказе в [Mailpit](http://127.0.0.1:8025/).
4. Снова соберите корзину от 1000 ₽. Первый код отклоняется с сообщением об исчерпанном
   лимите. Примените второй, откройте оформление и деактивируйте его из профиля
   сотрудника. Отправка уже открытой формы вернёт 400 с причиной. Корзина, остатки,
   список заказов и счётчик второго кода останутся прежними. В корзине можно снять код
   и продолжить оформление.

В [Swagger](http://127.0.0.1:8000/api/docs/) запрос `POST /api/promo/check/` с телом
`{"code":"BOOK10","subtotal":"1000.00"}` проверяет код гостя по переданной сумме,
а покупателя — по его корзине. Ответ содержит `discount`, `total` и `reason`.
Проверка не расходует лимит. `PATCH /api/cart/promo/` сохраняет код покупателя, пустое
значение `promo_code` снимает его. При оформлении явное значение `promo_code` сохраняет
приоритет для существующих клиентов API. Если поле пропущено, применяется код корзины.
Сотрудник использует `GET/POST /api/manager/promos/` и `POST /api/manager/promos/{id}/deactivate/`.
Промокоды также доступны в [Django admin](http://127.0.0.1:8000/admin/orders/promocode/).

Автоматическая проверка М2

```powershell
docker compose exec web python manage.py test orders.tests.test_promos --settings=config.settings.test
npm --prefix frontend run e2e -- promos.spec.ts
```

## Отчёт о продажах (М4)

Войдите как `manager_demo` и откройте [«Отчёты»](http://127.0.0.1:5173/manager/reports).
Период по умолчанию охватывает сегодня и 29 предыдущих календарных дней. Обе границы
включительны и относятся к дате оформления заказа в часовом поясе магазина
(`Asia/Novosibirsk`). Параметры `start` и `end` в адресе позволяют открыть тот же отчёт
в новой вкладке.

- Выручка — сумма итогов всех заказов за период, кроме отменённых, с учётом скидок и
  доставки. Средний чек делит эту сумму на число тех же заказов. Диаграмма статусов
  включает все заказы, в том числе отменённые.
- В таблицу входят до 10 изданий с книжными метаданными по числу экземпляров в заказах без
  отменённых. Стоимость позиций считается по сохранённым ценам и количеству, до скидки на
  заказ и без доставки. Заголовки столбцов меняют порядок строк. CSV содержит также отдельный
  топ по стоимости.
- `GET /api/manager/reports/sales/` отдаёт JSON, а `GET /api/manager/reports/sales/csv/` —
  CSV в UTF-8. Оба запроса принимают `start` и `end` в формате `ГГГГ-ММ-ДД` и требуют
  Bearer-токен сотрудника с правом просмотра заказов.

Для ручной проверки оформите контрольный заказ, выберите день его оформления и сравните
выручку, статус и число экземпляров с JSON в Network и файлом из кнопки «Скачать CSV».
Повторите с пустым периодом и с началом позже конца. Откройте тот же адрес в профиле
покупателя. React покажет «Нет доступа», оба API вернут 403. Запросы без Bearer возвращают 401.

При сборке Vite основной чанк вырос с 380,23 до 381,52 кБ (с 118,39 до 118,88 кБ gzip).
JavaScript страницы отчёта весит 3,85 кБ (1,71 кБ gzip), отдельный чанк `ReportCharts` —
3,27 кБ (1,46 кБ gzip). В Network чанк графиков появляется после открытия отчёта с заказами.
На странице заказов кабинета он не загружается.

```powershell
docker compose exec web python manage.py test orders.tests.test_reporting --settings=config.settings.test
```

## Живые статусы заказов и CI

`GET /api/orders/{id}/events/` открывает SSE-поток для владельца заказа с действующим
Bearer-токеном. Без токена ответ 401, с чужим токеном 404, в том числе для сотрудника.
После коммита смены статуса Django публикует событие в общем Redis. При первом подключении,
переподключении и событии изменения React запрашивает актуальные карточку и историю через
TanStack Query. Соединение закрывается при уходе со страницы, выходе или истечении access.
При переподключении общий API-клиент обновляет истёкший access через существующую сессию.
После первого развёртывания этой версии потребуется снова войти с токенами, выпущенными
до включения проверки смены пароля.

Оба Compose-стенда запускают Django под Gunicorn с ASGI-воркерами. Redis для событий
настраивается через `ORDER_EVENTS_REDIS_URL`. На HTTPS nginx отключает буферизацию для
потока. Для обычного локального `runserver` API потока вернёт 503.

1. В одном профиле браузера оформите и оплатите заказ. Оставьте его карточку открытой.
2. В другом профиле войдите сотрудником и подтвердите тот же заказ. В профиле покупателя
   статус и история обновятся без перезагрузки. В Network остаётся открытым запрос
   `/api/orders/{id}/events/` с типом `text/event-stream`.
3. Временно отключите сеть в профиле покупателя и снова измените статус из профиля сотрудника.
   После восстановления сети проверьте новый статус. При выходе запрос потока закрывается.

После запуска dev или HTTPS и загрузки демоданных сценарий можно повторить в Playwright.

```powershell
docker compose exec web python manage.py test orders.tests.test_events --settings=config.settings.test
npm --prefix frontend run e2e -- order-events.spec.ts
$env:E2E_BASE_URL = 'https://localhost'
npm --prefix frontend run e2e -- order-events.spec.ts
Remove-Item Env:E2E_BASE_URL
```

GitHub Actions запускает CI при каждом push. Задача **Django** поднимает PostgreSQL 16 и
Redis, проверяет настройки, миграции, тесты и OpenAPI. Задача **React** проверяет типы,
линт, Vitest и сборку. Результаты обеих задач и журналы шагов доступны на вкладке
[Actions](https://github.com/GlebNagornikov/corporate-is-lab1/actions/workflows/ci.yml).

## Витрина и проверка КТ2

Главная открывается на `/`, каталог — на `/catalog`. Ссылки с фильтрами на `/` продолжают
открывать каталог. Шапка, карточки, корзина, оформление и личный кабинет используют общую
палитру. В меню «Тема» можно выбрать системный режим, светлую или тёмную тему. Явный выбор
хранится в браузере. Для главного блока использован сгенерированный натюрморт, для карточек —
обложки конкретных изданий. Шрифты Lora и Manrope поставляются локально с лицензией SIL OFL.
[Источники обложек](docs/lab11-cover-research.md).

В разработке оставьте `VITE_API_URL` пустым, чтобы запросы шли через прокси Vite на том же
origin. Для проверки прямых запросов скопируйте `frontend/.env.example` в `frontend/.env.local`,
укажите `VITE_API_URL=http://127.0.0.1:8000` и перезапустите Vite. Django разрешает CORS для
`http://localhost:5173` и `http://127.0.0.1:5173`. При другом dev-порте перечислите нужные origin
в `DEV_CORS_ALLOWED_ORIGINS` в корневом `.env` через запятую и пересоздайте web. Вход,
обновление и выход всегда используют тот же origin, что витрина. HTTPS использует nginx.

Проверка КТ2 включает 11 тестов каталога и сеанса, из них 9 проверяют HTTP API.
В Chromium измерены 13 пар текста и фона. Минимальные коэффициенты контраста
составили 5,85:1 в светлой теме и 7,26:1 в тёмной при пороге 4,5:1.

| Расширение | Состояние после шага 3 |
| --- | --- |
| Р1 · TypeScript | Строгие типы и сгенерированный контракт, включая галерею книги. |
| Р2 · TanStack Query | Общий кэш и мутации витрины, оптимистичная корзина с откатом. |
| Р3 · Data Router | Loaders, route actions входа, регистрации и оформления, границы ошибок. Форма персонала появится на шаге 6. |
| Р4 · Тесты React | Vitest, RTL и MSW проверяют формы, хуки, доступ и ошибки каркаса. |
| Р5 · Playwright | Есть регистрация, защищённый возврат, заказ, оплата и смена статуса. Итоговый сценарий проверяется на шаге 12. |
| Р6 · Ленивая загрузка | Формы и страницы заказов загружаются отдельно. Кабинет, отчёт и замеры проверяются на следующих шагах. |
| Р7 · OpenAPI | Swagger, типы и строгий валидатор. Новые операции добавляются в схему по мере реализации. |
| Р8 · Серверная корзина | Корзина в БД для покупателя, гостевая в браузере. Слияние и откат проверяются тестами. |
| Р9 · SSE | Запланировано на шаге 11. |
| Р10 · Тема | Системный режим, ручной выбор и сохранение проверяются в браузере. |
| Р11 · Доступность | Клавиатура, ширина 360 px и [отчёты Lighthouse для трёх страниц](docs/lab11-step12-acceptance.md#расширения). |
| Р12 · Прокрутка | Следующая серверная страница загружается при прокрутке или по кнопке «Показать ещё». URL хранит фильтры и номер последней загруженной страницы. Возврат из книги восстанавливает диапазон и позицию, прямая ссылка начинает список с указанной страницы. |
| Р13 · Compose | Работают dev и HTTPS с nginx. Проксирование SSE проверяется после шага 11. |
| Р14 · CI | Локальные проверки работают. GitHub Actions запланирован на шаге 11. |
