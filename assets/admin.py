
from django.contrib import admin
from django.db import transaction

from .models import Asset, Category, Department, StockBalance
from .services import initialize_stock


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "department",
        "custodian",
        "condition",
        "publication",
    )

    search_fields = ("name", "asset_tag")

    list_filter = (
        "category",
        "department",
        "condition",
        "lifecycle",
        "publication",
    )

    readonly_fields = (
        "quantity",
        "department",
        "custodian",
        "tracking_mode",
        "lifecycle",
        "publication",
    )

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return self.readonly_fields

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)

        if not change:
            # Create the initial stock balance only once.
            initialize_stock(obj)


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "free",
        "held",
        "in_transit",
        "in_use",
        "blocked",
        "retired",
        "total",
    )

    readonly_fields = (
        "asset",
        "free",
        "held",
        "in_transit",
        "in_use",
        "blocked",
        "retired",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
