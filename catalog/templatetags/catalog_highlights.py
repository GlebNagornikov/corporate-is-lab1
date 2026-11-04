from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def search_highlight(value):
    """Escape all content; allow only attribute-free highlight tags."""
    escaped = escape(value)
    return mark_safe(escaped.replace("&lt;mark&gt;", "<mark>").replace("&lt;/mark&gt;", "</mark>"))
