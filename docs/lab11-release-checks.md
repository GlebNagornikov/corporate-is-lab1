# Протокол приёмки v2.0

Порядок следует части 7 лабораторной №11. Для проверки используйте свежую базу. Сквозные тесты и ручные сценарии создают записи и меняют остатки. Запишите время от `git clone` до первого входа, результаты команд и номер проверенного коммита. Цель для защиты — до 15 минут при установленных программах.

## Автоматические проверки

Запустите [dev по README](../README.md#запуск-на-новом-компьютере-с-windows) и выполните из корня в PowerShell. Django создаёт отдельную тестовую БД.

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test --settings=config.settings.test
docker compose exec web python manage.py spectacular --validate --fail-on-warn --file /tmp/openapi.yaml
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend test
npx.cmd --prefix frontend playwright install chromium
npm.cmd --prefix frontend run e2e -- --grep-invert '@https'
```

Успешный результат — `System check identified no issues`, `No changes detected`, `OK` у Django, завершение OpenAPI без предупреждений и `passed` у Vitest и Playwright. При сбое Playwright сохраняет след в `frontend/test-results/`. В GitHub Actions найдите тот же коммит и проверьте четыре задачи CI.

## Проверки на HTTPS

После создания `.env.prod` и сертификата [по инструкции](shop-setup.md#https-на-этом-компьютере) выполните команды. Тестовый проект получает собственные тома и адрес `https://localhost:8443`.

```powershell
$testProject = 'shop-e2e-' + (Get-Date -Format yyyyMMddHHmmss)
$testCompose = @('-p', $testProject, '-f', 'docker-compose.prod.yml', '-f', 'docker-compose.e2e.yml', '--env-file', '.env.prod')
```

Перед выполнением следующего блока Compose должен получить тестовый `.env.prod` внутри контейнеров. Выполняйте его в отдельном чистом клоне или в папке со свежим стендом, где `.env.prod` можно временно подменить. Меняются только origin и URL, пароль существующего рабочего стенда восстанавливается в `finally`.

```powershell
$prodSettings = Get-Content .env.prod -Raw
try {
    (Get-Content .env.prod) -replace '^(CSRF_TRUSTED_ORIGINS|SITE_URL)=.*$', '$1=https://localhost:8443' |
        Set-Content .env.prod -Encoding ascii
    docker compose @testCompose up -d --build --wait --wait-timeout 180
    if ($LASTEXITCODE) { throw 'HTTPS-стенд не запустился' }
    docker compose @testCompose exec web python manage.py seed_demo --password 'DemoShop2026!'
    if ($LASTEXITCODE) { throw 'Не удалось загрузить каталог' }
    $env:E2E_BASE_URL = 'https://localhost:8443'
    npm.cmd --prefix frontend run e2e
    if ($LASTEXITCODE) { throw 'Playwright обнаружил ошибки' }
    # Для дополнительной проверки восстановления снимка раскомментируйте следующую строку.
    # ./scripts/check-shop-snapshot.ps1 -SourceProject $testProject
} finally {
    Remove-Item Env:E2E_BASE_URL -ErrorAction SilentlyContinue
    docker compose @testCompose stop
    Set-Content .env.prod -Value $prodSettings -NoNewline -Encoding ascii
}
```

GitHub Actions также проверяет восстановление снимка в HTTPS-задаче.

## Два сквозных сценария

1. **Покупатель.** В обычном окне нажмите «Регистрация», создайте аккаунт с уникальным именем и email. На витрине найдите книгу по названию, выберите жанр или переплёт, откройте скопированный URL в новой вкладке и сравните результаты. Добавьте доступную книгу, откройте корзину и оформите самовывоз, указав имя и телефон. Откройте заказ в личном кабинете и обновите страницу. Выполните учебную оплату картой `4242 4242 4242 4242`, сроком в будущем и CVV `123`. Сохраните ссылку, чтобы видеть статус. После доставки оставьте отзыв и проверьте его появление после модерации.
2. **Сотрудник.** В другом профиле или приватном окне войдите как `manager_demo`. Откройте заказ покупателя, меняйте статус по доступным действиям до «Доставлен». При открытом заказе у покупателя статус и история обновляются без F5. Одобрите отзыв в очереди. В каталоге сотрудника нажмите «Добавить книгу», укажите уникальные название и SKU, жанр, автора, цену и остаток, загрузите JPEG или PNG и опубликуйте книгу. Найдите её на витрине. На HTTPS откройте прямую ссылку на карточку, нажмите F5 и проверьте обложку. Запрос каталога и запрос изображения должны вернуть 200. Откройте также защищённый вложенный маршрут сотрудника и обновите страницу.

Для проверки гостевого переноса повторите оформление в чистом профиле после добавления книги до входа. Корзина и маршрут продолжения покупки должны восстановиться после входа. Для проверки ролей откройте `/manager/catalog` под покупателем. React покажет «Нет доступа».

## Негативные проверки

Используйте [магазин dev](http://127.0.0.1:5173/) и отдельную демобазу. Для компактных запросов ниже нужен PowerShell 7. В PowerShell проверьте версию командой `$PSVersionTable.PSVersion`. Код ответа печатается перед JSON, токены остаются в переменных. Для истёкшего токена повторите блок выдачи.

```powershell
$base = 'http://127.0.0.1:8000'
function ShopApi($method, $path, $token = '', $body = $null) {
    $params = @{ Uri = "$base$path"; Method = $method; SkipHttpErrorCheck = $true; StatusCodeVariable = 'status' }
    if ($token) { $params.Headers = @{ Authorization = "Bearer $token" } }
    if ($null -ne $body) {
        $params.ContentType = 'application/json; charset=utf-8'
        $params.Body = $body | ConvertTo-Json -Depth 8 -Compress
    }
    $result = Invoke-RestMethod @params
    Write-Host "$method $path -> $status"
    $result
}
$demoPassword = 'DemoShop2026!'
$a = (ShopApi POST /api/auth/token/ '' @{username='buyer_demo'; password=$demoPassword}).access
$m = (ShopApi POST /api/auth/token/ '' @{username='manager_demo'; password=$demoPassword}).access
$bName = 'defense-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
ShopApi POST /api/auth/register/ '' @{username=$bName; email="$bName@example.com"; password=$demoPassword}
$b = (ShopApi POST /api/auth/token/ '' @{username=$bName; password=$demoPassword}).access
$orderData = @{full_name='Анна Петрова'; phone='+79991234567'; email='anna@example.com'; delivery_method='pickup'}
$book = (ShopApi GET '/api/catalog/products/?in_stock=true').results | Where-Object stock -ge 8 | Select-Object -First 1
$bookId = $book.id
$slug = $book.slug
ShopApi POST /api/cart/items/ $a @{product=$bookId; quantity=1}
$order = (ShopApi POST /api/orders/ $a $orderData).id
```

Начните с пустой корзины А. Если А уже покупал выбранную книгу, для проверки М1 используйте нового покупателя или чистую базу. В таблице команды `ShopApi` используют эту же сессию PowerShell.

| Сценарий | Действие | Ожидается |
| --- | --- | --- |
| Чужой заказ | Под Б открыть `/orders/$order`. Выполнить `ShopApi GET "/api/orders/$order/" $b` и `ShopApi POST "/api/orders/$order/cancel/" $b @{}`. Сравнить с `ShopApi GET "/api/orders/$order/" $a`. | В UI «Не найдено», в API два 404. Статус А остался `new`. |
| Права сотрудника | `ShopApi GET /api/manager/orders/`, затем этот же запрос с `$b`. Выполнить `ShopApi POST "/api/manager/orders/$order/status/" $b @{status='confirmed'}`. | Без токена 401, с токеном Б оба 403. Заказ без изменений. |
| Переход статуса | `ShopApi POST "/api/manager/orders/$order/status/" $m @{status='delivered'}`. Сверить детали заказа покупателя и историю до и после. | 400, статус, история и остаток прежние. События SSE нет. |
| Остаток | Положить две книги через `ShopApi POST /api/cart/items/ $a @{product=$bookId; quantity=2}`. В кабинете снизить остаток стандартного издания до 1. Выполнить `ShopApi POST /api/orders/ $a $orderData`. Получить `/api/cart/`, `/api/orders/`, `/api/catalog/products/$slug/`. Вернуть через кабинет прежний остаток и удалить позицию. | 400, в корзине по-прежнему две книги, новый заказ отсутствует, остаток 1. |
| Лимит издания | На тестовой БД повторить приведённый ниже тест `test_checkout_rejects_six_copies_in_one_line`. Он создаёт книгу с запасом и строку на шесть экземпляров, отправляет `POST /api/orders/` с `full_name`, `phone`, `email` и `delivery_method`. | 400 про лимит, заказов нет, в строке остаётся шесть экземпляров, остаток прежний. |
| М1 | `ShopApi POST "/api/catalog/products/$slug/reviews/" $b @{rating=5; text='Проверка отзыва'}`. Доставить заказ А из кабинета, выполнить этот запрос с `$a` дважды. | Для Б 400, для А 201 и затем 400. Очередь получает одну запись. |
| М2 | В кабинете создать активный код `DEFENSE10` со скидкой 10% и порогом 100000 ₽. Под А добавить одну книгу, выполнить `ShopApi POST /api/promo/check/ $a @{code='DEFENSE10'; subtotal='999999.00'}` и `ShopApi POST /api/orders/ $a ($orderData + @{promo_code='DEFENSE10'; subtotal='999999.00'})`. | Сумма берётся из БД, оформление даёт 400. Заказ и применение кода отсутствуют. Деактивировать код после проверки. |
| М3 | В кабинете обнулить остаток стандартной книги. Выполнить `ShopApi POST "/api/restock/$bookId/" $a @{}`. Пополнить остаток. Запросить `ShopApi GET /api/notifications/ $a` и повторить с `$b`. Удалить уведомление А по его ID с токеном Б. | Новое уведомление видно А, Б его не получает и получает 404 при удалении. |
| М4 | Подставить фактические даты в `ShopApi GET '/api/manager/reports/sales/?start=2026-11-01&end=2026-11-30' $b` и повторить для `/sales/csv/` с теми же параметрами. | 403 в обоих случаях. Для М те же запросы дают 200. |
| Подмена суммы | При корректной корзине и доступном остатке выполнить `ShopApi POST /api/orders/ $a ($orderData + @{price='0.01'; subtotal='0.01'; discount='9999.00'; total='0.01'})`. | 201, строки и итог содержат цену каталога, серверную скидку и доставку. |
| Сбой Django | Выполнить `docker compose stop web`, открыть `/catalog` в новой вкладке. После сообщения об ошибке выполнить `docker compose up -d web` и нажать «Повторить». | Понятное сообщение, затем рабочий каталог. |

```powershell
docker compose exec web python manage.py test --settings=config.settings.test orders.tests.test_api.OrderApiTests.test_checkout_rejects_six_copies_in_one_line
npm.cmd --prefix frontend test -- RootError.test.tsx
```

Для проверки срока JWT сохраните `.env` и временно задайте access на одну минуту. Откройте DevTools → Network, войдите и откройте «Уведомления». После истечения access вернитесь на вкладку. Для параллельных запросов должен быть один успешный `POST /api/auth/session/refresh/`, затем запросы повторятся. Для отдельного сценария просроченного refresh используйте тест сессии React, где запрос refresh возвращает 401, а защищённый маршрут ведёт на вход с `next`.

```powershell
Copy-Item .env .env.jwt-backup
(Get-Content .env | Where-Object { $_ -notmatch '^JWT_ACCESS_MINUTES=' }) + 'JWT_ACCESS_MINUTES=1' | Set-Content .env
docker compose up -d --force-recreate web
# После проверки
Copy-Item .env.jwt-backup .env -Force
Remove-Item .env.jwt-backup
docker compose up -d --force-recreate web
npm.cmd --prefix frontend test -- session.test.tsx client.test.ts
```

Сверка состояния и дополнительные ветки проверяются в `orders.tests.test_api`, `orders.tests.test_promos`, `orders.tests.test_reporting`, `catalog.tests.test_reviews` и `catalog.tests.test_restock_api`. [Артефакты и результаты предыдущего шага](lab11-step12-acceptance.md).

## Вопросы и доработка на защите

- [Оформление заказа](../backend/orders/services.py). Покажите, где начинается транзакция, как суммируются варианты издания, где проверяется остаток и почему итог берётся с сервера.
- [API заказов](../backend/orders/api.py) и [SSE на фронтенде](../frontend/src/orders/useOrderEvents.ts). Объясните проверку владельца, получение Bearer, сверку состояния при переподключении и очистку подписки.
- [Клиент API](../frontend/src/api/client.ts). Покажите, как несколько 401 используют одно обновление JWT и что происходит при выходе.

Для тренировки на отдельной ветке добавьте сортировку «Сначала новые издания». Начните с поля параметров в [фильтрах Django](../backend/catalog/filters.py), проведите вариант через схему и список сортировок витрины, проверьте URL в новой вкладке и обновите тест порядка выдачи. На работу отводится до десяти минут.

## История по контрольным точкам

| Точка | Коммиты и изменения |
| --- | --- |
| КТ1 | `0646019` перенос Django, `26ca25a` воспроизводимые проверки. |
| КТ2 | `d4deb3a` демокаталог, `6439d99` ISBN и старые позиции, `cb3d15c` витрина, `d5dccf0` навигация каталога, `11a10c9` прокрутка. |
| КТ3 | `c17f12f` лимит, `cc34bee` кабинет, `d58ee27` жанры, `f404f71` импорт и удаление, `7d258fc` JSON и заказ. |
| КТ4 | `df9c6a2` отзывы, `ad94cd3` скидки, `7938334` форма промокода, `e0130b2` уведомления, `41dd17b` пересчёт корзины, `eab38c0` отчёт, `46df1e3` SSE и CI, `d2e6290` тип SSE, `490b93b` ожидание коммита, `0ff2493` приёмка, `2e81de4` изоляция HTTPS, `d8a8c7d` ASGI, `669579c` гонки и восстановление. |

Полная история после исходного среза выводится командой `git log --no-merges --reverse --oneline 4773316..v2.0`.
