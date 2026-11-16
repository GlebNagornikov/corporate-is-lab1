# Книжная полка

Независимый книжный магазин с каталогом физических изданий. React и TypeScript обслуживают витрину и кабинет, Django REST Framework и PostgreSQL хранят каталог, корзины и заказы. Redis используется для кэша, очереди писем и событий заказов.

Гость может просматривать витрину и собирать корзину. Покупатель управляет своими заказами, отзывами и уведомлениями. Менеджер управляет каталогом, заказами и модулями в разделе **Кабинет менеджера**. Django admin и CRM доступны с отдельными правами.

В одном заказе допускается до **пяти экземпляров одного издания**, суммарно по его вариантам. При оформлении сервер проверяет остатки и лимит, применяет скидку и рассчитывает цены. После входа гостевые и серверные количества складываются по товару и варианту в пределах остатка и лимита издания. Недоступные позиции пропускаются. Гостевой промокод переносится, если в непустой корзине ещё нет своего кода. Витрина сообщает об изменениях цен и очищает локальную корзину после успешного переноса.

| Модуль | Правило |
| --- | --- |
| М1 · Отзывы и рейтинг | Один отзыв на издание после доставки собственного заказа. На витрине и в рейтинге учитываются одобренные отзывы.|
| М2 · Промокоды | Сервер проверяет код, срок, активность, минимальную сумму и лимит применений. Проверка в корзине не расходует лимит. |
| М3 · Избранное и поступления | Личные списки и уведомления привязаны к аккаунту. Пополнение с нуля уведомляет подписчика один раз за цикл. |
| М4 · Отчёт | Диапазон дат хранится в URL, CSV использует этот же диапазон.|

## Запуск на новом компьютере с Windows

