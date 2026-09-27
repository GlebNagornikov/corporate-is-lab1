from django.contrib import admin

# Register your models here.

from .models import Employee, Department

admin.site.register(Department)
@admin.register(Employee)

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "department")
    list_filter = ("department",)
