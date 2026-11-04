from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, ProductImage, Review


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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = (ProductImageInline,)
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

    @admin.action(description="Скрыть выбранные отзывы")
    def hide(self, request, queryset):
        queryset.update(is_published=False)
