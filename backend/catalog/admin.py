from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html

from .models import Category, Product, ProductImage, ProductVariant, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "slug")
    list_select_related = ("parent",)
    list_filter = ("parent",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "position", "image_preview")
    readonly_fields = ("image_preview",)

    @admin.display(description="Превью")
    def image_preview(self, obj):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" alt="{}" style="max-height:100px">', obj.image.url, obj.alt_text
        )


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("name", "sku", "price", "stock", "is_active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    change_list_template = "admin/catalog/product/change_list.html"

    def get_urls(self):
        return [
            path(
                "import-csv/",
                self.admin_site.admin_view(self.import_csv),
                name="catalog_product_import",
            )
        ] + super().get_urls()

    def import_csv(self, request):
        from io import StringIO

        from .importing import import_products

        if not self.has_add_permission(request) or not self.has_change_permission(request):
            raise PermissionDenied

        class UploadForm(forms.Form):
            file = forms.FileField()
            dry_run = forms.BooleanField(required=False)

        form = UploadForm(request.POST or None, request.FILES or None)
        errors = []
        if request.method == "POST" and form.is_valid():
            try:
                count = import_products(
                    StringIO(form.cleaned_data["file"].read().decode("utf-8-sig")),
                    dry_run=form.cleaned_data["dry_run"],
                )
                self.message_user(request, f"Строк обработано: {count}")
            except (ValidationError, UnicodeError) as error:
                errors = (
                    error.messages
                    if isinstance(error, ValidationError)
                    else ["Файл должен быть в UTF-8."]
                )
        return render(
            request,
            "admin/catalog/product/import.html",
            {**self.admin_site.each_context(request), "form": form, "errors": errors},
        )

    inlines = (ProductImageInline, ProductVariantInline)
    list_display = ("name", "sku", "category", "price", "old_price", "stock", "is_active")
    list_editable = ("price", "old_price", "stock", "is_active")
    list_filter = ("is_active", "category")
    list_select_related = ("category",)
    search_fields = ("name", "sku")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("image_preview", "created_at", "updated_at")
    autocomplete_fields = ("category",)

    @admin.display(description="Превью")
    def image_preview(self, product):
        if not product.image:
            return "—"
        return format_html('<img src="{}" style="max-height:150px">', product.image.url)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "author", "rating", "is_published", "created_at")
    list_filter = ("is_published", "rating")
    list_select_related = ("product", "author")
    search_fields = ("product__name", "author__username", "text")
    actions = ("publish", "hide")

    @admin.action(description="Опубликовать выбранные отзывы")
    def publish(self, request, queryset):
        queryset.update(is_published=True)
        from .caching import invalidate_catalog

        invalidate_catalog()

    @admin.action(description="Скрыть выбранные отзывы")
    def hide(self, request, queryset):
        queryset.update(is_published=False)
        from .caching import invalidate_catalog

        invalidate_catalog()
