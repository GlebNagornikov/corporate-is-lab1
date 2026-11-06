# Правила проекта для ИИ-ассистентов

Магазин на Django 6.1, Django REST Framework и PostgreSQL 16. Приложения Django находятся в корне
репозитория. Фронтенд на React 19 и TypeScript 7 находится в `frontend/`. Для запуска среды разработки
используйте `docker compose up -d`. Для локальных проверок фронтенда установите зависимости командой
`npm ci --prefix frontend` в Node.js 24.

## Бэкенд

- Размещайте бизнес-логику в сервисах или методах моделей. Используйте `transaction.atomic` для
  операций, которые должны выполниться целиком, и `select_for_update` для блокировки строк при
  конкурентных изменениях.
- По умолчанию API требует аутентификации через `IsAuthenticated`. Публичным операциям явно
  задавайте `AllowAny` и сохраняйте ограничения доступа для приватных операций.
- При изменении API обновляйте OpenAPI. Выполняйте
  `docker compose exec web python manage.py spectacular --validate --fail-on-warn`.
- Запускайте тесты командой
  `docker compose exec web python manage.py test --settings=config.settings.test`.

## Фронтенд

- Используйте `react-router` 8 в режиме данных через `createBrowserRouter` и импортируйте
  `RouterProvider` из `react-router/dom`.
- Загружайте серверные данные через TanStack Query v5 с `queryOptions` и объектным синтаксисом
  `useQuery`. Используйте загрузчики маршрутов для предзагрузки в общий кэш.
- Выполняйте запросы через типизированный клиент `api` из `frontend/src/api/client.ts`. Обновляйте
  `frontend/src/api/schema.d.ts` из запущенного Django командой `npm --prefix frontend run api:types`
  и сохраняйте сгенерированный файл в Git.
- Используйте строгие типы без `any`. API передаёт цены десятичными строками. Преобразуйте их в числа
  для форматирования, денежные суммы рассчитывает сервер.
- Перед коммитом в `frontend/` запускайте `npm run typecheck`, `npm run lint` и `npm test`.
