from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.manager_permissions import IsShopManager
from config.api_docs import MANAGER_ACCESS_ERRORS

from .book_import import MAX_BOOK_CSV_BYTES, import_books
from .manager_serializers import (
    ManagerBookSerializer,
    ManagerBookWriteSerializer,
    ManagerGenreWriteSerializer,
    ManagerVariantWriteSerializer,
)
from .models import BOOKS_ROOT_SLUG, Category, Product
from .serializers import CategorySerializer
from .services import create_genre

CATALOG_ERRORS = {
    400: OpenApiResponse(
        description="Ошибки по именам полей формы или общее сообщение в detail.",
        examples=[OpenApiExample("Ошибка обложки", value={"image": ["Загрузите JPEG или PNG."]})],
    ),
    **MANAGER_ACCESS_ERRORS,
}
BOOK_PAYLOAD = {"multipart/form-data": ManagerBookWriteSerializer}
BOOK_NOT_FOUND = OpenApiResponse(description="Издание не найдено.")


class BookCsvUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    dry_run = serializers.BooleanField(default=True)

    def validate_file(self, file):
        if file.size > MAX_BOOK_CSV_BYTES:
            raise serializers.ValidationError("Размер CSV должен быть не больше 1 МБ.")
        return file


class BookCsvResultSerializer(serializers.Serializer):
    processed = serializers.IntegerField()
    dry_run = serializers.BooleanField()


