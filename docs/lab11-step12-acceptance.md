# Приёмка лабораторной №11 · шаг 12

Проверки проводились 12 ноября 2026 года на стенде Docker с PostgreSQL, Redis и Vite
и на HTTPS-сборке за nginx. Источник критериев — [задание](lab-11-react-final-project.pdf)
и [план](../LAB11-PLAN.md#шаг-12-закрыть-пробелы-р1р14-и-прогнать-приёмку).
Чистый запуск по итоговому README с замером времени и выпуск тега относятся к шагу 13.

## Как повторить

Подготовьте [демоданные](../README.md#быстрый-запуск-разработки) на тестовой базе. Playwright создаёт
пользователей, заказы и карточки и изменяет остатки. Для HTTPS задайте в PowerShell
`$env:E2E_BASE_URL = 'https://localhost'`. Установите Chromium командой
`npx --prefix frontend playwright install chromium`.

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test --settings=config.settings.test
docker compose exec web python manage.py spectacular --validate --fail-on-warn --file /tmp/openapi.yaml
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend test
npm --prefix frontend run e2e
```

Django прошёл 212 тестов. `check` и проверка миграций завершились успешно, валидатор
OpenAPI прошёл без предупреждений. Typecheck, lint и production-сборка React прошли.
Полный прогон Playwright прошёл без повторов, 17 из 17 в dev и 17 из 17 через HTTPS.
Для HTTPS используйте [изолированный стенд из README](../README.md#тесты-react-витрины).
У него отдельная БД и лимиты для полного прогона с одного IP. На Gunicorn 26.2.0
после снятия проблемы с 429 оставались таймауты в трёх сценариях. После обновления
Gunicorn до 27.0.0 эти сценарии прошли в составе полного прогона.
Для повтора отдельного сценария добавьте после `npm --prefix frontend run e2e --` имя файла из таблицы.

Откройте [Swagger в dev](http://127.0.0.1:8000/api/docs/). В списке книг проверьте
описания параметров `q`, `binding`, `in_stock` и `ordering`. У `POST /api/orders/`
есть пример оформления и ответы 201/400, у учебной оплаты — пример запроса. Для Swagger
на HTTPS войдите в Django под сотрудником.

## Бэкенд и фронтенд

| Критерий | Проверка |
| --- | --- |
| Б1 | `git ls-files backend/requirements.txt frontend/package.json .gitignore frontend/.gitignore`. Отдельные манифесты, исходники и общий README. |
| Б2 | Открыть Swagger, сверить методы, параметры и сериализаторы. Итоговая сводная таблица API входит в шаг 13. |
| Б3 | Получить и обновить JWT, запросить `GET /api/auth/me/`. Без токена приватный список заказов даёт 401. |
| Б4 | Открыть чужой заказ и вложенную страницу менеджера под покупателем. API возвращает 404 и 403 соответственно. |
| Б5 | `GET /api/catalog/products/?q=ВОЙНА+МИРОВ&category=books&binding=paperback&ordering=price&page=1`. Сравнить поиск, параметры страницы и сортировку с `-price`. |
| Б6 | `orders.tests.test_api.OrderApiTests`. После заказа сохранены цена и количество, при отказе остатки и корзина сохраняются. |
| Б7 | [manager-catalog.spec.ts](../frontend/e2e/manager-catalog.spec.ts) и [storefront.spec.ts](../frontend/e2e/storefront.spec.ts). Публикация книги с фото, фильтр заказов и разрешённый переход. |
| Б8 | Прямые запросы checkout и отзывов из таблицы ниже. Ошибки 400/403 без побочных записей. |
| Б9 | `CORS_ALLOWED_ORIGINS` в настройках Django, прокси Vite и ответы 400 с полями или `detail`. Проверить запрос с разрешённым dev Origin и с посторонним Origin. |
| Б10 | [test_seed_books.py](../backend/catalog/tests/test_seed_books.py) и два запуска `seed_demo`. 21 издание, демопользователи, повторная загрузка сохраняет правки. |
| Б11 | [test_api.py](../backend/orders/tests/test_api.py) содержит 35 тестов одного класса `APITestCase`. Остальные классы покрывают модули и каталог. |
| Ф1 | [appRoutes.tsx](../frontend/src/appRoutes.tsx) и [маршруты менеджера](../frontend/src/manager/routes.tsx). Проверить больше 10 маршрутов, включая книгу, вложенные страницы и 404. |
| Ф2 | Открыть `/orders?page=1` гостем, зарегистрироваться и обновить страницу. Покупатель на `/manager/catalog/new` получает отказ. |
| Ф3 | Контексты сеанса и корзины, хуки [useDebouncedCallback](../frontend/src/lib/useDebouncedCallback.ts) и [usePageTitle](../frontend/src/lib/usePageTitle.ts). |
| Ф4 | [CatalogPage.test.tsx](../frontend/src/routes/CatalogPage.test.tsx) и [catalog-pagination.spec.ts](../frontend/e2e/catalog-pagination.spec.ts). URL, подгрузка, возврат, пустые результаты и повтор после ошибки. |
| Ф5 | [storefront.spec.ts](../frontend/e2e/storefront.spec.ts). Пустые поля показывают ошибки, два события отправки дают один POST заказа. |
| Ф6 | [two-profile-checkout.spec.ts](../frontend/e2e/two-profile-checkout.spec.ts). Гостевая корзина объединяется после входа, превышение показано до оплаты, при нехватке остатка форма сохраняется. |
| Ф7 | Открыть «Мои заказы», заказ и историю, отменить новый заказ. Покрытие в [orders.spec.ts](../frontend/e2e/orders.spec.ts) и `two-profile-checkout.spec.ts`. |
| Ф8 | [manager-catalog.spec.ts](../frontend/e2e/manager-catalog.spec.ts). Черновик, предпросмотр фото, публикация, снятие с витрины и JSON-импорт. |
| Ф9 | [client.test.ts](../frontend/src/api/client.test.ts) и [session.test.tsx](../frontend/src/auth/session.test.tsx). Один refresh на параллельные 401, при просроченном refresh возврат к входу. |
| Ф10 | [RootError.test.tsx](../frontend/src/routes/RootError.test.tsx) воспроизводит исключение компонента. Появляются сообщение и ссылка на главную. |
| Ф11 | [vite.config.ts](../frontend/vite.config.ts), [пример VITE_API_URL](../frontend/.env.example), команды lint и build. |
| Ф12 | `storefront.spec.ts` проверяет тему, ширину 360 px, заголовки вкладки и оформление. |
| Ф13 | Доставить заказ, отправить отзыв и одобрить его под менеджером. Проверка в [reviews.spec.ts](../frontend/e2e/reviews.spec.ts). Официальный вариант требует таблиц лабораторной №0.3. |

## Расширения

| Критерий | Проверка |
| --- | --- |
| Р1 | `npm --prefix frontend run typecheck`, [генерируемый контракт](../frontend/src/api/schema.d.ts). |
| Р2 | Общий QueryClient, loaders и точечная инвалидация. Повторить сбой изменения избранного в [personal.spec.ts](../frontend/e2e/personal.spec.ts). |
| Р3 | [appRoutes.tsx](../frontend/src/appRoutes.tsx) и маршруты менеджера. Выполнить вход, регистрацию, checkout и сохранение книги через route actions. |
| Р4 | Vitest и Testing Library. Прошли 59 тестов в 17 файлах. |
| Р5 | `npm --prefix frontend run e2e -- storefront.spec.ts manager-catalog.spec.ts`. Регистрация, ссылка с фильтром в новой вкладке, корзина, покупка, кабинет, переход сотрудника, книга с фото. |
| Р6 | `npm --prefix frontend run build`. Сравнение ниже, каркас менеджера и графики в отдельных файлах. |
| Р7 | Строгий валидатор схемы без предупреждений, русские параметры и примеры в Swagger. |
| Р8 | `npm --prefix frontend run e2e -- two-profile-checkout.spec.ts`. Два профиля видят одну корзину. |
| Р9 | `npm --prefix frontend run e2e -- order-events.spec.ts` через Vite и nginx. Bearer, повторное соединение, смена статуса без F5 и закрытие на выходе. |
| Р10 | `storefront.spec.ts`. Тёмная тема переживает F5, системная тема реагирует на настройку браузера. |
| Р11 | Lighthouse 13.6.0, HTTPS, мобильный режим. [Главная](lighthouse/home.json), [книга](lighthouse/product.json) и [оформление](lighthouse/checkout.json) получили по 100. Проверить `categories.accessibility.score` и `audits.color-contrast`. |
| Р12 | `npm --prefix frontend run e2e -- catalog-pagination.spec.ts`. Прямая ссылка на страницу 2, догрузка и восстановление позиции. |
| Р13 | `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build --wait`. Открыть `/healthz/`, `/api/catalog/products/`, обложку из `/media/` и обновить прямые ссылки. |
| Р14 | [CI на push](../.github/workflows/ci.yml), задачи Django и React в GitHub Actions. |

### Размеры production-сборок

Сравнивались архив исходного среза `4773316` и текущая ветка. В обоих случаях
использовались Node 24.19.0, зависимости из соответствующего lock-файла и `npm run build`
с Vite 8.3.6. Размеры из вывода Vite в кБ, в скобках gzip.

| Файл | Исходный срез | Шаг 12 |
| --- | ---: | ---: |
| Основной JS `index` | 257,26 (80,37) | 381,71 (118,96) |
| Основной JS и его modulepreload из HTML, сумма | 389,80 (124,24) | 427,04 (136,29) |
| `ManagerLayout` | — | 2,44 (1,15) |
| `ManagerOrdersPage` | 4,36 (1,85) | 4,82 (1,97) |
| `CheckoutPage` | 4,99 (2,13) | 5,52 (2,22) |
| `ManagerReportPage` | — | 3,85 (1,71) |
| `ReportCharts` | — | 3,27 (1,46) |

В DevTools на HTTPS отключите кэш и откройте витрину, затем кабинет и отчёт
за период с заказами. `ManagerLayout` загружается для кабинета, `ReportCharts` —
при появлении графиков. `lazy()` и `Suspense` находятся в [ManagerReportPage.tsx](../frontend/src/manager/ManagerReportPage.tsx).

## Негативные сценарии и М1–М4

Команды Django из раздела «Как повторить» принимают указанный ниже модуль тестов
после `--settings=config.settings.test`. Используются тестовая БД и собственные фикстуры.

| Сценарий | Действие и ожидаемый результат | Проверка |
| --- | --- | --- |
| Чужой заказ | Покупатель Б запрашивает `GET /api/orders/{id}/` и `POST /api/orders/{id}/cancel/` для заказа А. Оба ответа 404, отмены нет. | `orders.tests.test_api`, `two-profile-checkout.spec.ts` |
| Права персонала | Под покупателем запросить `GET /api/manager/orders/` и `POST /api/manager/orders/{id}/status/`. 403, а без JWT 401. | `orders.tests.test_api`, `manager-catalog.spec.ts` |
| Остаток | В корзине 2 книги, доступна 1. `POST /api/orders/` даёт 400, новый заказ отсутствует, остаток 1. | `orders.tests.test_api`, `two-profile-checkout.spec.ts` |
| Лимит | В корзине 6 экземпляров одного издания. `POST /api/orders/` даёт 400, корзина и остатки сохраняются. Пять экземпляров при наличии проходят. | `orders.tests.test_api` |
| М1 | `POST /api/catalog/products/{slug}/reviews/` без доставленной покупки или повторно даёт 400. Единственный допустимый отзыв ждёт модерации. Одобрение меняет публичный рейтинг. | `catalog.tests.test_reviews`, `reviews.spec.ts` |
| М2 | `POST /api/promo/check/` с завышенной суммой под покупателем использует сумму БД. `POST /api/orders/` с `promo_code` ниже порога даёт 400, заказ и использование промокода отсутствуют. | `orders.tests.test_promos`, `promos.spec.ts` |
| М3 | Пополнить книгу с нуля. Через `GET /api/notifications/` уведомление видно владельцу. Для другого покупателя запись отсутствует. | `catalog.tests.test_restock_api`, `personal.spec.ts` |
| М4 | Покупатель запрашивает `GET /api/manager/reports/sales/` и `GET /api/manager/reports/sales/csv/` с одинаковыми датами. Оба ответа 403. У менеджера суммы и диапазон совпадают. | `orders.tests.test_reporting` |
| Статус | `POST /api/manager/orders/{id}/status/` с `{"status":"delivered"}` для нового заказа даёт 400. Статус, история и остаток сохраняются, публикация в SSE не планируется. | `orders.tests.test_api.OrderApiTests.test_manager_cannot_skip_to_delivered_or_publish_an_event` |
| Подмена цены | Добавить в `POST /api/orders/` поля `price`, `subtotal`, `discount`, `total`, `items` и `status`. Сохранены цена каталога, количество из корзины, серверные суммы и начальный статус. | `orders.tests.test_api.OrderApiTests.test_checkout_ignores_server_controlled_fields` |
| JWT | На dev-стенде временно задать `JWT_ACCESS_MINUTES=1` для web. Войти, открыть `/notifications`, после истечения access вернуться на вкладку. Запросы списка и счётчика получили 401, один refresh вернул 200, оба запроса восстановились. Исходный срок восстановлен. При просроченном refresh защищённый маршрут ведёт на вход с `next`. | DevTools Network, `client.test.ts`, `session.test.tsx`, повтор SSE в `order-events.spec.ts` |
| Сбой UI/API | Исключение компонента даёт страницу ошибки. Выполнить `docker compose stop web` и открыть `/catalog` в новой вкладке. После таймаута и повторов видны сообщение и кнопка «Повторить». Выполнить `docker compose up -d web` и повторить загрузку. | `RootError.test.tsx`, `CatalogPage.test.tsx`, проверка с остановленным контейнером |

Клавиатурой проверены переход к основному содержимому, добавление книги, корзина, вход,
поля оформления и кнопка сохранения книги в кабинете. В Playwright диалог статуса
открывается Enter, закрывается Escape и возвращает фокус кнопке. При ширине 360 px
проверены страницы витрины и оформление. Контраст текста, вторичного текста и основной
кнопки составляет соответственно 14,72:1, 6,62:1 и 12,92:1 в светлой теме, 15,61:1,
10,11:1 и 8,95:1 в тёмной.
