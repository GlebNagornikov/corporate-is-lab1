from django.core.cache import cache

from .models import Category


def categories(request):
    """Дерево категорий для меню на каждой странице."""
    roots = cache.get("category-menu")
    if roots is None:
        roots = list(Category.objects.filter(parent__isnull=True).prefetch_related("children"))
        cache.set("category-menu", roots)
    return {"menu_categories": roots}
