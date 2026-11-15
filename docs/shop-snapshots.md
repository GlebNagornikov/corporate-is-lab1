# Перенос данных на другой компьютер

Обычный запуск с `seed_demo` создаёт базовый каталог из 21 книги. Чтобы получить текущий
каталог, отзывы, заказы и учётные записи с прежними паролями, перенесите снимок PostgreSQL
вместе с обложками. Для каждого стенда используется свой снимок.

На исходном компьютере при запущенном магазине выполните экспорт в новый каталог.
На время экспорта приостановите изменения каталога и загрузку обложек.

```powershell
.\scripts\shop-snapshot.ps1 -Action Export -Profile Dev -Directory .\backups\shop-dev
.\scripts\shop-snapshot.ps1 -Action Export -Profile Https -Directory .\backups\shop-https
```

На другом компьютере подготовьте ту же версию кода и окружение по инструкции для нужного
стенда. Скопируйте соответствующий каталог с `database.dump` и `media.tar`. Восстанавливайте
в свежую базу до обычного запуска Compose. Скрипт сам запустит PostgreSQL.

Для dev выполните:

```powershell
docker compose build web
.\scripts\shop-snapshot.ps1 -Action Restore -Profile Dev -Directory .\backups\shop-dev
docker compose up -d --build
docker compose exec web python manage.py migrate
```

Для HTTPS выполните:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod build web
.\scripts\shop-snapshot.ps1 -Action Restore -Profile Https -Directory .\backups\shop-https
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

После восстановления пользователи входят заново. Снимок содержит данные пользователей
и хеши паролей, поэтому передавайте его приватно. Переменные окружения, сертификаты и
активные сеансы создаются на новом компьютере отдельно.

Останавливайте стенд командой `docker compose stop`. Команда `down -v` удаляет тома с БД,
Redis и загруженными в HTTPS-стенд изображениями.
