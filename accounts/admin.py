
from django.contrib import admin

from .models import DepartmentApprover


@admin.register(DepartmentApprover)
class DepartmentApproverAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "department",
        "is_active",
    )

    list_filter = (
        "department",
        "is_active",
    )

    search_fields = (
        "user__username",
        "department__name",
    )

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
