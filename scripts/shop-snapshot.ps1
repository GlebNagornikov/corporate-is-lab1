param(
    [Parameter(Mandatory)]
    [ValidateSet('Export', 'Restore')]
    [string]$Action,

    [Parameter(Mandatory)]
    [ValidateSet('Dev', 'Https')]
    [string]$Profile,

    [Parameter(Mandatory)]
    [string]$Directory
)

$ErrorActionPreference = 'Stop'
$snapshotDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Directory)
$databaseDump = Join-Path $snapshotDirectory 'database.dump'
$mediaArchive = Join-Path $snapshotDirectory 'media.tar'
$snapshotId = [Guid]::NewGuid().ToString('N')
$databaseTemporary = "/tmp/shop-$snapshotId.dump"
$mediaTemporary = "/tmp/shop-$snapshotId.tar"
$composeOptions = @()
if ($Profile -eq 'Https') {
    $composeOptions = @('-f', 'docker-compose.prod.yml', '--env-file', '.env.prod')
}

function Invoke-ShopCompose {
    docker compose @composeOptions @args
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose завершился с кодом $LASTEXITCODE."
    }
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if ($Action -eq 'Export') {
        if ((Test-Path -LiteralPath $databaseDump) -or (Test-Path -LiteralPath $mediaArchive)) {
            throw 'Для экспорта укажите новый каталог.'
        }
        New-Item -ItemType Directory -Force -Path $snapshotDirectory | Out-Null
        try {
            Invoke-ShopCompose exec -T db sh -ec 'pg_dump -Fc --no-owner --no-privileges --exclude-table-data=public.django_session -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$1"; pg_restore --list "$1" >/dev/null' sh $databaseTemporary
            $mediaExport = @"
from pathlib import Path
import tarfile

from django.conf import settings
from catalog.models import Product, ProductImage

root = Path(settings.MEDIA_ROOT).resolve()
paths = set(Product.objects.exclude(image='').values_list('image', flat=True))
paths.update(ProductImage.objects.exclude(image='').values_list('image', flat=True))
with tarfile.open('$mediaTemporary', 'w') as archive:
    for name in sorted(paths):
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise RuntimeError(f'Missing or invalid media file: {name}')
        archive.add(path, arcname=name, recursive=False)
print(f'Media files: {len(paths)}')
"@
            $mediaExport | docker compose @composeOptions exec -T web python manage.py shell
            if ($LASTEXITCODE -ne 0) {
                throw 'Не удалось собрать архив обложек и фотографий.'
            }
            Invoke-ShopCompose cp "db:${databaseTemporary}" $databaseDump
            Invoke-ShopCompose cp "web:${mediaTemporary}" $mediaArchive
        }
        finally {
            docker compose @composeOptions exec -T db rm -f $databaseTemporary
            docker compose @composeOptions exec -T web rm -f $mediaTemporary
        }
        Write-Output "Снимок сохранён в $snapshotDirectory"
        return
    }

    if (!(Test-Path -LiteralPath $databaseDump -PathType Leaf) -or
        !(Test-Path -LiteralPath $mediaArchive -PathType Leaf)) {
        throw 'В каталоге снимка нужны database.dump и media.tar.'
    }
    Invoke-ShopCompose up -d --wait db
    $tableCount = Invoke-ShopCompose exec -T db sh -ec 'psql -XAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = current_schema()"'
    if (($tableCount -join '').Trim() -ne '0') {
        throw 'Для восстановления требуется пустая база. Укажите новый проект Compose или запустите восстановление до миграций.'
    }
    try {
        Invoke-ShopCompose cp $databaseDump "db:${databaseTemporary}"
        Invoke-ShopCompose exec -T db pg_restore --list --file=/dev/null $databaseTemporary
        Invoke-ShopCompose run --rm --no-deps -T --volume "${snapshotDirectory}:/snapshot:ro" --entrypoint sh web -ec 'tar -tf /snapshot/media.tar >/dev/null; mkdir -p /app/media; tar --no-same-owner -xf /snapshot/media.tar -C /app/media'
        Invoke-ShopCompose exec -T db sh -ec 'pg_restore --single-transaction --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$1"' sh $databaseTemporary
    }
    finally {
        docker compose @composeOptions exec -T db rm -f $databaseTemporary
    }
    Write-Output 'Снимок восстановлен. Запустите сервисы магазина по инструкции README.'
}
finally {
    Pop-Location
}
