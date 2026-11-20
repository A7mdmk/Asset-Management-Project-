
from django.urls import path

from .views import (
    asset_catalog,
    asset_management_view,
    asset_registration_view,
    asset_publication_view,
    maintenance_management_view,
    maintenance_report_view,
    maintenance_start_view,
    maintenance_complete_view,
    maintenance_cancel_view
)


urlpatterns = [
    path(
        "",
        asset_catalog,
        name="asset_catalog",
    ),
    path(
        "manage/",
        asset_management_view,
        name="asset_management",
    ),
    path(
        "register/",
        asset_registration_view,
        name="asset_registration",
    ),
    path(
        "manage/<uuid:asset_id>/publication/",
        asset_publication_view,
        name="asset_publication",
    ),
    path(
        "maintenance/",
        maintenance_management_view,
        name="maintenance_management",
    ),
    path(
        "maintenance/report/<uuid:asset_id>/",
        maintenance_report_view,
        name="maintenance_report",
    ),
    path(
        "maintenance/<int:maintenance_id>/start/",
        maintenance_start_view,
        name="maintenance_start",
    ),
    path(
        "maintenance/<int:maintenance_id>/complete/",
        maintenance_complete_view,
        name="maintenance_complete",
    ),
    path(
    "maintenance/<int:maintenance_id>/cancel/",
    maintenance_cancel_view,
    name="maintenance_cancel",
    ),
]
