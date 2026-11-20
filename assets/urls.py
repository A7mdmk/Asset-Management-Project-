
from django.urls import path
from .views import (
    asset_catalog,
    asset_management_view,
    asset_registration_view,
    asset_publication_view,
)
from .views import (
    asset_catalog,
    asset_management_view,
    asset_registration_view,
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
]