@extend_schema_view(
    list=extend_schema(
        description="Все жанры для формы сотрудника, включая пустые.",
        responses={200: CategorySerializer(many=True), **MANAGER_ACCESS_ERRORS},
    ),
)
class ManagerCategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = (
        Category.objects.exclude(slug=BOOKS_ROOT_SLUG)
        .select_related("parent")
        .order_by("name", "pk")
    )
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManager]
    manager_permissions = {
        "list": ("catalog.view_category",),
        "create": ("catalog.view_category", "catalog.add_category"),
    }
    pagination_class = None

    @extend_schema(
        description="Создаёт жанр внутри раздела «Книги». Адрес формируется автоматически.",
        request=ManagerGenreWriteSerializer,
        responses={
            201: CategorySerializer,
            400: OpenApiResponse(description="Ошибка поля name."),
            **MANAGER_ACCESS_ERRORS,
        },
    )
    def create(self, request):
        serializer = ManagerGenreWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            genre = create_genre(serializer.validated_data["name"])
        except ValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
        return Response(self.get_serializer(genre).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        description="Карточки всех состояний, включая черновики и снятые с продажи.",
        parameters=[
            OpenApiParameter("q", str, description="Часть названия, имени автора, SKU или ISBN."),
        ],
        responses={200: ManagerBookSerializer(many=True), **MANAGER_ACCESS_ERRORS},
    ),
    retrieve=extend_schema(
        description="Карточка издания и его складские варианты для сотрудника.",
        responses={200: ManagerBookSerializer, 404: BOOK_NOT_FOUND, **MANAGER_ACCESS_ERRORS},
    ),
)
class ManagerBookViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = (
        Product.objects.select_related("category__parent", "book")
        .prefetch_related("variants")
        .order_by("-created_at", "-pk")
    )
    serializer_class = ManagerBookSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManager]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    manager_permissions = {
        "list": ("catalog.view_product",),
        "retrieve": ("catalog.view_product",),
        "create": ("catalog.view_category", "catalog.add_product"),
        "partial_update": (
            "catalog.view_product",
            "catalog.view_category",
            "catalog.change_product",
        ),
        "destroy": ("catalog.view_product", "catalog.delete_product"),
        "import_csv": ("catalog.view_category", "catalog.add_product", "catalog.change_product"),
        "variant": ("catalog.view_product", "catalog.change_productvariant"),
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            query = self.request.query_params.get("q", "").strip()
            if query:
                queryset = queryset.filter(
                    Q(name__icontains=query)
                    | Q(book__author__icontains=query)
                    | Q(sku__icontains=query)
                    | Q(book__isbn__icontains=query)
                )
        return queryset

    @extend_schema(
        description="Создаёт издание. Без is_active издание остаётся черновиком.",
        request=BOOK_PAYLOAD,
        responses={201: ManagerBookSerializer, **CATALOG_ERRORS},
    )
    def create(self, request):
        return self.save_book(request, status.HTTP_201_CREATED)

    @extend_schema(
        description="Редактирует поля издания. Без нового файла сохраняет прежнюю обложку.",
        request=BOOK_PAYLOAD,
        responses={200: ManagerBookSerializer, 404: BOOK_NOT_FOUND, **CATALOG_ERRORS},
    )
    @transaction.atomic
    def partial_update(self, request, pk=None):
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
        self.check_object_permissions(request, product)
        return self.save_book(request, status.HTTP_200_OK, product)

    @extend_schema(
        description="Удаляет карточку. Если издание есть в истории заказов, вернёт 409.",
        responses={
            204: None,
            404: BOOK_NOT_FOUND,
            409: OpenApiResponse(description="Книга есть в заказах, её можно снять с продажи."),
            **MANAGER_ACCESS_ERRORS,
        },
    )
    @transaction.atomic
    def destroy(self, request, pk=None):
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
        self.check_object_permissions(request, product)
        try:
            product.delete()
        except ProtectedError:
            return Response(
                {"detail": "Книга есть в истории заказов. Снимите её с продажи в карточке."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Проверяет или импортирует книги из UTF-8 CSV. Сопоставляет строки по SKU.",
        request={"multipart/form-data": BookCsvUploadSerializer},
        responses={
            200: BookCsvResultSerializer,
            400: OpenApiResponse(description="Ошибки файла с номерами строк в поле file."),
            **MANAGER_ACCESS_ERRORS,
        },
    )
    @action(detail=False, methods=["post"], url_path="import-csv", parser_classes=[MultiPartParser])
    def import_csv(self, request):
        payload = BookCsvUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        upload = payload.validated_data["file"]
        dry_run = payload.validated_data["dry_run"]
        try:
            processed = import_books(upload, dry_run=dry_run)
        except ValidationError as error:
            raise serializers.ValidationError({"file": error.messages}) from error
        return Response({"processed": processed, "dry_run": dry_run})

    def save_book(self, request, status_code, product=None):
        serializer = ManagerBookWriteSerializer(
            product, data=request.data, partial=product is not None
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                saved = serializer.save()
        except IntegrityError as error:
            raise serializers.ValidationError(
                {"detail": "Конфликт данных. Проверьте уникальность артикула и адреса книги."}
            ) from error
        return Response(self.get_serializer(saved).data, status=status_code)

    @extend_schema(
        description="Меняет цену, остаток и доступность существующего складского варианта.",
        parameters=[OpenApiParameter("variant_id", int, OpenApiParameter.PATH)],
        request=ManagerVariantWriteSerializer,
        responses={
            200: ManagerBookSerializer,
            404: OpenApiResponse(description="Издание или его складской вариант не найден."),
            **CATALOG_ERRORS,
        },
    )
    @action(detail=True, methods=["patch"], url_path=r"variants/(?P<variant_id>[0-9]+)")
    @transaction.atomic
    def variant(self, request, pk=None, variant_id=None):
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
        self.check_object_permissions(request, product)
        variants = product.variants.filter(is_default=False)
        variant = get_object_or_404(variants.select_for_update(), pk=variant_id)
        serializer = ManagerVariantWriteSerializer(variant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if values.get("is_active", variant.is_active):
            other_stock = (
                variants.filter(is_active=True)
                .exclude(pk=variant.pk)
                .aggregate(total=Sum("stock", default=0))["total"]
            )
            if other_stock + values.get("stock", variant.stock) > 2147483647:
                raise serializers.ValidationError({"stock": "Слишком большой суммарный остаток."})
        serializer.save()
        product.refresh_from_db()
        return Response(self.get_serializer(product).data)
