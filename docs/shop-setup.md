# Запуск и перенос «Книжной полки»

Основной порядок установки программ, клонирования и запуска в [README](../README.md#запуск-на-новом-компьютере-с-windows). Все команды ниже вводите в PowerShell из папки проекта. На каждый блок с долгоживущим сервером откройте отдельное окно. В новом окне сначала перейдите в папку проекта, например `Set-Location "$HOME/knizhnaya-polka"`.

[Запуск Django и Vite в отдельных окнах](../README.md#django-и-vite-в-отдельных-окнах)

## HTTPS на этом компьютере

Стенд собирает React в nginx и использует отдельную базу, медиа и очередь. Перед первым запуском проверьте, что свободны порты 80, 443 и 8026. Dev может оставаться запущенным. Следующий блок создаёт настройки и сертификат для нового стенда. При повторном запуске переходите к командам Compose, чтобы сохранить пароль уже созданной базы.

```powershell
$pythonRandom = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$paymentRandom = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$dbRandom = [Guid]::NewGuid().ToString('N')
(Get-Content env/production.example) |
    ForEach-Object { $_ -replace '^SECRET_KEY=.*', "SECRET_KEY=$pythonRandom" } |
    ForEach-Object { $_ -replace '^PAYMENT_WEBHOOK_SECRET=.*', "PAYMENT_WEBHOOK_SECRET=$paymentRandom" } |
    ForEach-Object { $_ -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$dbRandom" } |
    Set-Content .env.prod -Encoding ascii
New-Item -ItemType Directory -Force nginx/certs | Out-Null
$openssl = Join-Path (Split-Path (Split-Path (Get-Command git.exe).Source)) 'usr/bin/openssl.exe'
& $openssl req -x509 -nodes -newkey rsa:2048 -days 365 -keyout nginx/certs/localhost.key -out nginx/certs/localhost.crt -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost'
```

Если Git установлен в нестандартную папку или `$openssl` не найден, укажите полный путь к `usr/bin/openssl.exe` внутри установленного Git for Windows.

```powershell
$shopCompose = @('-f', 'docker-compose.prod.yml', '--env-file', '.env.prod')
docker compose @shopCompose up -d --build --wait --wait-timeout 180
docker compose @shopCompose exec web python manage.py seed_demo --password 'DemoShop2026!'
curl.exe -fk https://localhost/healthz/
```

Дождитесь `web` и `nginx` в состоянии `Healthy`, а `migrate` — с завершением `Exited (0)`. В результате `curl.exe` будет JSON со статусом `ok`. Откройте [магазин](https://localhost/). Браузер предупредит о локальном самоподписанном сертификате. Для этого адреса подтвердите исключение в браузере. [API](https://localhost/api/catalog/products/), [Django admin](https://localhost/admin/) и [письма](http://127.0.0.1:8026/) доступны по отдельным ссылкам. Для Swagger на HTTPS сначала войдите под сотрудником в Django admin. Для остановки используйте `docker compose @shopCompose stop`.

Для полного Playwright с отдельной базой укажите [тестовый профиль HTTPS](lab11-release-checks.md#проверки-на-https).

## Перенос своих заказов, пользователей и изображений

Чистый клон и `seed_demo` создают пустой магазин с демокаталогом. Для переноса своей базы и обложек используйте архив из снимка. Выполняйте экспорт, когда никто не меняет данные магазина. Архив содержит данные покупателей и хеши паролей. Храните и переносите его как закрытый файл.

Порядок экспорта, проверки и восстановления описан в [инструкции по снимкам](shop-snapshots.md).
