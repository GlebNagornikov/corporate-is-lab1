param(
    [Parameter(Mandatory)]
    [string]$SourceProject
)

$ErrorActionPreference = 'Stop'
$sourceCompose = @('-p', $SourceProject, '-f', 'docker-compose.prod.yml', '--env-file', '.env.prod')
$restoreProject = 'shop-restore-check-' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$restoreCompose = @('-p', $restoreProject, '-f', 'docker-compose.prod.yml', '--env-file', '.env.prod')
$snapshot = Join-Path ([System.IO.Path]::GetTempPath()) $restoreProject

$manifestCode = @'
from hashlib import sha256
from json import dumps

from catalog.models import Product, ProductImage, ProductVariant
from orders.models import Order, OrderItem, OrderStatusLog

def rows(model, *fields):
    return list(model.objects.order_by("pk").values_list(*fields))

def media(model):
    result = []
    for row in model.objects.exclude(image="").order_by("pk"):
        with row.image.open("rb") as file:
            result.append((row.pk, row.image.name, sha256(file.read()).hexdigest()))
    return result

orders = rows(Order, "pk", "user_id", "status", "total")
items = rows(OrderItem, "pk", "order_id", "product_id", "variant_id", "price", "quantity")
covers = media(Product)
if not (orders and items and covers):
    raise RuntimeError("The source must contain orders, order items, and book covers.")
print(dumps({
    "products": rows(Product, "pk", "sku", "price", "stock"),
    "variants": rows(ProductVariant, "pk", "product_id", "sku", "stock", "is_legacy_return"),
    "orders": orders,
    "items": items,
    "history": rows(OrderStatusLog, "pk", "order_id", "from_status", "to_status"),
    "covers": covers,
    "gallery": media(ProductImage),
}, default=str, sort_keys=True))
'@

function Get-ShopManifest([string[]]$Compose) {
    $manifest = $manifestCode | docker compose @Compose exec -T web python manage.py shell --no-imports
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось проверить данные и медиа магазина.' }
    return $manifest -join "`n"
}

Push-Location (Split-Path -Parent $PSScriptRoot)
$previousProject = $env:COMPOSE_PROJECT_NAME
try {
    $expected = Get-ShopManifest $sourceCompose
    $env:COMPOSE_PROJECT_NAME = $SourceProject
    & "$PSScriptRoot/shop-snapshot.ps1" -Action Export -Profile Https -Directory $snapshot
    $env:COMPOSE_PROJECT_NAME = $restoreProject
    & "$PSScriptRoot/shop-snapshot.ps1" -Action Restore -Profile Https -Directory $snapshot
    docker compose @restoreCompose up -d --wait --wait-timeout 120 web
    if ($LASTEXITCODE -ne 0) { throw 'Магазин не запустился после восстановления.' }
    $actual = Get-ShopManifest $restoreCompose
    if ($actual -cne $expected) { throw 'Данные или хеши изображений отличаются от исходного стенда.' }
    Write-Output 'После восстановления совпали каталог, остатки, заказы, история и SHA-256 изображений.'
}
finally {
    $env:COMPOSE_PROJECT_NAME = $previousProject
    try {
        docker compose @restoreCompose down --volumes
        if ($LASTEXITCODE -ne 0) { throw 'Не удалось убрать временный стенд восстановления.' }
    }
    finally {
        foreach ($file in 'database.dump', 'media.tar') {
            $path = Join-Path $snapshot $file
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
        }
        if (Test-Path -LiteralPath $snapshot) { [System.IO.Directory]::Delete($snapshot) }
        Pop-Location
    }
}