1. Установите [Git for Windows](https://git-scm.com/download/win), [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) и [Node.js 24 LTS](https://nodejs.org/en/download). Если установщик Docker предложит включить WSL 2 или перезагрузиться, выполните это и снова откройте Docker Desktop. Дождитесь запуска Docker Engine.
2. Откройте **PowerShell** из меню «Пуск». Копируйте команды по одной и нажимайте Enter. Первая группа проверяет программы. `docker compose version` должен вывести версию Compose, `node --version` — строку с `v24.`.

   ```powershell
   git --version
   docker compose version
   docker info --format '{{.ServerVersion}}'
   node --version
   ```

3. Перейдите в домашнюю папку, скачайте релиз и скопируйте шаблон настроек. Точка в `.env` входит в имя файла. Если папка `knizhnaya-polka` уже существует, выберите другое имя для клона и перехода в него. Для повторного запуска в существующей рабочей копии сохраните её `.env`.

   ```powershell
   Set-Location $HOME
   git clone --branch v2.0 https://github.com/GlebNagornikov/corporate-is-lab1.git knizhnaya-polka
   Set-Location knizhnaya-polka
   Copy-Item .env.example .env
   ```

   Если этот магазин уже запускали на компьютере, а новой копии нужна собственная база, используйте [отдельное имя Compose-проекта](#ошибка-входа-в-postgresql) с первого запуска. Имя папки само по себе том не меняет.

4. Запустите Django, Vite и вспомогательные сервисы. При первом запуске Docker скачает образы и соберёт приложение. Дождитесь успешного завершения каждой команды. Миграции на пустой базе выведут строки `Applying ... OK`, а `seed_demo` напечатает число демоизданий. Если миграции сообщат `password authentication failed`, перейдите к разделу [об ошибке входа в PostgreSQL](#ошибка-входа-в-postgresql).

   ```powershell
   docker compose up -d --build --wait
   docker compose exec web python manage.py migrate --noinput
   docker compose exec web python manage.py seed_demo --password 'DemoShop2026!'
   docker compose ps
   ```

5. Откройте [магазин](http://127.0.0.1:5173/). Когда Vite завершит установку, на главной появятся «Книги, к которым возвращаются» и обложки. Если страница ещё не открывается, подождите вывода `Local` или `Network` в `docker compose logs frontend`, затем обновите её. Нажмите **Войти** и используйте одну из пар ниже.

   | Роль | Имя пользователя | Пароль |
   | --- | --- | --- |
   | Покупатель | `buyer_demo` | `DemoShop2026!` |
   | Менеджер | `manager_demo` | `DemoShop2026!` |

   Это реквизиты локальной демобазы. Повторный посев сохраняет пароли уже созданных пользователей. [Swagger](http://127.0.0.1:8000/api/docs/) открывается через Django, [Mailpit](http://127.0.0.1:8025/) показывает учебные письма.

6. Чтобы остановить магазин, в той же папке введите `docker compose stop`. Для следующего запуска откройте Docker Desktop, вернитесь в папку проекта и введите `docker compose up -d`. Данные лежат в томе PostgreSQL и папке `media`.

[HTTPS и перенос своих данных](docs/shop-setup.md)

### Ошибка входа в PostgreSQL

При `password authentication failed for user "corporate_is"` PostgreSQL доступен, но отклоняет реквизиты Django. Compose по умолчанию использует имя проекта `corporate-is-lab1`, поэтому даже новый клон в другой папке может подключить том от предыдущего запуска. PostgreSQL применяет `POSTGRES_USER`, `POSTGRES_PASSWORD` и `POSTGRES_DB` при создании базы в пустом томе. Изменение `.env` не меняет пароль роли в существующей базе.

- **Если нужны данные существующей базы**, восстановите в `.env` значения `POSTGRES_USER`, `POSTGRES_PASSWORD` и `POSTGRES_DB`, с которыми она работает. Если пароль был изменён в PostgreSQL, укажите действующий пароль. Переменные PowerShell с этими именами имеют приоритет над `.env`. Проверьте их наличие без вывода значений командой `Get-ChildItem Env:POSTGRES_* | Select-Object -ExpandProperty Name` и уберите переопределения из текущего сеанса, если хотите использовать `.env`. Затем выполните `docker compose up -d --wait` и повторите миграции. Если реквизиты неизвестны, сохраните том и восстановите доступ через администратора PostgreSQL.
- **Если нужна чистая демобаза**, остановите текущий запуск, чтобы освободить порты, и задайте новое имя Compose-проекта. Выберите имя, которое ещё не использовалось на этом компьютере. Старый том останется на месте.

  ```powershell
  docker compose stop
  docker compose -p knizhnaya-polka-demo up -d --build --wait
  docker compose -p knizhnaya-polka-demo exec web python manage.py migrate --noinput
  docker compose -p knizhnaya-polka-demo exec web python manage.py seed_demo --password 'DemoShop2026!'
  ```

  Используйте то же `-p knizhnaya-polka-demo` в последующих командах для этой копии. Если предыдущий запуск уже использовал другое имя проекта, укажите его в первой команде `stop`.

## API

Базовый адрес для запросов в dev — `http://127.0.0.1:8000`. Приватные запросы принимают `Authorization: Bearer <access>`. Публичные операции доступны гостю. «Свой» означает доступ к данным текущего пользователя. Операции кабинета проверяют роль и разрешения Django соответствующего действия. CRM проверяет модельные разрешения на чтение и запись. Без авторизации приватный API отвечает 401, при недостатке прав — 403, для чужого заказа — 404.

| Метод | Путь | Доступ | Операция |
| --- | --- | --- | --- |
| GET | `/api/docs/`, `/api/schema/` | Dev публично, HTTPS через сессию сотрудника Django | Swagger и OpenAPI |
| POST | `/api/auth/register/` | Публично | Регистрация |
| GET | `/api/auth/me/` | JWT | Профиль и роль |
| POST | `/api/auth/token/`, `/api/auth/token/refresh/` | Пароль или refresh соответственно | Выдать или обновить JWT для API |
| GET | `/api/auth/session/csrf/` | Публично | Получить CSRF для SPA |
| POST | `/api/auth/session/login/` | Пароль и CSRF | Войти и получить refresh в HttpOnly cookie |
| POST | `/api/auth/session/refresh/`, `/api/auth/session/logout/` | Сессия SPA и CSRF | Обновить access или завершить сессию |
| GET | `/api/catalog/categories/`, `/api/catalog/categories/{slug}/` | Публично | Жанры |
| GET | `/api/catalog/products/`, `/api/catalog/products/{slug}/`, `/api/catalog/editorial/` | Публично | Каталог, издание, подборка |
| GET | `/api/catalog/products/{slug}/review-eligibility/` | JWT | Возможность оставить отзыв |
| GET, POST | `/api/catalog/products/{slug}/reviews/` | GET публично, POST JWT с доставленной покупкой | Читать и оставить отзыв |
| GET | `/api/cart/` | Свой | Корзина |
| POST | `/api/cart/items/`, `/api/cart/merge/` | Свой | Добавить позицию или перенести гостевые |
| PATCH, DELETE | `/api/cart/items/{product_id}/` | Свой | Изменить количество или удалить позицию с учётом варианта |
| PATCH | `/api/cart/promo/` | Свой | Применить или убрать код |
| POST | `/api/promo/check/` | Публично | Проверить промокод, для JWT по сумме в БД |
| GET, POST | `/api/orders/` | Свой | Просмотреть заказы или оформить корзину |
| GET | `/api/orders/{id}/`, `/api/orders/{id}/events/` | Свой | Детали заказа и поток SSE |
| POST | `/api/orders/{id}/cancel/`, `/api/orders/{id}/simulate-payment/` | Свой | Отменить новый заказ или провести учебную оплату |
| POST | `/api/orders/{id}/status/`, `/api/manager/orders/{id}/status/` | Менеджер | Сменить статус по допустимому переходу |
| GET, POST, DELETE | `/api/wishlist/` | Свой | Читать, добавить или убрать избранное |
| DELETE | `/api/wishlist/{id}/` | Свой | Убрать книгу по ID товара |
| GET, POST | `/api/restock/{id}/` | Свой | Проверить или оформить подписку по ID товара |
| GET | `/api/notifications/` | Свой | Список уведомлений |
| GET, POST | `/api/notifications/unread/` | Свой | Счётчик или прочитать все |
| DELETE | `/api/notifications/{id}/` | Свой | Удалить уведомление |
| GET | `/api/manager/orders/`, `/api/manager/orders/{id}/` | Менеджер | Список, контакты и история заказов |
| GET, POST | `/api/manager/catalog/` | Менеджер | Список книг, создание через multipart |
| GET, PATCH, DELETE | `/api/manager/catalog/{id}/` | Менеджер | Детали, редактирование, удаление |
| PATCH | `/api/manager/catalog/{id}/variants/{variant_id}/` | Менеджер | Цена, остаток и доступность варианта |
| POST | `/api/manager/catalog/import-json/` | Менеджер | Проверить или импортировать JSON-файл |
| GET, POST | `/api/manager/categories/` | Менеджер | Жанры для формы, создание жанра |
| GET | `/api/manager/reviews/` | Менеджер | Очередь отзывов |
| POST | `/api/manager/reviews/{id}/moderate/` | Менеджер | Одобрить или отклонить |
| GET, POST | `/api/manager/promos/` | Менеджер | Список и создание кодов |
| POST | `/api/manager/promos/{id}/deactivate/` | Менеджер | Деактивировать код |
| GET | `/api/manager/reports/sales/`, `/api/manager/reports/sales/csv/` | Менеджер | Отчёт и CSV |
| GET, POST | `/api/departments/`, `/api/employees/` | Права CRM | Списки и создание |
| GET, PUT, PATCH, DELETE | `/api/departments/{id}/`, `/api/employees/{id}/` | Права CRM | Карточки, изменение, удаление |
| POST | `/payments/webhook/` | Подпись HMAC | Уведомление учебного шлюза |
| GET | `/healthz/` | Публично | Доступность приложения и БД |

Примеры JSON для `POST` (ID товара и заказа берутся из ответов API).

| Путь | Тело |
| --- | --- |
| `/api/auth/token/` | `{"username":"buyer_demo","password":"DemoShop2026!"}` |
| `/api/cart/items/` | `{"product":1,"variant":null,"quantity":1}` |
| `/api/orders/` | `{"full_name":"Анна Петрова"},"phone":"+79991234567","email":"anna@example.com","delivery_method":"pickup"}` |
| `/api/manager/orders/{id}/status/` | `{"status":"confirmed"}` |
