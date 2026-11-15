import uuid

from django.core.cache import cache
from django.db import transaction


def invalidate_catalog():
    def clear():
        cache.delete("category-menu")
        cache.set("catalog-generation", uuid.uuid4().hex, timeout=None)

    clear()
    transaction.on_commit(clear)


def product_key(slug):
    return f"product:{cache.get('catalog-generation', 'initial')}:{slug}"
