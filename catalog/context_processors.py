from .models import Category


def categories(request):
    """Дерево категорий для меню на каждой странице."""
    roots = Category.objects.filter(parent__isnull=True).prefetch_related("children")
    return {"menu_categories": roots}
