from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Register your models here.
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Корпоративные данные", {"fields": ("phone", "employee")}),
    )
    list_display = ("username", "last_name", "first_name", "employee", "is_staff")
