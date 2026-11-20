
from django.urls import path
from .views import ai_recommendations_view

urlpatterns = [
    path(
        "recommendations/",
        ai_recommendations_view,
        name="ai_recommendations",
    ),
]
