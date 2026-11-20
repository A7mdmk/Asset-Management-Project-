
from django.urls import path

from .views import (
    ai_recommendations_view,
    my_requests_view,
    submit_request_view,
)


urlpatterns = [
    path(
        "recommendations/",
        ai_recommendations_view,
        name="ai_recommendations",
    ),
    path(
        "my-requests/",
        my_requests_view,
        name="my_requests",
    ),
    path(
        "request/<uuid:asset_id>/",
        submit_request_view,
        name="submit_request",
    ),
]
