import io
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw

from catalog.models import Category, Product

CATEGORIES = [
    # (slug, название, slug родителя)
    ("electronics", "Электроника", None),
    ("laptops", "Ноутбуки", "electronics"),
    ("smartphones", "Смартфоны", "electronics"),
    ("headphones", "Наушники", "electronics"),
    ("appliances", "Бытовая техника", None),
    ("kettles", "Чайники", "appliances"),
    ("vacuums", "Пылесосы", "appliances"),
    ("books", "Книги", None),
    ("programming", "Программирование", "books"),
    ("business", "Бизнес-литература", "books"),
]

# (артикул, категория, название, цена, старая цена, остаток, описание)
PRODUCTS = [
    (
        "NB-001",
        "laptops",
        "Ноутбук Lenovo IdeaPad 5",
        "64990",
        "72990",
        7,
        "Лёгкий ноутбук для учёбы и работы: 14 дюймов, 16 ГБ памяти, SSD 512 ГБ.",
    ),
    (
        "NB-002",
        "laptops",
        "Ноутбук ASUS Vivobook 16",
        "54990",
        None,
        12,
        "Большой экран 16 дюймов, тихая система охлаждения, автономность до 10 часов.",
    ),
    (
        "NB-003",
        "laptops",
        "Ноутбук Apple MacBook Air 13",
        "119990",
        None,
        3,
        "Тонкий алюминиевый корпус, процессор M-серии, работает без вентилятора.",
    ),
    (
        "NB-004",
        "laptops",
        "Игровой ноутбук MSI Katana 15",
        "99990",
        "109990",
        0,
        "Дискретная видеокарта, экран 144 Гц, подсветка клавиатуры.",
    ),
    (
        "NB-005",
        "laptops",
        "Ноутбук HUAWEI MateBook D 14",
        "49990",
        None,
        5,
        "Металлический корпус, сканер отпечатка пальца в кнопке питания.",
    ),
    (
        "SP-001",
        "smartphones",
        "Смартфон Samsung Galaxy A56",
        "34990",
        "39990",
        20,
        "Камера 50 Мп, защита от воды, обновления системы на шесть лет.",
    ),
    (
        "SP-002",
        "smartphones",
        "Смартфон Xiaomi Redmi Note 14",
        "21990",
        None,
        35,
        "Яркий AMOLED-экран, быстрая зарядка 45 Вт, аккумулятор 5500 мАч.",
    ),
    (
        "SP-003",
        "smartphones",
        "Смартфон Apple iPhone 16",
        "89990",
        None,
        4,
        "Новая кнопка управления камерой, яркий дисплей, долгая поддержка обновлений.",
    ),
    (
        "SP-004",
        "smartphones",
        "Смартфон Google Pixel 9a",
        "44990",
        "49990",
        0,
        "Чистый Android, лучшая в классе ночная съёмка.",
    ),
    (
        "SP-005",
        "smartphones",
        "Смартфон realme 14 Pro",
        "27990",
        None,
        15,
        "Тонкий корпус, перископная камера, экран 120 Гц.",
    ),
    (
        "HP-001",
        "headphones",
        "Беспроводные наушники Sony WH-1000XM5",
        "32990",
        "36990",
        9,
        "Полноразмерные наушники с активным шумоподавлением и временем работы до 30 часов.",
    ),
    (
        "HP-002",
        "headphones",
        "Наушники Apple AirPods Pro 2",
        "24990",
        None,
        14,
        "Внутриканальные беспроводные наушники с шумоподавлением и прозрачным режимом.",
    ),
    (
        "HP-003",
        "headphones",
        "Наушники JBL Tune 520BT",
        "3990",
        "4990",
        50,
        "Недорогие накладные беспроводные наушники, складная конструкция.",
    ),
    (
        "HP-004",
        "headphones",
        "Проводные наушники Sennheiser HD 560S",
        "15990",
        None,
        6,
        "Открытые мониторные наушники для музыки и сведения.",
    ),
    (
        "KT-001",
        "kettles",
        "Электрический чайник Xiaomi Kettle 2",
        "2990",
        None,
        40,
        "Объём 1,7 литра, двойные стенки, корпус не нагревается.",
    ),
    (
        "KT-002",
        "kettles",
        "Чайник Bosch TWK3A011",
        "2490",
        "2990",
        25,
        "Классический пластиковый чайник, защита от включения без воды.",
    ),
    (
        "KT-003",
        "kettles",
        "Стеклянный чайник Redmond RK-G178",
        "3490",
        None,
        0,
        "Стеклянная колба с подсветкой, поддержание температуры.",
    ),
    (
        "KT-004",
        "kettles",
        "Умный чайник Polaris PWK 1755",
        "4990",
        "5990",
        8,
        "Управление со смартфона, выбор температуры от 40 до 100 градусов.",
    ),
    (
        "VC-001",
        "vacuums",
        "Робот-пылесос Dreame L10s",
        "39990",
        "45990",
        6,
        "Влажная и сухая уборка, станция самоочистки, построение карты квартиры.",
    ),
    (
        "VC-002",
        "vacuums",
        "Беспроводной пылесос Dyson V12",
        "59990",
        None,
        2,
        "Вертикальный пылесос с лазерной подсветкой пыли и экраном.",
    ),
    (
        "VC-003",
        "vacuums",
        "Пылесос Samsung VC18M",
        "9990",
        None,
        18,
        "Мешковый пылесос с циклонным фильтром, мощность всасывания 380 Вт.",
    ),
    (
        "VC-004",
        "vacuums",
        "Робот-пылесос Xiaomi Robot Vacuum S20",
        "21990",
        "24990",
        11,
        "Лидар, приложение Mi Home, работа по расписанию.",
    ),
    (
        "BK-001",
        "programming",
        "Книга «Чистый код»",
        "1290",
        None,
        30,
        "Роберт Мартин о том, как писать код, который легко читать и сопровождать.",
    ),
    (
        "BK-002",
        "programming",
        "Книга «Django 5 в примерах»",
        "2490",
        "2990",
        12,
        "Пошаговое создание веб-приложений на Django: блог, магазин, платформа.",
    ),
    (
        "BK-003",
        "programming",
        "Книга «Изучаем SQL»",
        "1590",
        None,
        0,
        "Основы языка запросов, соединения таблиц, транзакции и индексы.",
    ),
    (
        "BK-004",
        "programming",
        "Книга «Docker. Практическое руководство»",
        "1890",
        None,
        9,
        "Контейнеры, образы, тома и сети: как упаковать приложение и запустить его везде.",
    ),
    (
        "BK-005",
        "programming",
        "Книга «Высоконагруженные приложения»",
        "2790",
        None,
        7,
        "Мартин Клеппман о базах данных, репликации и распределённых системах.",
    ),
    (
        "BK-006",
        "business",
        "Книга «Цель. Процесс непрерывного улучшения»",
        "990",
        None,
        22,
        "Бизнес-роман о теории ограничений и управлении производством.",
    ),
    (
        "BK-007",
        "business",
        "Книга «Канбан»",
        "1190",
        "1490",
        10,
        "Как наладить поток задач в команде и сократить время выполнения.",
    ),
    (
        "BK-008",
        "business",
        "Книга «Проект Феникс»",
        "1390",
        None,
        15,
        "Роман об ИТ-отделе, DevOps и о том, почему релизы ломаются по пятницам.",
    ),
]

