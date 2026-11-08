# Лабораторная №7: части 1–4

Выпущен релиз `1.0.0`: версия в коде, тег Git `v1.0.0` и образ `shop-web:1.0.0`
совпадают. Стенд разработки работает отдельно. В части 4 выпущен hotfix `1.0.1` и проверен откат.

## Как устроен стенд

Dockerfile содержит этапы `base`, `dev`, `builder`, `prod`. Dev использует runserver
и зависимости разработки. Prod копирует установленный в builder `/opt/venv`, запускает
Gunicorn от пользователя app, не содержит Debug Toolbar, Ruff и Coverage.
Код prod скопирован в образ, поэтому изменения требуют пересборки.

В `docker-compose.prod.yml` пять сервисов:

- `db`: PostgreSQL 16, отдельный том `shop-prod_pgdata`, без порта на компьютере.
- `migrate`: тот же prod-образ, однократный `migrate --noinput` после готовности БД.
- `web`: после успешных миграций собирает статику и запускает Gunicorn, без внешнего порта.
- `nginx`: после готовности web принимает HTTP/HTTPS, перенаправляет HTTP на HTTPS,
  передаёт запросы Django и самостоятельно отдаёт static/media из общих томов.
- `mailpit`: принимает SMTP внутри сети, интерфейс доступен на `127.0.0.1:8026`.

`/healthz/` выполняет `SELECT 1` и возвращает статус и версию; при ошибке БД возвращается
500. Только этот путь исключён из HTTPS-перенаправления Django для внутренней проверки.
Nginx устанавливает `X-Forwarded-Proto`, Django распознаёт HTTPS и использует Secure cookies.
`depends_on` задаёт порядок старта; статус unhealthy сам по себе не перезапускает контейнер.

## Подготовка на новом компьютере

Для воспроизведения лабораторной используйте checkout тега `v1.0.1` и запущенный Docker Desktop.
Команды выполняются из корня этого checkout. Актуальный запуск описан в [корневом README](../README.md).
Ниже команды PowerShell; в Git Bash вместо `curl.exe` используется `curl`.

```powershell
Copy-Item .env.prod.example .env.prod
New-Item -ItemType Directory -Force nginx/certs
```

В `.env.prod` оставить `APP_VERSION=1.0.1`, заменить `SECRET_KEY` длинным случайным
ключом (отличным от dev) и `POSTGRES_PASSWORD` случайным паролем. Для URL базы удобен
пароль из букв, цифр, `_` и `-`; остальные спецсимволы в DATABASE_URL требуют URL-кодирования.
Например, с установленным Python дважды выполнить `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

Сертификат в PowerShell с Git for Windows:

```powershell
& 'C:/Program Files/Git/usr/bin/openssl.exe' req -x509 -nodes -newkey rsa:2048 -days 365 -keyout nginx/certs/localhost.key -out nginx/certs/localhost.crt -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
```

В Git Bash использовать `openssl` и `-subj '//CN=localhost'`, если срабатывает преобразование путей.
`.env.prod`, сертификат с ключом и backups исключены из Git и контекста сборки.
Примеры окружения секретов не содержат. Shell-скрипты хранятся с LF; Dockerfile также
выставляет исполняемый бит entrypoint, что позволяет собирать образ из Windows.

## Запуск и наполнение

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod ps -a
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py seed_catalog --images
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py setup_groups
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py createsuperuser
```

Ожидаются `db` и `web` healthy, `migrate` Exited (0), `nginx` и `mailpit` Up.
Seed предназначен для новой демобазы: повторный запуск обновляет цены и остатки.
Данные dev не переносятся. На подготовленном локальном стенде уже создан `lab7admin`;
его пароль находится в локальном `.env.prod` (`DJANGO_SUPERUSER_PASSWORD`).
Эти дополнительные переменные нужны только для локального `createsuperuser --noinput`.
При новом развёртывании можно создать администратора интерактивной командой выше.

