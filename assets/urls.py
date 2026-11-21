
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
    maintenance_cancel_view,
    inspection_management_view,
    inspection_request_view,
    inspection_complete_view,
    inspection_cancel_view
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
    path(
    "inspections/",
    inspection_management_view,
    name="inspection_management",
    ),
    path(
    "inspections/request/<uuid:asset_id>/",
    inspection_request_view,
    name="inspection_request",
    ),
    path(
    "inspections/<int:inspection_id>/complete/",
    inspection_complete_view,
    name="inspection_complete",
    ),
    path(
    "inspections/<int:inspection_id>/cancel/",
    inspection_cancel_view,
    name="inspection_cancel",
    ),

]
