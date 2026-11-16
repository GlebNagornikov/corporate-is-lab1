# Перенос данных на другой компьютер

Обычный запуск с `seed_demo` создаёт базовый каталог из 21 книги. Чтобы получить текущий
каталог, отзывы, заказы и учётные записи с прежними паролями, перенесите снимок PostgreSQL
вместе с обложками. Для каждого стенда используется свой снимок.

На Windows откройте [PowerShell 7](https://learn.microsoft.com/powershell/scripting/install/install-powershell-on-windows)
командой `pwsh` и перейдите в папку проекта. `$PSVersionTable.PSVersion` должен показать
версию 7.x. Встроенный Windows PowerShell 5.1 может неверно прочитать кириллицу в скрипте
и выдать `ParserError`. Если запуск проверенного скрипта из клона блокирует политика
выполнения, задайте `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`
в этом окне PowerShell 7. Настройка действует до закрытия окна.

На исходном компьютере при запущенном магазине выполните экспорт в новый каталог.
На время экспорта приостановите изменения каталога и загрузку обложек.

```powershell
.\scripts\shop-snapshot.ps1 -Action Export -Profile Dev -Directory .\backups\shop-dev
.\scripts\shop-snapshot.ps1 -Action Export -Profile Https -Directory .\backups\shop-https
```

На другом компьютере подготовьте ту же версию кода и окружение по инструкции для нужного
стенда. Скопируйте соответствующий каталог с `database.dump` и `media.tar`. Восстанавливайте
в пустую базу до миграций и `seed_demo`. Скрипт сам запустит PostgreSQL. Если какая-либо
команда завершилась ошибкой, устраните её перед переходом к следующей.

Для dev выполните:

```powershell
docker compose build web
.\scripts\shop-snapshot.ps1 -Action Restore -Profile Dev -Directory .\backups\shop-dev
docker compose up -d --build --wait
docker compose exec web python manage.py migrate --noinput
```

Если в dev уже запускали миграции или нужно сохранить прежнюю базу, остановите прежний
стенд командой `docker compose stop` (с его именем проекта, если оно было переопределено).
Затем задайте `$env:COMPOSE_PROJECT_NAME = 'knizhnaya-polka-restore'` с ещё не использованным
именем и выполните весь блок dev в этом же окне. Так скрипт и последующие команды увидят
один и тот же новый том PostgreSQL. При повторном запуске в новом окне задайте то же имя.
В dev файлы обложек распаковываются в `media` рабочей копии. Если нужно сохранить
существующие обложки, используйте отдельную рабочую копию с собственным `.env`.

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