Открыть [магазин](https://localhost/), подтвердить исключение для собственного
самоподписанного сертификата. [Админка](https://localhost/admin/),
[версия и живость](https://localhost/healthz/), [почта стенда](http://localhost:8026/).
Для dev использовать [127.0.0.1:8000](http://127.0.0.1:8000/): HSTS для localhost
может мешать HTTP-разработке в течение 60 секунд и действует независимо от порта.

## Проверки

```powershell
curl.exe -I http://localhost/
curl.exe -k https://localhost/healthz/
curl.exe -kI https://localhost/
curl.exe -kI https://localhost/static/admin/css/base.css
curl.exe -sk -o NUL -w '%{http_code}' -X POST -H 'Origin: https://evil.example' https://localhost/accounts/login/
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py check --deploy
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py migrate --check
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python -c "import debug_toolbar"
docker compose -f docker-compose.prod.yml --env-file .env.prod logs web --tail 15
docker images shop-web
docker compose exec web python manage.py test --settings=config.settings.test
```

Ожидаются: HTTP 301 на HTTPS; JSON `{"status":"ok","version":"1.0.0"}`;
главная 200, Server nginx, X-Frame-Options DENY, HSTS max-age=60;
CSS 200 с Content-Type text/css; чужой Origin 403; check --deploy без замечаний;
миграции применены. Импорт debug_toolbar **должен завершиться с ModuleNotFoundError**.
В логах Gunicorn три worker и внутренние запросы healthcheck.

Дополнительная автоматическая проверка с компьютера (нужен Python 3):

```powershell
python scripts/check_prod.py
python scripts/check_prod.py --purchase
```

Первый вариант проверяет HTTP/HTTPS, версию, заголовки, CSS и отказ CSRF.
Второй также создаёт случайного покупателя, входит через обычные формы с CSRF,
проверяет Secure session cookie, изображение из nginx, добавляет товар в корзину,
оформляет курьерский заказ и находит письмо в Mailpit. Он оставляет тестового пользователя
и заказ в демобазе, списывает одну единицу товара. Пароль случайного покупателя не сохраняется.
Проверяющий скрипт принимает только локальный стенд и пропускает проверку доверия
самоподписанного сертификата, как `curl -k`.

Ручной сценарий: зарегистрироваться, выбрать товар с фото, добавить в корзину,
оформить заказ с курьером и адресом, открыть заказ, проверить письмо в Mailpit :8026.
В dev письма находятся отдельно, на :8025.

Остановка без потери данных:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod down
```

Не добавлять `-v`: это удалит базу, статику и загруженные изображения.
После изменения пароля в `.env.prod` существующая БД не меняет пароль автоматически.


## Релиз 1.0.0 (часть 3)

Релизная ветка `release/1.0.0` создана от develop. В ней поднята версия,
заполнен [CHANGELOG](../CHANGELOG.md#100--2026-11-04), выполнены тесты и проверка миграций.
PR в main сливается merge-коммитом; на этот коммит ставится аннотированный тег
`v1.0.0`. Изменения релиза возвращаются отдельным merge-коммитом в develop,
после чего release-ветка удаляется локально и на GitHub.

Для развёртывания нужен чистый checkout тега: незакоммиченные файлы не должны попадать
в релизный образ. Если в основной папке есть незавершённая работа, создать отдельный
checkout через `git worktree add --detach <папка-релиза> v1.0.0` и собирать образ там.
`.env.prod` и сертификат при этом сохраняются отдельно от исходников.

Обычный порядок для чистой основной папки:

```powershell
git checkout v1.0.0
# В .env.prod установить APP_VERSION=1.0.0
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
curl.exe -k https://localhost/healthz/
docker images shop-web
git checkout develop
```

Если используется отдельный checkout тега, собрать из него образ
`docker build --target prod -t shop-web:1.0.0 <папка-релиза>`, а затем из основной папки
выполнить `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build`.
Это запускает уже собранный из тега образ без добавления локальных правок.
Образ выпущенного релиза повторно не пересобирают: исправления получают новую версию.

Проверка истории и развёртывания:

```powershell
git cat-file -t v1.0.0
git show --no-patch v1.0.0
git log --oneline --graph --all -15
curl.exe -k https://localhost/healthz/
docker compose -f docker-compose.prod.yml --env-file .env.prod ps -a
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py check --deploy
python scripts/check_prod.py --expected-version 1.0.0
```

Тип объекта тега должен быть `tag`, версия в HTTPS-ответе — `1.0.0`,
`db` и `web` healthy, `migrate` Exited (0). В images остаются `0.9.0` и `1.0.0`.
Проверить, что прежние товары, пользователи и заказы сохранились в томах.
Для полного сценария покупки запустить `python scripts/check_prod.py --purchase`:
он оставляет новый тестовый заказ и письмо в Mailpit.


## Hotfix 1.0.1 и откат (часть 4)

Ветка `hotfix/1.0.1` создаётся от main. Общая `orders.validators.normalize_phone`
приводит телефон в форме и API к `+7XXXXXXXXXX`; неверный номер даёт ошибку поля
(HTML) или HTTP 400 с ключом phone (API). Исправление и выпуск версии — два коммита.
PR в main сливается merge-коммитом, на нём ставится аннотированный тег `v1.0.1`.
Исправление также возвращается merge-коммитом в develop, затем hotfix-ветка удаляется.

Образ `shop-web:1.0.1` собран из чистого checkout `v1.0.1`. В `.env.prod` после
обновления `APP_VERSION=1.0.1`; исходники основной папки на develop, локальные правки
в образ не добавляются. Старые телефоны в исторических заказах не переписываются.
Миграций в hotfix нет.

Проверить нормализацию и отказ в реальном HTTPS-сценарии (нужен Python):

```powershell
python scripts/check_prod.py --expected-version 1.0.1 --purchase --check-invalid-phone --phone "8 (913) 555-12-34" --expected-phone "+79135551234"
```

Скрипт сначала проверяет ошибку поля для 123, затем оформляет заказ с нормализованным
номером и проверяет сохранённый телефон через API и письмо в Mailpit.
В админке открыть новый заказ: телефон `+79135551234`.

Откат выполняется переключением готовых образов, без сборки:

```powershell
# В .env.prod установить APP_VERSION=1.0.0
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build
curl.exe -k https://localhost/healthz/
# Ожидается 1.0.0. Старые и новые заказы остаются в БД.
# Вернуть в .env.prod APP_VERSION=1.0.1
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build
curl.exe -k https://localhost/healthz/
# Ожидается 1.0.1.
```

После каждой команды дождаться healthy у web. Если nginx удерживает адрес прежнего
контейнера и отвечает 502, выполнить `docker compose -f docker-compose.prod.yml --env-file .env.prod restart nginx`.
Это не пересобирает образы и не удаляет данные. После отката и возврата проверить
`check --deploy`, `/healthz/`, сохранность заказов, а также `docker images shop-web`.
