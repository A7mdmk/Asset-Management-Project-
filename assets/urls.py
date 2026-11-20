
from django.urls import path

from .views import asset_catalog, asset_management_view


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
]
