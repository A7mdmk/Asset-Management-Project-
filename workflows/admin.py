
from django.contrib import admin

from .models import ResourceRequest, RequestApproval


@admin.register(ResourceRequest)
class ResourceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "asset",
        "requester",
        "quantity",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("asset__name", "requester__username")
    readonly_fields = (
        "asset",
        "requester",
        "quantity",
        "reason",
        "status",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RequestApproval)
class RequestApprovalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request",
        "approver",
        "decision",
        "created_at",
    )
    readonly_fields = (
        "request",
        "approver",
        "decision",
        "comment",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
