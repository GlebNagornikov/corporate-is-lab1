from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    SearchVectorField,
    TrigramWordSimilarity,
)
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, F, Q
from django.urls import reverse


class Category(models.Model):
    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Адрес в URL", max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    description = models.TextField("Описание", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "категория"
        verbose_name_plural = "категории"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{reverse('catalog:product_list')}?category={self.slug}"

    def get_descendant_ids(self):
        """id самой категории и всех её подкатегорий любой глубины."""
        ids = [self.pk]
        level = [self.pk]
        while level:
            level = list(Category.objects.filter(parent_id__in=level).values_list("pk", flat=True))
            ids += level
        return ids


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_rating(self):
        published = Q(reviews__is_published=True)
        return self.annotate(
            rating=Avg("reviews__rating", filter=published),
            reviews_count=Count("reviews", filter=published),
        )

    def search(self, text):
        query = SearchQuery(text, config="russian", search_type="websearch")
        return (
            self.filter(search_vector=query)
            .annotate(rank=SearchRank(F("search_vector"), query))
            .order_by("-rank")
        )

    def similar_to(self, text, threshold=0.4):
        """Товары, в названии которых есть слово, похожее на text (для опечаток)."""
        return (
            self.annotate(similarity=TrigramWordSimilarity(text, "name"))
            .filter(similarity__gt=threshold)
            .order_by("-similarity")
        )


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
    )
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Адрес в URL", max_length=200, unique=True)
    sku = models.CharField("Артикул", max_length=32, unique=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    old_price = models.DecimalField(
        "Старая цена", max_digits=10, decimal_places=2, null=True, blank=True
    )
    stock = models.PositiveIntegerField("Остаток", default=0)
    is_active = models.BooleanField("Показывать в каталоге", default=True)
    image = models.ImageField("Фото", upload_to="products/%Y/%m/", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)
    search_vector = models.GeneratedField(
        expression=SearchVector("name", weight="A", config="russian")
        + SearchVector("description", weight="B", config="russian"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "товар"
        verbose_name_plural = "товары"
        indexes = [
            GinIndex(fields=["search_vector"], name="product_search_idx"),
            GinIndex(fields=["name"], name="product_name_trgm_idx", opclasses=["gin_trgm_ops"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="product_price_positive"),
            models.CheckConstraint(
                condition=Q(old_price__isnull=True) | Q(old_price__gt=F("price")),
                name="product_old_price_gt_price",
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:product_detail", args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def discount_percent(self):
        if not self.old_price:
            return 0
        return round((1 - self.price / self.old_price) * 100)


class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews", verbose_name="Товар"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Автор",
    )
    rating = models.PositiveSmallIntegerField(
        "Оценка", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    text = models.TextField("Отзыв")
    is_published = models.BooleanField("Опубликован", default=True)
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "отзыв"
        verbose_name_plural = "отзывы"
        constraints = [
            models.UniqueConstraint(fields=["product", "author"], name="one_review_per_author"),
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"
            ),
        ]

    def __str__(self):
        return f"{self.product}: {self.rating}★ от {self.author}"