COLORS = {
    "laptops": "#4c6ef5",
    "smartphones": "#15aabf",
    "headphones": "#7950f2",
    "kettles": "#fd7e14",
    "vacuums": "#40c057",
    "programming": "#e64980",
    "business": "#868e96",
}


def make_image(sku, color):
    image = Image.new("RGB", (600, 400), color)
    draw = ImageDraw.Draw(image)
    draw.text((30, 30), sku, fill="white", font_size=64)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue(), name=f"{sku.lower()}.png")


class Command(BaseCommand):
    help = "Заполняет каталог демонстрационными категориями и товарами (можно запускать повторно)"

    def add_arguments(self, parser):
        parser.add_argument("--images", action="store_true", help="сгенерировать картинки товаров")

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for slug, name, parent_slug in CATEGORIES:
            categories[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={"name": name, "parent": categories.get(parent_slug)}
            )

        created_count = 0
        for sku, category_slug, name, price, old_price, stock, description in PRODUCTS:
            product, created = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "category": categories[category_slug],
                    "name": name,
                    "slug": sku.lower(),
                    "price": Decimal(price),
                    "old_price": Decimal(old_price) if old_price else None,
                    "stock": stock,
                    "description": description,
                },
            )
            created_count += created
            if options["images"] and not product.image:
                product.image.save(f"{sku.lower()}.png", make_image(sku, COLORS[category_slug]))

        self.stdout.write(
            self.style.SUCCESS(
                f"Категорий: {len(categories)}, товаров: {len(PRODUCTS)} (новых {created_count})"
            )
        )
