
from django.urls import path

from .views import ai_recommendations_view, my_requests_view


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
]
