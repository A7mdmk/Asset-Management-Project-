
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "accounts/",
        include("accounts.urls"),
    ),

    path(
        "workflows/",
        include("workflows.urls"),
    ),

    path(
        "assets/",
        include("assets.urls"),
    ),
]
