
from django.urls import path

from .views import asset_catalog


urlpatterns = [
    path(
        "",
        asset_catalog,
        name="asset_catalog",
    ),
]
